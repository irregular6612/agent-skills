#!/usr/bin/env python3
"""
Fetch intraday OHLCV (15-minute default) for KRX + US tickers via yfinance.

yfinance limits:
  - 1m  : last 7 days
  - 5m  : last 60 days
  - 15m : last 60 days   (default)
  - 30m : last 60 days
  - 60m : last 730 days

Usage:
  python fetch_intraday.py <ticker1> [...] --out <dir> [--interval 15m] [--days 30]

Output: <out>/<ticker>-intraday.json
  {
    "ticker": "005930.KS", "market": "KRX", "interval": "15m",
    "currency": "KRW", "fetched_at": "...",
    "data": [{"date": "2026-05-20T14:30:00", ...}, ...]
  }
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import traceback
from datetime import date, datetime
from pathlib import Path

KRX_CODE = re.compile(r"^\d{6}(\.(KS|KQ))?$")


def classify(ticker: str) -> tuple[str, str, str]:
    """Return (market, canonical_ticker, currency). Mirrors fetch_ohlcv.classify."""
    t = ticker.strip().upper()
    if KRX_CODE.match(t):
        code = t.split(".")[0]
        suffix = t.split(".")[1] if "." in t else None
        market = "KOSDAQ" if suffix == "KQ" else "KOSPI" if suffix == "KS" else "KRX"
        return market, f"{code}.{suffix or 'KS'}", "KRW"
    return "US", t, "USD"


def fetch_yfinance_intraday(ticker: str, interval: str, days: int) -> list[dict]:
    """Fetch intraday OHLCV. yfinance interval values: 1m,2m,5m,15m,30m,60m,90m."""
    import yfinance as yf

    period_map = {1: "7d", 5: "60d", 7: "7d", 30: "60d", 60: "60d"}
    period = period_map.get(days, "60d")
    df = yf.Ticker(ticker).history(interval=interval, period=period, auto_adjust=False)
    if df is None or df.empty:
        raise RuntimeError(f"yfinance returned empty intraday for {ticker} {interval}")
    # yfinance returns more than `days` worth — trim to last N trading days roughly
    # 15m × ~26 bars per day for US, slightly fewer for KRX. Approximate: keep last days*30 bars.
    df = df.tail(days * 30)
    out = []
    for idx, row in df.iterrows():
        out.append({
            "date": idx.strftime("%Y-%m-%dT%H:%M:%S"),
            "open": float(row["Open"]),
            "high": float(row["High"]),
            "low": float(row["Low"]),
            "close": float(row["Close"]),
            "volume": float(row["Volume"]),
        })
    return out


def fetch_one(ticker: str, out_dir: Path, interval: str, days: int, force: bool) -> dict:
    market, canon, currency = classify(ticker)
    out_path = out_dir / f"{canon}-intraday.json"

    if out_path.exists() and not force:
        try:
            existing = json.loads(out_path.read_text())
            fetched = existing.get("fetched_at", "")
            same_day = fetched.startswith(date.today().isoformat())
            same_interval = existing.get("interval") == interval
            same_days = existing.get("days_requested") == days
            if same_day and same_interval and same_days:
                return {"ticker": canon, "status": "cached",
                        "rows": len(existing.get("data", []))}
        except Exception:
            pass

    rows = fetch_yfinance_intraday(canon, interval, days)
    payload = {
        "ticker": canon,
        "market": market,
        "interval": interval,
        "currency": currency,
        "fetched_at": datetime.now().isoformat(timespec="seconds"),
        "days_requested": days,
        "data": rows,
    }
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2))
    return {"ticker": canon, "status": "fetched", "rows": len(rows), "path": str(out_path)}


def main():
    ap = argparse.ArgumentParser(description="Fetch intraday OHLCV via yfinance")
    ap.add_argument("tickers", nargs="+")
    ap.add_argument("--out", required=True)
    ap.add_argument("--interval", default="15m", choices=["1m", "5m", "15m", "30m", "60m", "90m"])
    ap.add_argument("--days", type=int, default=30)
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    out_dir = Path(args.out).expanduser()
    out_dir.mkdir(parents=True, exist_ok=True)

    results = []
    ok = 0
    for t in args.tickers:
        try:
            r = fetch_one(t, out_dir, args.interval, args.days, args.force)
            results.append(r)
            ok += 1
            print(f"OK  {r['ticker']}: {r['status']} ({r.get('rows','?')} rows)", file=sys.stderr)
        except Exception as e:
            results.append({"ticker": t, "status": "error", "error": str(e)})
            print(f"ERR {t}: {e}", file=sys.stderr)
            if os.environ.get("DEBUG"):
                traceback.print_exc()

    print(json.dumps({"total": len(args.tickers), "ok": ok, "interval": args.interval,
                      "results": results}, ensure_ascii=False, indent=2))
    sys.exit(0 if ok > 0 else 1)


if __name__ == "__main__":
    main()
