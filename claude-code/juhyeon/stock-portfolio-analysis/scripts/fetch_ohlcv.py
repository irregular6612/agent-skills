#!/usr/bin/env python3
"""
Fetch OHLCV (Open/High/Low/Close/Volume) for KRX (KOSPI/KOSDAQ) + US tickers.

Usage:
  python fetch_ohlcv.py <ticker1> [<ticker2> ...] --out <dir> [--days 250]

KRX tickers are recognized by 6-digit code or `.KS`/`.KQ` suffix.
US tickers are everything else (NVDA, AAPL, SPY, ...).

Output: JSON file per ticker at <out>/<ticker>-ohlcv.json with structure:
  {
    "ticker": "005930.KS",
    "market": "KRX",
    "fetched_at": "2026-05-20T14:30:05",
    "currency": "KRW",
    "data": [
      {"date": "2025-09-22", "open": ..., "high": ..., "low": ..., "close": ..., "volume": ...},
      ...
    ]
  }

Cache: if a same-day file exists at <out>/<ticker>-ohlcv.json, skip refetch.
Failures: log to stderr, continue with other tickers, exit 0 unless ALL fail.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import traceback
from datetime import date, datetime, timedelta
from pathlib import Path

KRX_CODE = re.compile(r"^\d{6}(\.(KS|KQ))?$")


def classify(ticker: str) -> tuple[str, str, str]:
    """Return (market, canonical_ticker, currency)."""
    t = ticker.strip().upper()
    if KRX_CODE.match(t):
        code = t.split(".")[0]
        suffix = t.split(".")[1] if "." in t else None
        # KOSPI default; KOSDAQ if .KQ explicit
        market = "KOSDAQ" if suffix == "KQ" else "KOSPI" if suffix == "KS" else "KRX"
        return "KRX", f"{code}.{suffix or 'KS'}", "KRW"
    return "US", t, "USD"


def fetch_yfinance(ticker: str, days: int) -> list[dict]:
    """Fetch OHLCV via yfinance. Works for both KRX (.KS/.KQ suffix) and US tickers."""
    import yfinance as yf

    # period mapping: 250 days ~ 1y, 500 ~ 2y
    period = "2y" if days > 250 else "1y"
    df = yf.Ticker(ticker).history(period=period, auto_adjust=False)
    if df is None or df.empty:
        raise RuntimeError(f"yfinance returned empty for {ticker}")
    df = df.tail(days)
    out = []
    for idx, row in df.iterrows():
        out.append({
            "date": idx.strftime("%Y-%m-%d"),
            "open": float(row["Open"]),
            "high": float(row["High"]),
            "low": float(row["Low"]),
            "close": float(row["Close"]),
            "volume": float(row["Volume"]),
        })
    return out


def fetch_one(ticker: str, out_dir: Path, days: int, force: bool) -> dict:
    market, canon, currency = classify(ticker)
    out_path = out_dir / f"{canon}-ohlcv.json"

    if out_path.exists() and not force:
        # cache hit: only reuse if same calendar day
        try:
            existing = json.loads(out_path.read_text())
            fetched = existing.get("fetched_at", "")
            if fetched.startswith(date.today().isoformat()):
                return {"ticker": canon, "status": "cached", "rows": len(existing.get("data", []))}
        except Exception:
            pass  # re-fetch

    # yfinance handles both KRX (.KS / .KQ) and US tickers uniformly
    rows = fetch_yfinance(canon, days)

    payload = {
        "ticker": canon,
        "market": market,
        "currency": currency,
        "fetched_at": datetime.now().isoformat(timespec="seconds"),
        "days_requested": days,
        "data": rows,
    }
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2))
    return {"ticker": canon, "status": "fetched", "rows": len(rows), "path": str(out_path)}


def main():
    ap = argparse.ArgumentParser(description="Fetch OHLCV for KRX + US tickers")
    ap.add_argument("tickers", nargs="+", help="ticker symbols (e.g. 005930.KS NVDA AAPL)")
    ap.add_argument("--out", required=True, help="output directory")
    ap.add_argument("--days", type=int, default=250, help="trading days to fetch (default 250)")
    ap.add_argument("--force", action="store_true", help="ignore same-day cache")
    args = ap.parse_args()

    out_dir = Path(args.out).expanduser()
    out_dir.mkdir(parents=True, exist_ok=True)

    results = []
    successes = 0
    for t in args.tickers:
        try:
            res = fetch_one(t, out_dir, args.days, args.force)
            results.append(res)
            successes += 1
            print(f"OK  {res['ticker']}: {res['status']} ({res['rows']} rows)", file=sys.stderr)
        except Exception as e:
            results.append({"ticker": t, "status": "error", "error": str(e)})
            print(f"ERR {t}: {e}", file=sys.stderr)
            if os.environ.get("DEBUG"):
                traceback.print_exc()

    summary = {
        "total": len(args.tickers),
        "ok": successes,
        "failed": len(args.tickers) - successes,
        "results": results,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))

    if successes == 0:
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
