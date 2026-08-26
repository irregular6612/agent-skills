#!/usr/bin/env python3
"""
Detect shape patterns (H&S, Double Top/Bottom) from OHLCV using zigzag pivots.

Reads:
  <data>/<ticker>-ohlcv.json   (daily OHLCV — daily timeframe only for v1)

Writes:
  <data>/<ticker>-patterns.json

See references/pattern-detection-spec.md for the algorithm and the rationale
behind every threshold. This module is the executable companion to that doc;
the docstrings here mirror the spec but the spec is the source of truth.

Usage:
  python detect_patterns.py <ticker1> [...] --in <session>/data
"""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path

import numpy as np
from zigzag import peak_valley_pivots


# ---------------------------------------------------------------------------
# Defaults — see references/pattern-detection-spec.md for the why behind each.
# ---------------------------------------------------------------------------
DEFAULTS = {
    "pivot_threshold_pct": 3.0,
    "min_bars_between_pivots": 5,
    "shoulder_equality_pct": 5.0,
    "peak_equality_pct": 3.0,
    "head_prominence_pct": 3.0,
    "prior_trend_lookback_bars": 20,
    "prior_trend_min_pct": 5.0,
    "max_pattern_bars": 120,
    "volume_check": True,
}


# ---------------------------------------------------------------------------
# Pivot extraction
# ---------------------------------------------------------------------------
def extract_pivots(rows: list[dict], threshold_pct: float) -> list[dict]:
    """Return alternating peak/valley pivots.

    Each output dict has: date, price, kind ("peak"|"valley"), bar_idx.

    Driver series is `close` (so wicks don't flip pivots), but the *price* we
    report for a peak is its `high` and for a valley its `low` — this avoids
    intra-bar bias when projecting necklines and targets.
    """
    if len(rows) < 5:
        return []
    closes = np.array([r["close"] for r in rows], dtype=float)
    pivot_flags = peak_valley_pivots(
        closes, threshold_pct / 100.0, -threshold_pct / 100.0
    )
    out: list[dict] = []
    for i, flag in enumerate(pivot_flags):
        if flag == 0:
            continue
        if flag == 1:
            out.append({
                "date": rows[i]["date"],
                "price": float(rows[i]["high"]),
                "kind": "peak",
                "bar_idx": i,
            })
        elif flag == -1:
            out.append({
                "date": rows[i]["date"],
                "price": float(rows[i]["low"]),
                "kind": "valley",
                "bar_idx": i,
            })
    return out


# ---------------------------------------------------------------------------
# Shared guards / helpers
# ---------------------------------------------------------------------------
def _prior_trend_pct(closes: np.ndarray, end_idx: int, lookback: int) -> float | None:
    """Net pct change of closes[end_idx - lookback : end_idx]. None if not enough bars."""
    start = end_idx - lookback
    if start < 0:
        return None
    head, tail = closes[start], closes[end_idx]
    if head == 0:
        return None
    return float((tail - head) / head * 100.0)


def _interp_neckline_at(start_bar: int, start_price: float,
                       end_bar: int, end_price: float, query_bar: int) -> float:
    """Linear interpolation of the neckline at `query_bar`."""
    if end_bar == start_bar:
        return start_price
    slope = (end_price - start_price) / (end_bar - start_bar)
    return start_price + slope * (query_bar - start_bar)


def _neckline_break(rows: list[dict],
                    nl_start_bar: int, nl_start_price: float,
                    nl_end_bar: int, nl_end_price: float,
                    after_bar: int,
                    bearish: bool) -> tuple[bool, str | None]:
    """First bar after `after_bar` where close crosses neckline in the breakout direction.

    For a bearish pattern (H&S, Double Top): close < neckline_at(bar).
    For a bullish pattern (Inverse H&S, Double Bottom): close > neckline_at(bar).
    """
    for i in range(after_bar + 1, len(rows)):
        nl = _interp_neckline_at(nl_start_bar, nl_start_price,
                                 nl_end_bar, nl_end_price, i)
        c = float(rows[i]["close"])
        if bearish and c < nl:
            return True, rows[i]["date"]
        if (not bearish) and c > nl:
            return True, rows[i]["date"]
    return False, None


def _grade(guards_passed: list[str], guards_failed: list[str],
          neckline_broken: bool) -> str:
    if not guards_failed:
        return "high" if neckline_broken else "medium"
    if len(guards_failed) == 1:
        return "low"
    return "low"  # >=2 will be filtered before emit


def _volume_ok(rows: list[dict], idx_to_compare: int, idx_reference_min: list[int]) -> bool | None:
    """True if vol[compare] < min(vol[refs]). None if volume missing/zero (skip guard)."""
    try:
        v_cmp = float(rows[idx_to_compare].get("volume") or 0.0)
        refs = [float(rows[i].get("volume") or 0.0) for i in idx_reference_min]
    except (TypeError, ValueError):
        return None
    if v_cmp <= 0 or any(v <= 0 for v in refs):
        return None
    return v_cmp < min(refs)


# ---------------------------------------------------------------------------
# Head & Shoulders (regular — bearish top)
# ---------------------------------------------------------------------------
def detect_head_and_shoulders(pivots: list[dict], rows: list[dict],
                              params: dict) -> list[dict]:
    """Slide a 5-pivot window: peak(LS), valley(LN), peak(H), valley(RN), peak(RS)."""
    return _detect_hs(pivots, rows, params, inverse=False)


def detect_inverse_head_and_shoulders(pivots: list[dict], rows: list[dict],
                                      params: dict) -> list[dict]:
    """Mirror: valley(LS), peak(LN), valley(H), peak(RN), valley(RS)."""
    return _detect_hs(pivots, rows, params, inverse=True)


def _detect_hs(pivots: list[dict], rows: list[dict], params: dict,
              *, inverse: bool) -> list[dict]:
    closes = np.array([r["close"] for r in rows], dtype=float)
    out: list[dict] = []

    primary = "valley" if inverse else "peak"
    secondary = "peak" if inverse else "valley"
    pattern_name = ("inverse_head_and_shoulders" if inverse
                    else "head_and_shoulders")

    for i in range(len(pivots) - 4):
        window = pivots[i:i + 5]
        kinds = [p["kind"] for p in window]
        expected = [primary, secondary, primary, secondary, primary]
        if kinds != expected:
            continue

        ls, ln, h, rn, rs = window

        guards_passed: list[str] = []
        guards_failed: list[str] = []

        # Head prominence
        if inverse:
            head_ok = h["price"] < min(ls["price"], rs["price"]) * (1 - params["head_prominence_pct"] / 100.0)
        else:
            head_ok = h["price"] > max(ls["price"], rs["price"]) * (1 + params["head_prominence_pct"] / 100.0)
        (guards_passed if head_ok else guards_failed).append("head_prominence")

        # Shoulder equality
        denom = max(ls["price"], rs["price"])
        if denom == 0:
            shoulder_ok = False
        else:
            shoulder_ok = abs(ls["price"] - rs["price"]) / denom <= params["shoulder_equality_pct"] / 100.0
        (guards_passed if shoulder_ok else guards_failed).append("shoulder_equality")

        # Spacing
        gaps = [window[k + 1]["bar_idx"] - window[k]["bar_idx"] for k in range(4)]
        spacing_ok = all(g >= params["min_bars_between_pivots"] for g in gaps)
        (guards_passed if spacing_ok else guards_failed).append("spacing")

        # Total span
        span = rs["bar_idx"] - ls["bar_idx"]
        span_ok = span <= params["max_pattern_bars"]
        (guards_passed if span_ok else guards_failed).append("total_span")

        # Prior trend
        prior = _prior_trend_pct(closes, ls["bar_idx"], params["prior_trend_lookback_bars"])
        if prior is None:
            trend_ok = False
        elif inverse:
            trend_ok = prior <= -params["prior_trend_min_pct"]
        else:
            trend_ok = prior >= params["prior_trend_min_pct"]
        (guards_passed if trend_ok else guards_failed).append("prior_trend")

        # Volume (skip if missing)
        if params.get("volume_check", True):
            v_check = _volume_ok(rows, rs["bar_idx"], [ls["bar_idx"], h["bar_idx"]])
            if v_check is None:
                guards_passed.append("volume_skipped")
            elif v_check:
                guards_passed.append("volume_declining")
            else:
                guards_failed.append("volume_declining")

        # Skip emission if ≥ 2 guards failed
        if len(guards_failed) >= 2:
            continue

        # Build neckline: line through left_neck → right_neck, extended to last bar
        nl_start_bar = ln["bar_idx"]
        nl_start_price = ln["price"]
        nl_end_bar = rn["bar_idx"]
        nl_end_price = rn["price"]
        # Extend to the last bar so renderer + breakout check use the same line
        last_bar = len(rows) - 1
        nl_extrapolated_price = _interp_neckline_at(
            nl_start_bar, nl_start_price, nl_end_bar, nl_end_price, last_bar
        )

        # Target = head height projected from neckline level at head bar
        nl_at_head = _interp_neckline_at(
            nl_start_bar, nl_start_price, nl_end_bar, nl_end_price, h["bar_idx"]
        )
        if inverse:
            target_price = nl_at_head + (nl_at_head - h["price"])
        else:
            target_price = nl_at_head - (h["price"] - nl_at_head)

        # Neckline broken?
        broken, break_date = _neckline_break(
            rows, nl_start_bar, nl_start_price, nl_end_bar, nl_end_price,
            after_bar=rs["bar_idx"], bearish=not inverse,
        )

        confidence = _grade(guards_passed, guards_failed, broken)

        out.append({
            "name": pattern_name,
            "pivots": [
                {"date": ls["date"], "price": ls["price"], "role": "left_shoulder", "bar_idx": ls["bar_idx"]},
                {"date": ln["date"], "price": ln["price"], "role": "left_neck",     "bar_idx": ln["bar_idx"]},
                {"date": h["date"],  "price": h["price"],  "role": "head",          "bar_idx": h["bar_idx"]},
                {"date": rn["date"], "price": rn["price"], "role": "right_neck",    "bar_idx": rn["bar_idx"]},
                {"date": rs["date"], "price": rs["price"], "role": "right_shoulder", "bar_idx": rs["bar_idx"]},
            ],
            "neckline": {
                "start_date": ln["date"],          "start_price": float(nl_start_price),
                "end_date":   rows[last_bar]["date"], "end_price": float(nl_extrapolated_price),
            },
            "target_price": float(round(target_price, 4)),
            "neckline_broken": broken,
            "break_date": break_date,
            "confidence": confidence,
            "guards_passed": guards_passed,
            "guards_failed": guards_failed,
        })

    return out


# ---------------------------------------------------------------------------
# Double Top / Double Bottom — 3-pivot window
# ---------------------------------------------------------------------------
def detect_double_top(pivots: list[dict], rows: list[dict],
                     params: dict) -> list[dict]:
    """Slide a 3-pivot window: peak(P1), valley(neck), peak(P2)."""
    return _detect_double(pivots, rows, params, inverse=False)


def detect_double_bottom(pivots: list[dict], rows: list[dict],
                        params: dict) -> list[dict]:
    """Mirror: valley(P1), peak(neck), valley(P2). Prior trend down."""
    return _detect_double(pivots, rows, params, inverse=True)


def _detect_double(pivots: list[dict], rows: list[dict], params: dict,
                  *, inverse: bool) -> list[dict]:
    closes = np.array([r["close"] for r in rows], dtype=float)
    out: list[dict] = []

    primary = "valley" if inverse else "peak"
    secondary = "peak" if inverse else "valley"
    pattern_name = "double_bottom" if inverse else "double_top"

    for i in range(len(pivots) - 2):
        window = pivots[i:i + 3]
        kinds = [p["kind"] for p in window]
        if kinds != [primary, secondary, primary]:
            continue

        p1, neck, p2 = window

        guards_passed: list[str] = []
        guards_failed: list[str] = []

        # Peak equality (3% by default)
        denom = max(p1["price"], p2["price"])
        if denom == 0:
            peak_ok = False
        else:
            peak_ok = abs(p1["price"] - p2["price"]) / denom <= params["peak_equality_pct"] / 100.0
        (guards_passed if peak_ok else guards_failed).append("peak_equality")

        # Spacing — both sides AND ceiling
        gap = p2["bar_idx"] - p1["bar_idx"]
        spacing_ok = (params["min_bars_between_pivots"] <= gap
                      <= params["max_pattern_bars"])
        (guards_passed if spacing_ok else guards_failed).append("spacing")

        # Prior trend
        prior = _prior_trend_pct(closes, p1["bar_idx"], params["prior_trend_lookback_bars"])
        if prior is None:
            trend_ok = False
        elif inverse:
            trend_ok = prior <= -params["prior_trend_min_pct"]
        else:
            trend_ok = prior >= params["prior_trend_min_pct"]
        (guards_passed if trend_ok else guards_failed).append("prior_trend")

        # Volume: vol[P2] < vol[P1]
        if params.get("volume_check", True):
            v_check = _volume_ok(rows, p2["bar_idx"], [p1["bar_idx"]])
            if v_check is None:
                guards_passed.append("volume_skipped")
            elif v_check:
                guards_passed.append("volume_declining")
            else:
                guards_failed.append("volume_declining")

        if len(guards_failed) >= 2:
            continue

        # Horizontal neckline = intervening pivot's price
        neckline_price = float(neck["price"])
        last_bar = len(rows) - 1

        # Target = mirror through the neckline
        if inverse:
            extreme = min(p1["price"], p2["price"])
            target_price = neckline_price + (neckline_price - extreme)
        else:
            extreme = max(p1["price"], p2["price"])
            target_price = neckline_price - (extreme - neckline_price)

        # Neckline break check (horizontal — both endpoints same price)
        broken, break_date = _neckline_break(
            rows, neck["bar_idx"], neckline_price,
            last_bar, neckline_price,
            after_bar=p2["bar_idx"], bearish=not inverse,
        )

        confidence = _grade(guards_passed, guards_failed, broken)

        out.append({
            "name": pattern_name,
            "pivots": [
                {"date": p1["date"],   "price": p1["price"],   "role": "first_peak" if not inverse else "first_trough",   "bar_idx": p1["bar_idx"]},
                {"date": neck["date"], "price": neck["price"], "role": "neckline_pivot",                                   "bar_idx": neck["bar_idx"]},
                {"date": p2["date"],   "price": p2["price"],   "role": "second_peak" if not inverse else "second_trough", "bar_idx": p2["bar_idx"]},
            ],
            "neckline": {
                "start_date": neck["date"], "start_price": neckline_price,
                "end_date":   rows[last_bar]["date"], "end_price": neckline_price,
            },
            "target_price": float(round(target_price, 4)),
            "neckline_broken": broken,
            "break_date": break_date,
            "confidence": confidence,
            "guards_passed": guards_passed,
            "guards_failed": guards_failed,
        })

    return out


# ---------------------------------------------------------------------------
# Public entry points
# ---------------------------------------------------------------------------
def process(ticker: str, in_dir: Path, params: dict | None = None) -> dict:
    """Read <ticker>-ohlcv.json, detect patterns, write <ticker>-patterns.json."""
    params = {**DEFAULTS, **(params or {})}
    in_dir = Path(in_dir)
    ohlcv = json.loads((in_dir / f"{ticker}-ohlcv.json").read_text())
    rows = ohlcv["data"]
    if len(rows) < 30:
        out = {"ticker": ticker, "timeframe": "daily",
               "as_of": rows[-1]["date"] if rows else None,
               "params": params, "patterns": [],
               "note": "insufficient_bars"}
        (in_dir / f"{ticker}-patterns.json").write_text(
            json.dumps(out, ensure_ascii=False, indent=2))
        return {"ticker": ticker, "status": "ok", "patterns_found": 0}

    pivots = extract_pivots(rows, params["pivot_threshold_pct"])
    patterns: list[dict] = []
    patterns += detect_head_and_shoulders(pivots, rows, params)
    patterns += detect_inverse_head_and_shoulders(pivots, rows, params)
    patterns += detect_double_top(pivots, rows, params)
    patterns += detect_double_bottom(pivots, rows, params)

    out = {
        "ticker": ticker,
        "timeframe": "daily",
        "as_of": rows[-1]["date"],
        "params": params,
        "patterns": patterns,
    }
    out_path = in_dir / f"{ticker}-patterns.json"
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2))
    return {"ticker": ticker, "status": "ok",
            "patterns_found": len(patterns), "path": str(out_path)}


def main():
    ap = argparse.ArgumentParser(description="Detect shape patterns from OHLCV")
    ap.add_argument("tickers", nargs="+")
    ap.add_argument("--in", dest="in_dir", required=True)
    args = ap.parse_args()

    in_dir = Path(args.in_dir).expanduser()
    results = []
    ok = 0
    for t in args.tickers:
        try:
            r = process(t, in_dir)
            results.append(r)
            ok += 1
            print(f"OK  {t}: patterns_found={r['patterns_found']}", file=sys.stderr)
        except Exception as e:
            results.append({"ticker": t, "status": "error", "error": str(e)})
            print(f"ERR {t}: {e}", file=sys.stderr)

    print(json.dumps({"total": len(args.tickers), "ok": ok,
                      "results": results}, ensure_ascii=False, indent=2))
    sys.exit(0 if ok > 0 else 1)


if __name__ == "__main__":
    main()
