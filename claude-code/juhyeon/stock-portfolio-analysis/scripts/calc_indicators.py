#!/usr/bin/env python3
"""
Compute technical indicators from OHLCV JSON files (daily or intraday).

Daily (default)
  Reads <in>/<ticker>-ohlcv.json, writes <out>/<ticker>-indicators.json.
  Indicators: RSI(14), MACD(12,26,9), SMA(20/50/200), EMA(12/26), Bollinger(20,2).
  Signals use SMA50/SMA200 labels.

Intraday (--timeframe intraday)
  Reads <in>/<ticker>-intraday.json, writes <out>/<ticker>-indicators-intraday.json.
  Indicators: RSI(14), MACD(12,26,9), SMA(20/60) only (no SMA50/200), EMA, Bollinger.
  Signals use SMA20/SMA60 labels.

Usage:
  python calc_indicators.py <ticker1> [<ticker2> ...] --in <dir> [--out <dir>]
                            [--timeframe daily|intraday]

Output schema:
  {
    "ticker": "005930.KS",
    "timeframe": "daily" | "intraday",
    "as_of": "2026-05-19" (daily) | "2026-05-20T14:30:00" (intraday),
    "close": 75200.0,
    "indicators": {
        "rsi14": 58.3,
        "rsi14_label": "neutral",      # overbought|bullish|neutral|bearish|oversold
        "macd": 142.3, "macd_signal": 110.1, "macd_hist": 32.2,
        "macd_label": "bullish_cross_3d_ago",   # daily: days, intraday: bars
        "sma20": ..., "sma50": ..., "sma200": ...,   # daily
        "sma20": ..., "sma60": ..., "sma50": null, "sma200": null,   # intraday
        "ema12": ..., "ema26": ...,
        "bb_mid": ..., "bb_upper": ..., "bb_lower": ...,
        "bb_position": 0.62             # 0=lower band, 1=upper band
    },
    "recent_5": [                       # last 5 bars of the active timeframe
        {"date": ..., "close": ..., "rsi14": ..., "macd_hist": ...},
        ...
    ],
    "signals": [...]                    # uses sma50/200 labels (daily) or sma20/60 (intraday)
  }
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def to_series(rows: list[dict], key: str) -> list[float]:
    return [float(r[key]) for r in rows]


def ema(values: list[float], period: int) -> list[float]:
    if not values:
        return []
    k = 2.0 / (period + 1)
    out = [values[0]]
    for v in values[1:]:
        out.append(v * k + out[-1] * (1 - k))
    return out


def sma(values: list[float], period: int) -> list[float | None]:
    out: list[float | None] = []
    cum = 0.0
    for i, v in enumerate(values):
        cum += v
        if i >= period:
            cum -= values[i - period]
        if i >= period - 1:
            out.append(cum / period)
        else:
            out.append(None)
    return out


def rsi(values: list[float], period: int = 14) -> list[float | None]:
    if len(values) < period + 1:
        return [None] * len(values)
    gains = [0.0]
    losses = [0.0]
    for i in range(1, len(values)):
        d = values[i] - values[i - 1]
        gains.append(max(d, 0))
        losses.append(max(-d, 0))
    # initial avg over first `period` values (Wilder)
    avg_g = sum(gains[1:period + 1]) / period
    avg_l = sum(losses[1:period + 1]) / period
    out: list[float | None] = [None] * period
    rs = avg_g / avg_l if avg_l > 0 else float("inf")
    out.append(100 - 100 / (1 + rs))
    for i in range(period + 1, len(values)):
        avg_g = (avg_g * (period - 1) + gains[i]) / period
        avg_l = (avg_l * (period - 1) + losses[i]) / period
        rs = avg_g / avg_l if avg_l > 0 else float("inf")
        out.append(100 - 100 / (1 + rs))
    return out


def macd(values: list[float], fast: int = 12, slow: int = 26, signal: int = 9):
    ef = ema(values, fast)
    es = ema(values, slow)
    line = [a - b for a, b in zip(ef, es)]
    sig = ema(line, signal)
    hist = [a - b for a, b in zip(line, sig)]
    return line, sig, hist


def bollinger(values: list[float], period: int = 20, k: float = 2.0):
    mid = sma(values, period)
    upper: list[float | None] = []
    lower: list[float | None] = []
    for i, m in enumerate(mid):
        if m is None or i < period - 1:
            upper.append(None)
            lower.append(None)
            continue
        window = values[i - period + 1: i + 1]
        avg = sum(window) / period
        var = sum((x - avg) ** 2 for x in window) / period
        sd = var ** 0.5
        upper.append(avg + k * sd)
        lower.append(avg - k * sd)
    return mid, upper, lower


def label_rsi(v: float | None) -> str:
    if v is None:
        return "n/a"
    if v >= 70:
        return "overbought"
    if v >= 55:
        return "bullish"
    if v >= 45:
        return "neutral"
    if v >= 30:
        return "bearish"
    return "oversold"


def label_macd(hist_tail: list[float]) -> str:
    """Detect recent bullish/bearish cross in last 5 bars."""
    if len(hist_tail) < 2:
        return "n/a"
    for i in range(len(hist_tail) - 1, 0, -1):
        prev = hist_tail[i - 1]
        cur = hist_tail[i]
        if prev <= 0 < cur:
            return f"bullish_cross_{len(hist_tail) - 1 - i}d_ago"
        if prev >= 0 > cur:
            return f"bearish_cross_{len(hist_tail) - 1 - i}d_ago"
    return "bullish_trend" if hist_tail[-1] > 0 else "bearish_trend"


def detect_signals(closes: list[float], rsi_v: list[float | None],
                   sma_mid: list[float | None], sma_long: list[float | None],
                   macd_hist: list[float],
                   mid_label: str = "sma50",
                   long_label: str = "sma200") -> list[str]:
    """Detect named signals from the indicator series.

    `mid_label`/`long_label` parameterize the emitted signal strings so that
    intraday output (SMA20/SMA60) is not mislabeled as SMA50/SMA200. Both
    cross detection and price-vs-MA strings use these labels verbatim.
    """
    sig = []
    if closes and sma_mid[-1] is not None:
        sig.append(f"price_above_{mid_label}" if closes[-1] > sma_mid[-1] else f"price_below_{mid_label}")
    if closes and sma_long[-1] is not None:
        sig.append(f"price_above_{long_label}" if closes[-1] > sma_long[-1] else f"price_below_{long_label}")
    if sma_mid[-1] is not None and sma_long[-1] is not None:
        sig.append("golden_cross" if sma_mid[-1] > sma_long[-1] else "death_cross")
    if rsi_v[-1] is not None:
        if rsi_v[-1] >= 70:
            sig.append("rsi_overbought")
        elif rsi_v[-1] <= 30:
            sig.append("rsi_oversold")
    # MACD cross detection (5 bars)
    label = label_macd(macd_hist[-5:])
    if label != "n/a":
        sig.append(f"macd_{label}")
    return sig


def process(ticker: str, in_dir: Path, out_dir: Path, timeframe: str = "daily") -> dict:
    """Compute indicators for `daily` or `intraday` timeframe.

    daily    : reads <ticker>-ohlcv.json,    writes <ticker>-indicators.json
               (SMA20/50/200 + RSI + MACD + Bollinger; existing behavior)
    intraday : reads <ticker>-intraday.json, writes <ticker>-indicators-intraday.json
               (SMA20/60 + RSI + MACD + Bollinger; skip SMA50/200)
    """
    if timeframe == "intraday":
        in_path = in_dir / f"{ticker}-intraday.json"
        out_path = out_dir / f"{ticker}-indicators-intraday.json"
    else:
        in_path = in_dir / f"{ticker}-ohlcv.json"
        out_path = out_dir / f"{ticker}-indicators.json"

    if not in_path.exists():
        raise FileNotFoundError(f"missing {in_path}")
    payload = json.loads(in_path.read_text())
    rows = payload.get("data", [])
    min_bars = 30 if timeframe == "daily" else 80
    if len(rows) < min_bars:
        raise ValueError(f"insufficient bars ({len(rows)}) for {ticker} {timeframe}; need >= {min_bars}")

    closes = to_series(rows, "close")
    rsi_v = rsi(closes, 14)
    macd_line, macd_sig, macd_hist = macd(closes)
    ema12 = ema(closes, 12)
    ema26 = ema(closes, 26)
    bb_mid, bb_up, bb_lo = bollinger(closes, 20, 2.0)
    sma20 = sma(closes, 20)

    if timeframe == "daily":
        sma50 = sma(closes, 50)
        sma200 = sma(closes, 200)
        sma_short = None  # not used in daily
    else:
        sma50 = [None] * len(closes)
        sma200 = [None] * len(closes)
        sma_short = sma(closes, 60)  # intraday medium MA

    last = -1
    last_close = closes[last]

    bb_pos = None
    if bb_up[last] is not None and bb_lo[last] is not None:
        rng = bb_up[last] - bb_lo[last]
        if rng > 0:
            bb_pos = (last_close - bb_lo[last]) / rng

    indicators = {
        "rsi14": round(rsi_v[last], 2) if rsi_v[last] is not None else None,
        "rsi14_label": label_rsi(rsi_v[last]),
        "macd": round(macd_line[last], 4),
        "macd_signal": round(macd_sig[last], 4),
        "macd_hist": round(macd_hist[last], 4),
        "macd_label": label_macd(macd_hist[-5:]),
        "sma20": round(sma20[last], 4) if sma20[last] is not None else None,
        "ema12": round(ema12[last], 4),
        "ema26": round(ema26[last], 4),
        "bb_mid": round(bb_mid[last], 4) if bb_mid[last] is not None else None,
        "bb_upper": round(bb_up[last], 4) if bb_up[last] is not None else None,
        "bb_lower": round(bb_lo[last], 4) if bb_lo[last] is not None else None,
        "bb_position": round(bb_pos, 3) if bb_pos is not None else None,
    }
    if timeframe == "daily":
        indicators["sma50"] = round(sma50[last], 4) if sma50[last] is not None else None
        indicators["sma200"] = round(sma200[last], 4) if sma200[last] is not None else None
    else:
        indicators["sma50"] = None
        indicators["sma200"] = None
        indicators["sma60"] = round(sma_short[last], 4) if sma_short[last] is not None else None

    recent_5 = []
    for i in range(max(0, len(rows) - 5), len(rows)):
        recent_5.append({
            "date": rows[i]["date"],
            "close": rows[i]["close"],
            "rsi14": round(rsi_v[i], 2) if rsi_v[i] is not None else None,
            "macd_hist": round(macd_hist[i], 4),
        })

    # Signal detection: pick the right MA pair + labels for the timeframe
    if timeframe == "daily":
        signals = detect_signals(closes, rsi_v, sma50, sma200, macd_hist,
                                 mid_label="sma50", long_label="sma200")
    else:
        signals = detect_signals(closes, rsi_v, sma20, sma_short, macd_hist,
                                 mid_label="sma20", long_label="sma60")

    out = {
        "ticker": ticker,
        "timeframe": timeframe,
        "as_of": rows[last]["date"],
        "close": last_close,
        "currency": payload.get("currency"),
        "market": payload.get("market"),
        "indicators": indicators,
        "recent_5": recent_5,
        "signals": signals,
        "bars_used": len(rows),
    }

    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2))
    return {"ticker": ticker, "status": "ok", "path": str(out_path),
            "as_of": out["as_of"], "timeframe": timeframe}


def main():
    ap = argparse.ArgumentParser(description="Compute technical indicators")
    ap.add_argument("tickers", nargs="+")
    ap.add_argument("--in", dest="in_dir", required=True)
    ap.add_argument("--out", dest="out_dir", default=None)
    ap.add_argument("--timeframe", choices=["daily", "intraday"], default="daily")
    args = ap.parse_args()

    in_dir = Path(args.in_dir).expanduser()
    out_dir = Path(args.out_dir).expanduser() if args.out_dir else in_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    results = []
    ok = 0
    for t in args.tickers:
        try:
            r = process(t, in_dir, out_dir, timeframe=args.timeframe)
            results.append(r)
            ok += 1
            print(f"OK  {t} [{args.timeframe}]: as_of={r['as_of']}", file=sys.stderr)
        except Exception as e:
            results.append({"ticker": t, "status": "error", "error": str(e),
                            "timeframe": args.timeframe})
            print(f"ERR {t} [{args.timeframe}]: {e}", file=sys.stderr)

    print(json.dumps({"total": len(args.tickers), "ok": ok, "results": results,
                      "timeframe": args.timeframe}, ensure_ascii=False, indent=2))
    sys.exit(0 if ok > 0 else 1)


if __name__ == "__main__":
    main()
