#!/usr/bin/env python3
"""
Compose the final portfolio analysis report from 3 channel agent outputs.

Input: a session directory containing
  data/
    <ticker>-ohlcv.json
    <ticker>-indicators.json
    <ticker>-fundamentals.json
  agents/
    <ticker>-news.json        # output of news subagent
    <ticker>-fundamentals.json # NOTE: agent output is at agents/<ticker>-funda-agent.json
    <ticker>-chart.json
  holdings.yml                 # user's portfolio
  exchange_rate.json           # USD_KRW rate

Each agent output JSON schema:
  {
    "ticker": "...",
    "channel": "news" | "fundamentals" | "chart",
    "direction": "bull" | "bear" | "neutral",
    "strength": "strong" | "medium" | "weak",
    "reasoning_kr": "...",
    "key_drivers": [...],
    ...channel-specific extras
  }

Output:
  <reports>/<YYYY-MM-DD>/<HHMMSS>-portfolio.md
  <reports>/<YYYY-MM-DD>/<HHMMSS>-portfolio.json
  <reports>/<YYYY-MM-DD>/<HHMMSS>-<ticker>.md
  <reports>/<YYYY-MM-DD>/<HHMMSS>-<ticker>.json

Usage:
  python compose_report.py --session <dir> --reports <dir> [--settings <path>]
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

try:
    import yaml  # PyYAML
except ImportError:
    yaml = None


# direction × strength → numeric score
DIR_STR_TO_SCORE = {
    ("bull", "strong"): 3,
    ("bull", "medium"): 2,
    ("bull", "weak"): 1,
    ("neutral", "strong"): 0,
    ("neutral", "medium"): 0,
    ("neutral", "weak"): 0,
    ("bear", "weak"): -1,
    ("bear", "medium"): -2,
    ("bear", "strong"): -3,
}

DEFAULT_WEIGHTS = {"news": 0.30, "fundamentals": 0.40, "chart": 0.30}


def score_to_verdict(total: float) -> tuple[str, str]:
    """Return (label, emoji)."""
    if total >= 1.5:
        return "강매수", "🟢"
    if total >= 0.5:
        return "중매수", "🟡"
    if total > -0.5:
        return "중립", "⚪"
    if total > -1.5:
        return "중매도", "🟠"
    return "강매도", "🔴"


def load_json(p: Path) -> dict | None:
    try:
        return json.loads(p.read_text())
    except Exception:
        return None


def load_holdings(p: Path) -> dict:
    if yaml is None:
        # fallback: try to parse as JSON
        return load_json(p) or {"holdings": []}
    return yaml.safe_load(p.read_text()) or {"holdings": []}


def load_rubric_score(p: Path) -> dict | None:
    """Load deterministic rubric score for a ticker. Returns None if missing."""
    return load_json(p)


def copy_chart_pngs(session_dir: Path, day_dir: Path, ticker: str, stamp: str) -> dict:
    """Copy chart PNGs from session into the day_dir using <stamp>-<ticker>-{daily,intraday,daily-annotated}.png.

    Returns dict with bools for which charts succeeded.
    """
    import shutil
    out = {"daily": False, "intraday": False, "daily_annotated": False}
    charts_src = session_dir / "charts"
    name_map = {
        "daily": "daily.png",
        "intraday": "intraday.png",
        "daily_annotated": "daily-annotated.png",
    }
    for key, suffix in name_map.items():
        src = charts_src / f"{ticker}-{suffix}"
        if src.exists():
            dst = day_dir / f"{stamp}-{ticker}-{suffix}"
            shutil.copyfile(src, dst)
            out[key] = True
    return out


def load_settings(p: Path | None) -> dict:
    if p is None or not p.exists():
        return {"weights": DEFAULT_WEIGHTS, "base_currency": "KRW", "preset": "balanced"}
    if yaml is None:
        return load_json(p) or {"weights": DEFAULT_WEIGHTS}
    data = yaml.safe_load(p.read_text()) or {}
    weights = data.get("weights") or DEFAULT_WEIGHTS
    # normalize sum to 1.0
    total = sum(weights.values()) or 1.0
    weights = {k: v / total for k, v in weights.items()}
    data["weights"] = weights
    data.setdefault("base_currency", "KRW")
    return data


def _safe_score(direction, strength, channel_name: str, source: str = "") -> int:
    """Look up (direction, strength) in DIR_STR_TO_SCORE; warn to stderr on unknown."""
    raw = DIR_STR_TO_SCORE.get((direction, strength))
    if raw is None:
        tag = f"{channel_name}" + (f"/{source}" if source else "")
        print(f"WARN: unknown (direction={direction!r}, strength={strength!r}) on {tag} → score=0",
              file=sys.stderr)
        return 0
    return raw


def compute_verdict(news: dict | None, funda_agent: dict | None,
                    chart: dict | None, weights: dict,
                    rubric_score: dict | None = None) -> dict:
    """Compute weighted verdict. Fundamentals direction/strength comes from rubric if available,
    otherwise falls back to agent output (legacy behavior)."""
    parts = []
    weighted = 0.0

    # News (LLM-decided)
    if news is None:
        parts.append({"channel": "news", "direction": "n/a", "strength": "n/a",
                      "raw_score": 0, "weighted": 0, "missing": True})
    else:
        d = news.get("direction", "neutral")
        s = news.get("strength", "weak")
        raw = _safe_score(d, s, "news")
        w = weights.get("news", 0)
        wscore = raw * w
        weighted += wscore
        parts.append({"channel": "news", "direction": d, "strength": s,
                      "raw_score": raw, "weighted": round(wscore, 4)})

    # Fundamentals — prefer deterministic rubric, fall back to agent
    if rubric_score is not None:
        d = rubric_score.get("direction", "neutral")
        s = rubric_score.get("strength", "weak")
        source = "rubric"
    elif funda_agent is not None:
        d = funda_agent.get("direction", "neutral")
        s = funda_agent.get("strength", "weak")
        source = "agent"
    else:
        parts.append({"channel": "fundamentals", "direction": "n/a", "strength": "n/a",
                      "raw_score": 0, "weighted": 0, "missing": True})
        d = s = source = None

    if d is not None:
        raw = _safe_score(d, s, "fundamentals", source)
        w = weights.get("fundamentals", 0)
        wscore = raw * w
        weighted += wscore
        parts.append({"channel": "fundamentals", "direction": d, "strength": s,
                      "raw_score": raw, "weighted": round(wscore, 4), "source": source})

    # Chart (LLM-decided)
    if chart is None:
        parts.append({"channel": "chart", "direction": "n/a", "strength": "n/a",
                      "raw_score": 0, "weighted": 0, "missing": True})
    else:
        d = chart.get("direction", "neutral")
        s = chart.get("strength", "weak")
        raw = _safe_score(d, s, "chart")
        w = weights.get("chart", 0)
        wscore = raw * w
        weighted += wscore
        parts.append({"channel": "chart", "direction": d, "strength": s,
                      "raw_score": raw, "weighted": round(wscore, 4)})

    label, emoji = score_to_verdict(weighted)
    return {
        "total_weighted": round(weighted, 4),
        "label": label,
        "emoji": emoji,
        "parts": parts,
    }


def render_ticker_md(ticker: str, holding: dict | None, ind: dict | None,
                     funda: dict | None, news_a: dict | None, funda_a: dict | None,
                     chart_a: dict | None, verdict: dict, fx: float | None,
                     rubric_score: dict | None = None, chart_pngs: dict | None = None,
                     stamp: str = "", patterns_data: dict | None = None) -> str:
    lines = []
    lines.append(f"# {ticker} — 포트폴리오 분석 리포트")
    lines.append("")
    lines.append(f"**최종 verdict**: {verdict['emoji']} **{verdict['label']}** (점수 {verdict['total_weighted']:+.2f})")
    lines.append("")
    if holding:
        qty = holding.get("quantity")
        avg = holding.get("avg_buy_price")
        cur = holding.get("currency", "")
        price = ind.get("close") if ind else None
        unreal = None
        if qty and avg and price:
            unreal = (price - avg) * qty
            pct = (price - avg) / avg * 100
            lines.append(f"**보유**: {qty}주 / 평균가 {avg:,.2f} {cur} / 현재가 {price:,.2f} {cur} / "
                         f"평가손익 {unreal:+,.0f} {cur} ({pct:+.2f}%)")
            lines.append("")

    lines.append("## 채널별 판단")
    lines.append("")
    lines.append("| 채널 | 방향 | 강도 | 원시 점수 | 가중 점수 |")
    lines.append("|------|------|------|-----------|-----------|")
    for p in verdict["parts"]:
        if p.get("missing"):
            lines.append(f"| {p['channel']} | (데이터 없음) | - | 0 | 0 |")
        else:
            lines.append(f"| {p['channel']} | {p['direction']} | {p['strength']} | "
                         f"{p['raw_score']:+d} | {p['weighted']:+.3f} |")
    lines.append("")

    # === NEW: Chart PNGs ===
    if chart_pngs and (chart_pngs.get("daily") or chart_pngs.get("intraday")):
        lines.append("## 📈 차트")
        lines.append("")
        if chart_pngs.get("daily"):
            lines.append(f"![{ticker} daily]({stamp}-{ticker}-daily.png)")
            lines.append("")
        if chart_pngs.get("intraday"):
            lines.append(f"![{ticker} 15m]({stamp}-{ticker}-intraday.png)")
            lines.append("")

    # === NEW: Algorithmic shape patterns (H&S / Double T/B) ===
    raw_patterns = (patterns_data or {}).get("patterns") or []
    if raw_patterns:
        lines.append("## 🔍 감지된 패턴 (알고리즘)")
        lines.append("")
        if chart_pngs and chart_pngs.get("daily_annotated"):
            lines.append(f"![{ticker} 패턴 시각화]({stamp}-{ticker}-daily-annotated.png)")
            lines.append("")
        lines.append("> 일봉 zigzag 피벗 + 6개 false-positive 가드로 자동 추출한 후보입니다. "
                     "차트 agent가 vocabulary 가드 + 시각 검증으로 최종 confidence를 결정합니다.")
        lines.append("")
        lines.append("| 패턴 | 신뢰도 | 넥라인 돌파 | 목표가 | 형성 종료일 | 가드 결과 |")
        lines.append("|------|--------|-------------|--------|-------------|-----------|")
        for p in raw_patterns:
            name = p.get("name", "?")
            conf = p.get("confidence", "-")
            broken = "✓" if p.get("neckline_broken") else "—"
            break_date = p.get("break_date") or "-"
            target = p.get("target_price")
            target_str = f"{target:,.2f}" if isinstance(target, (int, float)) else "-"
            pivots = p.get("pivots") or []
            last_date = pivots[-1]["date"] if pivots else "-"
            passed = p.get("guards_passed") or []
            failed = p.get("guards_failed") or []
            badges = []
            if failed:
                badges.append(f"실패 {len(failed)}: {','.join(failed)}")
            else:
                badges.append(f"6/6 통과")
            badges_str = " · ".join(badges)
            lines.append(f"| **{name}** | {conf} | {broken} ({break_date}) | {target_str} | {last_date} | {badges_str} |")
        lines.append("")

    # === NEW: Deterministic fundamentals rubric breakdown ===
    if rubric_score:
        lines.append("## 펀더멘털 Rubric (deterministic)")
        lines.append("")
        total = rubric_score.get("total_score", 0)
        direction = rubric_score.get("direction", "neutral")
        strength = rubric_score.get("strength", "weak")
        lines.append(f"**Total**: {total:+d} → {direction} {strength}")
        lines.append("")
        lines.append("| 지표 | 값 | 점수 | 등급 |")
        lines.append("|------|----|----|-----|")
        for b in rubric_score.get("breakdown", []):
            val = b.get("value")
            val_str = f"{val:.2f}" if isinstance(val, (int, float)) else str(val)
            note = b.get("tier_note", "")
            metric = b.get("metric", "?")
            score = b.get("score", 0)
            lines.append(f"| {metric} | {val_str} | **{score:+d}** | {note} |")
        if rubric_score.get("skipped_metrics"):
            lines.append("")
            skipped_names = ", ".join(s.get("metric", "?") for s in rubric_score["skipped_metrics"])
            lines.append("_Skipped (null values)_: " + skipped_names)
        lines.append("")

    # Channel detail sections
    for label, agent in (("📰 뉴스", news_a), ("📊 펀더멘털", funda_a), ("📈 차트", chart_a)):
        lines.append(f"### {label}")
        lines.append("")
        if agent is None:
            lines.append("_데이터 없음_")
            lines.append("")
            continue
        if "reasoning_kr" in agent:
            lines.append(agent["reasoning_kr"])
            lines.append("")
        if "key_drivers" in agent and agent["key_drivers"]:
            lines.append("**핵심 근거**:")
            for d in agent["key_drivers"]:
                lines.append(f"- {d}")
            lines.append("")
        if label == "📰 뉴스" and agent.get("top_headlines"):
            lines.append("**주요 헤드라인**:")
            for h in agent["top_headlines"][:5]:
                title = h.get("title", "")
                url = h.get("url", "")
                sent = h.get("sentiment", "")
                lines.append(f"- [{sent}] [{title}]({url})" if url else f"- [{sent}] {title}")
            lines.append("")

    # === NEW: Patterns detected ===
    if chart_a and chart_a.get("patterns_detected"):
        lines.append("### 📊 패턴 감지")
        lines.append("")
        auto = [p for p in chart_a["patterns_detected"] if p.get("detection_method") == "automatic"]
        interp = [p for p in chart_a["patterns_detected"] if p.get("detection_method") == "agent_interpretation"]
        if auto:
            lines.append("**자동 감지 (지표 기반)**")
            for p in auto:
                tag = "🟢" if "bull" in p["name"] or p["name"] == "golden_cross" or "bullish" in p["name"] else "🔴" if "bear" in p["name"] or p["name"] == "death_cross" or "bearish" in p["name"] else "⚪"
                lines.append(f"- {tag} **{p['name']}** ({p['timeframe']}, {p['as_of']}) — confidence: {p.get('confidence','-')}")
            lines.append("")
        if interp:
            lines.append("**캔들/형태 패턴 (해석)**")
            for p in interp:
                tag = "🟡"
                ctx = f" — {p['context']}" if p.get("context") else ""
                lines.append(f"- {tag} **{p['name']}** ({p['timeframe']}, {p['as_of']}, confidence: {p.get('confidence','-')}){ctx}")
            lines.append("")

    if ind:
        lines.append("## 기술 지표 (참고)")
        lines.append("")
        idn = ind.get("indicators", {})
        lines.append(f"- RSI(14): **{idn.get('rsi14')}** ({idn.get('rsi14_label')})")
        lines.append(f"- MACD: hist={idn.get('macd_hist')} ({idn.get('macd_label')})")
        lines.append(f"- SMA20/50/200: {idn.get('sma20')} / {idn.get('sma50')} / {idn.get('sma200')}")
        bb = idn.get("bb_position")
        if bb is not None:
            lines.append(f"- Bollinger 위치: {bb} (0=하단, 1=상단)")
        if ind.get("signals"):
            lines.append("")
            lines.append("**신호**: " + ", ".join(ind["signals"]))
        lines.append("")

    if funda:
        lines.append("## 펀더멘털 (참고)")
        lines.append("")
        name = funda.get("long_name") or "n/a"
        sector = funda.get("sector") or "n/a"
        industry = funda.get("industry") or ""
        lines.append(f"- **{name}** — {sector}" + (f" / {industry}" if industry else ""))
        lines.append(f"- 시가총액: {funda.get('market_cap'):,.0f} {funda.get('currency', '')}" if funda.get("market_cap") else "- 시가총액: n/a")
        # Valuation
        valuation_parts = []
        if funda.get("trailing_pe") is not None:
            valuation_parts.append(f"PER(t) {funda['trailing_pe']:.2f}")
        if funda.get("forward_pe") is not None:
            valuation_parts.append(f"PER(f) {funda['forward_pe']:.2f}")
        if funda.get("price_to_book") is not None:
            valuation_parts.append(f"PBR {funda['price_to_book']:.2f}")
        if funda.get("peg_ratio") is not None:
            valuation_parts.append(f"PEG {funda['peg_ratio']:.2f}")
        if valuation_parts:
            lines.append(f"- 밸류에이션: {' | '.join(valuation_parts)}")
        # EPS / dividend
        eps_parts = []
        if funda.get("trailing_eps") is not None:
            eps_parts.append(f"EPS(t) {funda['trailing_eps']:.2f}")
        if funda.get("forward_eps") is not None:
            eps_parts.append(f"EPS(f) {funda['forward_eps']:.2f}")
        if funda.get("dividend_yield_pct") is not None:
            eps_parts.append(f"배당 {funda['dividend_yield_pct']:.2f}%")
        if eps_parts:
            lines.append(f"- 주당: {' | '.join(eps_parts)}")
        # Growth
        growth_parts = []
        if funda.get("revenue_growth_yoy_pct") is not None:
            growth_parts.append(f"매출 YoY {funda['revenue_growth_yoy_pct']:+.1f}%")
        if funda.get("earnings_growth_yoy_pct") is not None:
            growth_parts.append(f"이익 YoY {funda['earnings_growth_yoy_pct']:+.1f}%")
        if funda.get("roe_pct") is not None:
            growth_parts.append(f"ROE {funda['roe_pct']:.2f}%")
        if growth_parts:
            lines.append(f"- 성장/효율: {' | '.join(growth_parts)}")
        # Quality
        quality_parts = []
        if funda.get("operating_margin_pct") is not None:
            quality_parts.append(f"영업이익률 {funda['operating_margin_pct']:.2f}%")
        if funda.get("profit_margin_pct") is not None:
            quality_parts.append(f"순이익률 {funda['profit_margin_pct']:.2f}%")
        if funda.get("debt_to_equity") is not None:
            quality_parts.append(f"D/E {funda['debt_to_equity']:.1f}")
        if quality_parts:
            lines.append(f"- 마진/재무: {' | '.join(quality_parts)}")
        # EDGAR cross-check
        if funda.get("edgar_revenue_usd"):
            lines.append(f"- EDGAR 매출 (annual): ${funda['edgar_revenue_usd']:,.0f} (period end {funda.get('edgar_revenue_period_end')})")
        if funda.get("recommendation_key"):
            target = funda.get("target_mean_price")
            target_str = f", 목표가 {target}" if target else ""
            lines.append(f"- 애널리스트 컨센서스: {funda['recommendation_key']}{target_str}")
        lines.append("")

    lines.append("---")
    lines.append(f"_생성: {datetime.now().isoformat(timespec='seconds')}_")
    return "\n".join(lines)


def render_portfolio_md(ticker_summaries: list[dict], settings: dict, fx: float | None) -> str:
    lines = []
    lines.append("# 포트폴리오 종합 리포트")
    lines.append("")
    lines.append(f"분석 시각: `{datetime.now().isoformat(timespec='seconds')}`")
    base_cur = settings.get("base_currency", "KRW")
    lines.append(f"기준 통화: **{base_cur}**")
    if fx:
        lines.append(f"USD→KRW 환율: {fx:,.2f}")
    lines.append("")

    weights = settings.get("weights", DEFAULT_WEIGHTS)
    lines.append(f"채널 가중치: news={weights['news']:.2f}, fundamentals={weights['fundamentals']:.2f}, chart={weights['chart']:.2f}")
    lines.append("")

    lines.append("## 종목별 verdict 요약")
    lines.append("")
    lines.append("| 종목 | 시장 | 보유 | 평가액 | News | Funda | Chart | 합산 | Verdict |")
    lines.append("|------|------|------|--------|------|-------|-------|------|---------|")
    total_value_base = 0.0
    for s in ticker_summaries:
        v = s["verdict"]
        parts = {p["channel"]: p for p in v["parts"]}
        def cell(c):
            p = parts.get(c, {})
            if p.get("missing"):
                return "-"
            d = p["direction"][:1].upper()
            st = {"strong": "강", "medium": "중", "weak": "약"}.get(p["strength"], "-")
            return f"{d}{st}"
        market = s.get("market", "?")
        qty = s.get("quantity", 0)
        price = s.get("close")
        val_native = qty * price if (qty and price) else 0
        val_base = val_native
        if fx and s.get("currency") == "USD" and base_cur == "KRW":
            val_base = val_native * fx
        elif fx and s.get("currency") == "KRW" and base_cur == "USD":
            val_base = val_native / fx
        total_value_base += val_base
        lines.append(f"| {s['ticker']} | {market} | {qty} | {val_base:,.0f} {base_cur} | "
                     f"{cell('news')} | {cell('fundamentals')} | {cell('chart')} | "
                     f"{v['total_weighted']:+.2f} | {v['emoji']} {v['label']} |")
    lines.append("")
    lines.append(f"**총 평가액**: {total_value_base:,.0f} {base_cur}")
    lines.append("")

    lines.append("## 액션 추천 (정렬: 점수 절대값 내림차순)")
    lines.append("")
    sorted_t = sorted(ticker_summaries, key=lambda s: abs(s["verdict"]["total_weighted"]), reverse=True)
    for s in sorted_t:
        v = s["verdict"]
        # find strongest single driver
        drivers = []
        for ch in ("news", "fundamentals", "chart"):
            a = s.get(f"agent_{ch}")
            if a and a.get("key_drivers"):
                drivers.append(f"({ch}) {a['key_drivers'][0]}")
        top_driver = drivers[0] if drivers else "n/a"
        lines.append(f"- {v['emoji']} **{s['ticker']}** → {v['label']} ({v['total_weighted']:+.2f}). 핵심: {top_driver}")
    lines.append("")
    lines.append("---")
    lines.append("_상세 리포트는 같은 디렉토리의 종목별 .md 파일을 참고._")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--session", required=True, help="session dir with data/ + agents/ + holdings.yml")
    ap.add_argument("--reports", required=True, help="reports root dir")
    ap.add_argument("--settings", default=None, help="settings.yml path (optional)")
    args = ap.parse_args()

    session = Path(args.session).expanduser()
    reports_root = Path(args.reports).expanduser()
    settings = load_settings(Path(args.settings).expanduser() if args.settings else None)
    weights = settings["weights"]

    holdings_path = session / "holdings.yml"
    holdings_doc = load_holdings(holdings_path) if holdings_path.exists() else {"holdings": []}
    holdings_list = holdings_doc.get("holdings") or []
    by_ticker = {h["ticker"]: h for h in holdings_list}

    fx = None
    fx_path = session / "exchange_rate.json"
    if fx_path.exists():
        d = load_json(fx_path)
        if d and d.get("pair") == "USD_KRW":
            fx = d.get("rate")

    # discover tickers from agent outputs
    agents_dir = session / "agents"
    data_dir = session / "data"
    scores_dir = session / "scores"
    tickers = set()
    if agents_dir.exists():
        for f in agents_dir.glob("*-news.json"):
            tickers.add(f.name.replace("-news.json", ""))
        for f in agents_dir.glob("*-funda-agent.json"):
            tickers.add(f.name.replace("-funda-agent.json", ""))
        for f in agents_dir.glob("*-chart.json"):
            tickers.add(f.name.replace("-chart.json", ""))
    tickers.update(by_ticker.keys())
    tickers = sorted(tickers)

    now = datetime.now()
    day_dir = reports_root / now.strftime("%Y-%m-%d")
    day_dir.mkdir(parents=True, exist_ok=True)
    stamp = now.strftime("%H%M%S")

    summaries = []
    for t in tickers:
        ind = load_json(data_dir / f"{t}-indicators.json")
        funda = load_json(data_dir / f"{t}-fundamentals.json")
        news_a = load_json(agents_dir / f"{t}-news.json")
        funda_a = load_json(agents_dir / f"{t}-funda-agent.json")
        chart_a = load_json(agents_dir / f"{t}-chart.json")

        # Load deterministic rubric score (None if missing)
        rubric_score = load_rubric_score(scores_dir / f"{t}-rubric.json")

        # Load algorithmic patterns (None if detect_patterns wasn't run / missing)
        patterns_data = load_json(data_dir / f"{t}-patterns.json")

        verdict = compute_verdict(news_a, funda_a, chart_a, weights, rubric_score=rubric_score)
        holding = by_ticker.get(t)

        # Copy chart PNGs into the day directory
        chart_pngs = copy_chart_pngs(session, day_dir, t, stamp)

        # per-ticker files
        md = render_ticker_md(t, holding, ind, funda, news_a, funda_a, chart_a, verdict, fx,
                              rubric_score=rubric_score, chart_pngs=chart_pngs, stamp=stamp,
                              patterns_data=patterns_data)
        (day_dir / f"{stamp}-{t}.md").write_text(md)
        per_json = {
            "ticker": t,
            "as_of": ind.get("as_of") if ind else None,
            "close": ind.get("close") if ind else None,
            "currency": ind.get("currency") if ind else (funda.get("currency") if funda else None),
            "market": ind.get("market") if ind else (funda.get("market") if funda else None),
            "verdict": verdict,
            "channels": {"news": news_a, "fundamentals": funda_a, "chart": chart_a},
            "indicators": ind.get("indicators") if ind else None,
            "signals": ind.get("signals") if ind else None,
            "fundamentals": funda,
            "rubric_score": rubric_score,
            "chart_pngs": chart_pngs,
            "patterns": (patterns_data or {}).get("patterns") or [],
        }
        (day_dir / f"{stamp}-{t}.json").write_text(json.dumps(per_json, ensure_ascii=False, indent=2))

        summaries.append({
            "ticker": t,
            "market": ind.get("market") if ind else (holding.get("market") if holding else "?"),
            "currency": ind.get("currency") if ind else (holding.get("currency") if holding else None),
            "close": ind.get("close") if ind else None,
            "quantity": holding.get("quantity") if holding else 0,
            "verdict": verdict,
            "agent_news": news_a,
            "agent_fundamentals": funda_a,
            "agent_chart": chart_a,
        })

    # portfolio composite
    port_md = render_portfolio_md(summaries, settings, fx)
    (day_dir / f"{stamp}-portfolio.md").write_text(port_md)
    port_json = {
        "generated_at": now.isoformat(timespec="seconds"),
        "settings": settings,
        "fx_usd_krw": fx,
        "tickers": summaries,
    }
    (day_dir / f"{stamp}-portfolio.json").write_text(json.dumps(port_json, ensure_ascii=False, indent=2))

    # Terminal summary
    print()
    print("=" * 60)
    print(f"REPORT WRITTEN: {day_dir / f'{stamp}-portfolio.md'}")
    print("=" * 60)
    for s in summaries:
        v = s["verdict"]
        print(f"  {v['emoji']} {s['ticker']:12s}  {v['label']:6s}  {v['total_weighted']:+.2f}")
    print("=" * 60)


if __name__ == "__main__":
    main()
