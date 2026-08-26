#!/usr/bin/env python3
"""
Fetch USD/KRW exchange rate via yfinance ('KRW=X' ticker).

Usage:
  python currency.py [--pair USD_KRW] [--out <path>]

Output (stdout JSON + optional file):
  {"pair": "USD_KRW", "rate": 1380.25, "fetched_at": "..."}
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path


def fetch_rate(pair: str = "USD_KRW") -> float:
    import yfinance as yf

    base, quote = pair.split("_")
    # yfinance convention: KRW=X means USD→KRW
    if base == "USD" and quote == "KRW":
        t = yf.Ticker("KRW=X")
    elif base == "KRW" and quote == "USD":
        t = yf.Ticker("KRW=X")
        df = t.history(period="5d")
        if df.empty:
            raise RuntimeError("yfinance returned empty for KRW=X")
        return 1.0 / float(df["Close"].iloc[-1])
    else:
        t = yf.Ticker(f"{base}{quote}=X")

    df = t.history(period="5d")
    if df.empty:
        raise RuntimeError(f"yfinance returned empty for {pair}")
    return float(df["Close"].iloc[-1])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pair", default="USD_KRW")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    try:
        rate = fetch_rate(args.pair)
    except Exception as e:
        print(json.dumps({"status": "error", "error": str(e)}, ensure_ascii=False))
        sys.exit(1)

    payload = {
        "pair": args.pair,
        "rate": round(rate, 4),
        "fetched_at": datetime.now().isoformat(timespec="seconds"),
    }
    out = json.dumps(payload, ensure_ascii=False, indent=2)
    print(out)
    if args.out:
        Path(args.out).expanduser().write_text(out)


if __name__ == "__main__":
    main()
