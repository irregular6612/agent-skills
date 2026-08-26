#!/usr/bin/env python3
"""
Render candlestick charts (daily + intraday) for each ticker.

Reads:
  <data>/<ticker>-ohlcv.json     (daily)
  <data>/<ticker>-intraday.json  (15m)
  <data>/<ticker>-indicators.json
  <data>/<ticker>-indicators-intraday.json

Produces:
  <out>/<ticker>-daily.png        (candle + SMA20/50/200 + volume + cross markers)
  <out>/<ticker>-intraday.png     (candle + SMA20/60 + volume + cross markers)

Usage:
  python render_chart.py <ticker1> [...] --data <session>/data --out <session>/charts
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

_MACD_CROSS_RE = re.compile(r"macd_(bullish|bearish)_cross_(\d+)d_ago")


def _macd_event_marker(signal: str, bars: list[dict]) -> dict | None:
    """Parse a `macd_{bull|bear}ish_cross_{N}d_ago` signal into an event marker.

    Returns a marker placed at the actual cross bar (N bars before the last bar),
    not at as_of. Returns None if the signal doesn't match this pattern.
    """
    m = _MACD_CROSS_RE.match(signal)
    if not m or not bars:
        return None
    direction = m.group(1)
    n = int(m.group(2))
    idx = max(0, len(bars) - 1 - n)
    return {"date": bars[idx]["date"],
            "kind": "bull" if direction == "bullish" else "bear"}


def _load_df(path: Path):
    """Load OHLCV JSON into a pandas DataFrame indexed by datetime."""
    import pandas as pd
    rows = json.loads(path.read_text()).get("data", [])
    if not rows:
        raise ValueError(f"empty data in {path}")
    df = pd.DataFrame(rows)
    df["Date"] = pd.to_datetime(df["date"])
    df = df.set_index("Date")
    df = df.rename(columns={"open": "Open", "high": "High", "low": "Low",
                            "close": "Close", "volume": "Volume"})
    return df[["Open", "High", "Low", "Close", "Volume"]]


def _render(df, sma_periods: list[int], title: str, out_path: Path,
            cross_markers: list[dict] | None = None,
            patterns: list[dict] | None = None):
    import mplfinance as mpf
    import pandas as pd

    addplots = []
    colors = ["#1f77b4", "#ff7f0e", "#d62728"]   # blue, orange, red
    for i, p in enumerate(sma_periods):
        if len(df) >= p:
            sma_series = df["Close"].rolling(window=p).mean()
            addplots.append(mpf.make_addplot(sma_series, color=colors[i % len(colors)],
                                              width=1.0, label=f"SMA{p}"))

    # Cross markers (golden/death/macd) overlaid as scatter on the candle plot
    if cross_markers:
        for m in cross_markers:
            marker_series = pd.Series([float("nan")] * len(df), index=df.index)
            try:
                idx = df.index.get_indexer([pd.Timestamp(m["date"])], method="nearest")[0]
                marker_series.iloc[idx] = df["Close"].iloc[idx]
                addplots.append(mpf.make_addplot(
                    marker_series, type="scatter", markersize=80,
                    marker="^" if m["kind"].startswith("bull") else "v",
                    color="green" if m["kind"].startswith("bull") else "red",
                ))
            except Exception:
                pass  # skip markers that don't align

    # Pattern overlays (H&S / Double Top/Bottom) — necklines + pivot markers + targets
    alines: list[list[tuple]] = []
    aline_colors: list[str] = []
    aline_widths: list[float] = []
    hline_targets: list[float] = []
    hline_colors: list[str] = []
    if patterns:
        bearish_color = "#d62728"   # red — H&S, Double Top
        bullish_color = "#2ca02c"   # green — Inverse H&S, Double Bottom
        for pat in patterns:
            is_bullish = pat["name"] in ("inverse_head_and_shoulders", "double_bottom")
            color = bullish_color if is_bullish else bearish_color
            nl = pat.get("neckline") or {}
            try:
                alines.append([
                    (pd.Timestamp(nl["start_date"]), float(nl["start_price"])),
                    (pd.Timestamp(nl["end_date"]),   float(nl["end_price"])),
                ])
                aline_colors.append(color)
                aline_widths.append(1.4)
            except (KeyError, TypeError, ValueError):
                pass

            # Shoulder-to-shoulder polyline for H&S — connects all 5 pivots
            if "head_and_shoulders" in pat["name"]:
                try:
                    poly = [(pd.Timestamp(piv["date"]), float(piv["price"]))
                            for piv in pat.get("pivots", [])]
                    if len(poly) >= 2:
                        alines.append(poly)
                        aline_colors.append(color)
                        aline_widths.append(0.9)
                except (KeyError, TypeError, ValueError):
                    pass

            # Pivot markers — one scatter series per pattern (NaN-padded)
            marker_series = pd.Series([float("nan")] * len(df), index=df.index)
            for piv in pat.get("pivots", []):
                try:
                    pidx = df.index.get_indexer(
                        [pd.Timestamp(piv["date"])], method="nearest"
                    )[0]
                    marker_series.iloc[pidx] = float(piv["price"])
                except Exception:
                    continue
            if marker_series.notna().any():
                addplots.append(mpf.make_addplot(
                    marker_series, type="scatter", markersize=110,
                    marker="o", color=color,
                ))

            # Target line
            t = pat.get("target_price")
            if t is not None:
                try:
                    hline_targets.append(float(t))
                    hline_colors.append(color)
                except (TypeError, ValueError):
                    pass

    plot_kwargs = dict(
        type="candle", style="yahoo", volume=True,
        addplot=addplots if addplots else None,
        title=title,
        warn_too_much_data=10_000,
        savefig=dict(fname=str(out_path), dpi=100, bbox_inches="tight"),
        figratio=(12, 8), figscale=1.0,
    )
    if alines:
        plot_kwargs["alines"] = dict(alines=alines, colors=aline_colors,
                                     linewidths=aline_widths, alpha=0.85)
    if hline_targets:
        plot_kwargs["hlines"] = dict(hlines=hline_targets, colors=hline_colors,
                                     linestyle="--", linewidths=1.0)

    mpf.plot(df, **plot_kwargs)


def _collect_event_markers(ind: dict, bars: list[dict]) -> list[dict]:
    """Build event markers from indicator signals.

    Stateful regime labels (`golden_cross`/`death_cross`) intentionally produce
    NO marker — the SMA overlay lines already show the regime visually, and
    stamping a "today" marker for a months-old cross is misleading.

    Only true event signals (MACD cross with `_Nd_ago` suffix) generate markers,
    placed at the actual cross bar.
    """
    markers = []
    for s in ind.get("signals", []):
        m = _macd_event_marker(s, bars)
        if m:
            markers.append(m)
    return markers


def _read_bars(data_path: Path) -> list[dict]:
    return json.loads(data_path.read_text()).get("data", [])


_CONFIDENCE_RANK = {"low": 0, "medium": 1, "high": 2}


def _load_patterns(data_dir: Path, ticker: str,
                  min_confidence: str = "medium") -> list[dict]:
    """Read <ticker>-patterns.json and keep patterns with confidence >= min_confidence.

    Real-data runs frequently emit double-digit low-confidence candidates that
    each draw a neckline + 5 pivot markers, drowning the chart in noise. The
    JSON file keeps everything for the chart-agent to verify; the PNG renders
    only patterns the algorithm itself believes are real (medium+ by default).
    """
    p = data_dir / f"{ticker}-patterns.json"
    if not p.exists():
        return []
    try:
        patterns = json.loads(p.read_text()).get("patterns", []) or []
    except (json.JSONDecodeError, OSError):
        return []
    threshold = _CONFIDENCE_RANK.get(min_confidence, 1)
    return [p for p in patterns
            if _CONFIDENCE_RANK.get(p.get("confidence", "low"), 0) >= threshold]


def render_daily(ticker: str, data_dir: Path, out_dir: Path) -> Path:
    df = _load_df(data_dir / f"{ticker}-ohlcv.json")
    cross_markers = []
    ind_path = data_dir / f"{ticker}-indicators.json"
    if ind_path.exists():
        ind = json.loads(ind_path.read_text())
        bars = _read_bars(data_dir / f"{ticker}-ohlcv.json")
        cross_markers = _collect_event_markers(ind, bars)
    out_path = out_dir / f"{ticker}-daily.png"
    _render(df, [20, 50, 200], f"{ticker} daily as of {df.index[-1].date()}",
            out_path, cross_markers=cross_markers)
    return out_path


def render_daily_annotated(ticker: str, data_dir: Path, out_dir: Path,
                          min_confidence: str = "medium") -> Path | None:
    """Emit <ticker>-daily-annotated.png if any pattern at >= min_confidence exists.

    Default `medium` filter keeps the chart readable; pass `low` to include
    every algorithm candidate (useful only for debugging false-positive guards).
    """
    patterns = _load_patterns(data_dir, ticker, min_confidence=min_confidence)
    if not patterns:
        return None
    df = _load_df(data_dir / f"{ticker}-ohlcv.json")
    cross_markers = []
    ind_path = data_dir / f"{ticker}-indicators.json"
    if ind_path.exists():
        ind = json.loads(ind_path.read_text())
        bars = _read_bars(data_dir / f"{ticker}-ohlcv.json")
        cross_markers = _collect_event_markers(ind, bars)
    out_path = out_dir / f"{ticker}-daily-annotated.png"
    _render(df, [20, 50, 200],
            f"{ticker} daily (annotated) as of {df.index[-1].date()}",
            out_path, cross_markers=cross_markers, patterns=patterns)
    return out_path


def render_intraday(ticker: str, data_dir: Path, out_dir: Path) -> Path:
    df = _load_df(data_dir / f"{ticker}-intraday.json")
    cross_markers = []
    ind_path = data_dir / f"{ticker}-indicators-intraday.json"
    if ind_path.exists():
        ind = json.loads(ind_path.read_text())
        bars = _read_bars(data_dir / f"{ticker}-intraday.json")
        cross_markers = _collect_event_markers(ind, bars)
    out_path = out_dir / f"{ticker}-intraday.png"
    _render(df, [20, 60], f"{ticker} 15m as of {df.index[-1].strftime('%Y-%m-%d %H:%M')}",
            out_path, cross_markers=cross_markers)
    return out_path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("tickers", nargs="+")
    ap.add_argument("--data", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--annotated", dest="annotated", action="store_true", default=True,
                    help="Emit <ticker>-daily-annotated.png when patterns exist (default)")
    ap.add_argument("--no-annotated", dest="annotated", action="store_false",
                    help="Skip the annotated daily PNG even if patterns exist")
    ap.add_argument("--annotated-min-confidence", choices=["low", "medium", "high"],
                    default="medium",
                    help="Minimum confidence to draw on annotated PNG (default: medium)")
    args = ap.parse_args()

    data_dir = Path(args.data).expanduser()
    out_dir = Path(args.out).expanduser()
    out_dir.mkdir(parents=True, exist_ok=True)

    results = []
    ok = 0
    for t in args.tickers:
        per = {"ticker": t}
        try:
            p = render_daily(t, data_dir, out_dir)
            per["daily"] = str(p)
        except Exception as e:
            per["daily_error"] = str(e)
        try:
            p = render_intraday(t, data_dir, out_dir)
            per["intraday"] = str(p)
        except Exception as e:
            per["intraday_error"] = str(e)
        if args.annotated:
            try:
                p = render_daily_annotated(
                    t, data_dir, out_dir,
                    min_confidence=args.annotated_min_confidence,
                )
                if p is None:
                    print(f"{t}: no medium+ patterns — skipped annotated PNG",
                          file=sys.stderr)
                else:
                    per["daily_annotated"] = str(p)
            except Exception as e:
                per["daily_annotated_error"] = str(e)
        if "daily" in per or "intraday" in per:
            ok += 1
        results.append(per)
        print(f"{t}: daily={'ok' if 'daily' in per else 'fail'} "
              f"intraday={'ok' if 'intraday' in per else 'fail'} "
              f"annotated={'ok' if 'daily_annotated' in per else 'skip'}",
              file=sys.stderr)

    print(json.dumps({"total": len(args.tickers), "ok": ok, "results": results},
                     ensure_ascii=False, indent=2))
    sys.exit(0 if ok > 0 else 1)


if __name__ == "__main__":
    main()
