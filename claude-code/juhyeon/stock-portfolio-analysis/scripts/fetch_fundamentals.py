#!/usr/bin/env python3
"""
Fetch fundamentals (P/E, EPS, growth, ROE) for KRX + US tickers via yfinance.

For US tickers, optionally enriches with SEC EDGAR companyfacts (more authoritative
revenue/net income, multi-year YoY growth).

Usage:
  python fetch_fundamentals.py <ticker1> [...] --out <dir>

Output: <out>/<ticker>-fundamentals.json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.request
from datetime import datetime
from pathlib import Path

KRX_CODE = re.compile(r"^\d{6}(\.(KS|KQ))?$")

EDGAR_HEADERS = {"User-Agent": "portfolio-analysis-skill irregular6612@gmail.com"}


def is_krx(t: str) -> bool:
    return bool(KRX_CODE.match(t.upper()))


def fetch_yf_info(ticker: str) -> dict:
    """Pull fundamentals via yfinance .info. Works for KRX (.KS/.KQ) and US."""
    import yfinance as yf

    t = yf.Ticker(ticker)
    info = t.info or {}
    if not info or len(info) < 3:
        raise RuntimeError(f"yfinance .info empty for {ticker}")

    # yfinance field conventions (as of yfinance 0.2.x, 2025+):
    #   dividendYield → already in PERCENT form (0.5 = 0.5%)
    #   revenueGrowth, earningsGrowth → DECIMAL form (0.5 = 50%, 4.5 = 450%)
    #   returnOnEquity, operatingMargins, profitMargins, payoutRatio → DECIMAL form
    def dec_to_pct(v):
        """Decimal multiplier → percent (0.5 → 50.0). None-safe."""
        if v is None:
            return None
        try:
            return round(float(v) * 100, 4)
        except (TypeError, ValueError):
            return None

    def passthrough_pct(v):
        """Already in percent form. None-safe + rounded."""
        if v is None:
            return None
        try:
            return round(float(v), 4)
        except (TypeError, ValueError):
            return None

    return {
        "long_name": info.get("longName") or info.get("shortName"),
        "sector": info.get("sector"),
        "industry": info.get("industry"),
        "currency": info.get("currency"),
        "market_cap": info.get("marketCap"),
        "trailing_pe": info.get("trailingPE"),
        "forward_pe": info.get("forwardPE"),
        "price_to_book": info.get("priceToBook"),
        "trailing_eps": info.get("trailingEps"),
        "forward_eps": info.get("forwardEps"),
        "peg_ratio": info.get("pegRatio") or info.get("trailingPegRatio"),
        "dividend_yield_pct": passthrough_pct(info.get("dividendYield")),
        "payout_ratio": info.get("payoutRatio"),
        "revenue_growth_yoy_pct": dec_to_pct(info.get("revenueGrowth")),
        "earnings_growth_yoy_pct": dec_to_pct(info.get("earningsGrowth")),
        "roe_pct": dec_to_pct(info.get("returnOnEquity")),
        "debt_to_equity": info.get("debtToEquity"),
        "current_ratio": info.get("currentRatio"),
        "operating_margin_pct": dec_to_pct(info.get("operatingMargins")),
        "profit_margin_pct": dec_to_pct(info.get("profitMargins")),
        "beta": info.get("beta"),
        "52w_high": info.get("fiftyTwoWeekHigh"),
        "52w_low": info.get("fiftyTwoWeekLow"),
        "recommendation_key": info.get("recommendationKey"),
        "target_mean_price": info.get("targetMeanPrice"),
    }


def http_get_json(url: str) -> dict:
    req = urllib.request.Request(url, headers=EDGAR_HEADERS)
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode("utf-8"))


def get_cik(ticker: str) -> str | None:
    """Resolve US ticker → CIK via EDGAR ticker map."""
    try:
        data = http_get_json("https://www.sec.gov/files/company_tickers.json")
    except Exception:
        return None
    for _, entry in data.items():
        if entry.get("ticker", "").upper() == ticker.upper():
            return str(entry["cik_str"]).zfill(10)
    return None


def latest_annual(facts: dict, concept: str, unit_priority: list[str]) -> tuple[float | None, str | None]:
    g = facts.get("facts", {}).get("us-gaap", {}).get(concept)
    if not g:
        return None, None
    units = g.get("units", {})
    for u in unit_priority:
        if u in units:
            entries = [e for e in units[u] if e.get("form") == "10-K" and e.get("fp") == "FY"]
            entries.sort(key=lambda x: x.get("end", ""), reverse=True)
            if entries:
                return float(entries[0]["val"]), entries[0].get("end")
    return None, None


def yoy_growth_annual(facts: dict, concept: str, unit_priority: list[str]) -> float | None:
    g = facts.get("facts", {}).get("us-gaap", {}).get(concept)
    if not g:
        return None
    units = g.get("units", {})
    for u in unit_priority:
        if u in units:
            entries = [e for e in units[u] if e.get("form") == "10-K" and e.get("fp") == "FY"]
            entries.sort(key=lambda x: x.get("end", ""), reverse=True)
            if len(entries) >= 2 and entries[1]["val"]:
                return round((entries[0]["val"] - entries[1]["val"]) / abs(entries[1]["val"]) * 100, 2)
    return None


def enrich_us_with_edgar(ticker: str) -> dict:
    """Optional enrichment: pull SEC-filed numbers for higher trust. Returns {} on failure."""
    cik = get_cik(ticker)
    if not cik:
        return {}
    try:
        facts = http_get_json(f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json")
    except Exception:
        return {}

    revenue, rev_end = latest_annual(facts, "Revenues", ["USD"])
    if revenue is None:
        revenue, rev_end = latest_annual(facts, "RevenueFromContractWithCustomerExcludingAssessedTax", ["USD"])
    net_income, ni_end = latest_annual(facts, "NetIncomeLoss", ["USD"])
    eps_diluted, eps_end = latest_annual(facts, "EarningsPerShareDiluted", ["USD/shares"])

    revenue_growth = yoy_growth_annual(facts, "Revenues", ["USD"]) or \
                     yoy_growth_annual(facts, "RevenueFromContractWithCustomerExcludingAssessedTax", ["USD"])

    return {
        "edgar_cik": cik,
        "edgar_revenue_usd": revenue,
        "edgar_revenue_period_end": rev_end,
        "edgar_net_income_usd": net_income,
        "edgar_net_income_period_end": ni_end,
        "edgar_eps_diluted": eps_diluted,
        "edgar_eps_period_end": eps_end,
        "edgar_revenue_growth_yoy_pct_annual": revenue_growth,
    }


def fetch_one(ticker: str, out_dir: Path) -> dict:
    t = ticker.upper()
    is_krx_t = is_krx(t)
    canon = t
    if is_krx_t and "." not in t:
        canon = f"{t}.KS"  # default to KOSPI suffix

    base = fetch_yf_info(canon)
    base["ticker"] = canon
    base["market"] = "KRX" if is_krx_t else "US"
    base["fetched_at"] = datetime.now().isoformat(timespec="seconds")

    # Optional EDGAR enrichment for US tickers
    if not is_krx_t:
        enrichment = enrich_us_with_edgar(canon)
        base.update(enrichment)

    out_path = out_dir / f"{canon}-fundamentals.json"
    out_path.write_text(json.dumps(base, ensure_ascii=False, indent=2))
    return {"ticker": canon, "status": "ok", "path": str(out_path)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("tickers", nargs="+")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    out_dir = Path(args.out).expanduser()
    out_dir.mkdir(parents=True, exist_ok=True)

    results = []
    ok = 0
    for t in args.tickers:
        try:
            r = fetch_one(t, out_dir)
            results.append(r)
            ok += 1
            print(f"OK  {r['ticker']}", file=sys.stderr)
        except Exception as e:
            results.append({"ticker": t, "status": "error", "error": str(e)})
            print(f"ERR {t}: {e}", file=sys.stderr)

    print(json.dumps({"total": len(args.tickers), "ok": ok, "results": results},
                     ensure_ascii=False, indent=2))
    sys.exit(0 if ok > 0 else 1)


if __name__ == "__main__":
    main()
