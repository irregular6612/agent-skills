# Stock Portfolio Analysis — Charts, Patterns, Deterministic Rubric

**Date**: 2026-05-20
**Status**: Approved (pending user review)
**Skill**: `stock-portfolio-analysis`

## 1. Motivation

The current skill produces 3-channel verdicts (news / fundamentals / chart) but the chart channel
is purely numeric (RSI/MACD/SMA values) and the fundamentals channel lets the LLM decide
direction/strength subjectively. Two problems follow:

1. **No visual artifact** — the report has no chart image, only text indicators. Users can't quickly
   eyeball trend or pattern context.
2. **Fundamentals verdict is not reproducible** — two runs on the same data can produce different
   verdicts because the agent reads the same numbers but lands on different judgments.

This spec upgrades the skill with: (a) dual-timeframe charts (daily + 15-minute) rendered as PNG and
embedded in the report, (b) a Core 7 pattern reference library that grounds chart-agent
interpretation in a consistent vocabulary, and (c) a deterministic fundamentals rubric that drives
the channel verdict from value-tier mappings instead of LLM judgment.

## 2. Architecture

```
Phase 0  : First-run setup (unchanged)
Phase 1  : Universe resolution (unchanged)
Phase 2  : Bulk data fetch (extended)
           ├─ fetch_ohlcv.py        (daily 250d)        — existing
           ├─ fetch_intraday.py     (15m × 30d)         — NEW
           ├─ calc_indicators.py    (daily)             — existing
           ├─ calc_indicators.py    (intraday)          — extended (--timeframe flag)
           ├─ render_chart.py       (daily + intraday)  — NEW
           ├─ fetch_fundamentals.py                     — existing
           └─ score_fundamentals.py                     — NEW (rubric-driven)
Phase 3  : 3 parallel agents per ticker (unchanged structure)
           ├─ news-agent     (unchanged)
           ├─ funda-agent    (prompt rewritten — narrative only)
           └─ chart-agent    (prompt extended — patterns reference + intraday)
Phase 4  : compose_report.py (extended — chart embeds + rubric breakdown)
Phase 5  : Present results (unchanged)
```

The 5-phase outer skeleton stays. Phase 2 grows from 4 to 7 script calls. Phase 3's agent prompts
are extended (chart) and rewritten (fundamentals). Phase 4 adds two new report sections.

## 3. Components

### 3.1 New Files

| Path | Purpose |
|------|---------|
| `scripts/fetch_intraday.py` | yfinance 15m × 30d intraday OHLCV for KRX (.KS/.KQ) + US |
| `scripts/render_chart.py` | mplfinance candlestick + SMA overlay + volume → PNG ×2 |
| `scripts/score_fundamentals.py` | Reads fundamentals JSON + rubric YAML → deterministic score |
| `references/chart-patterns.md` | Core 7 pattern vocabulary (ASCII + identification + strength) |
| `references/fundamentals-rubric.yml` | Threshold tiers per metric (user-customizable) |

### 3.2 Modified Files

| Path | Change |
|------|--------|
| `scripts/calc_indicators.py` | Add `--timeframe daily\|intraday`. Intraday skips SMA200 (needs ≥200 bars, 15m × 30d only has ~780, but SMA200 over 200 15-min bars ≈ 50 hours of trading isn't meaningful as a "long-term" line). Intraday uses SMA20/60. |
| `scripts/compose_report.py` | Embed PNG paths, render rubric breakdown table, render patterns_detected section. Channel score for fundamentals comes from deterministic rubric (not agent output). |
| `references/agent-prompts/chart-agent.md` | Add intraday inputs + chart-patterns.md content embedded. Output schema gains `patterns_detected` array. |
| `references/agent-prompts/fundamentals-agent.md` | direction/strength frozen — agent must copy from rubric score. Agent role narrows to `reasoning_kr`, `sector_context`, `red_flags`. |

### 3.3 Configuration Surface

```yaml
# settings.yml additions (all optional; defaults shown)
chart:
  intraday_interval: "15m"    # 1m | 5m | 15m | 30m | 60m
  intraday_days: 30
  render_chart: true          # set false to skip PNG generation
```

`fundamentals-rubric.yml` lives at two locations with override precedence:

1. `~/.config/portfolio-analysis/fundamentals-rubric.yml` (user) — wins if present
2. `~/.claude/skills/stock-portfolio-analysis/references/fundamentals-rubric.yml` (skill default) —
   copied to user location on first run

## 4. Deterministic Fundamentals Rubric

### 4.1 Rubric File Format

```yaml
metrics:
  trailing_pe:
    direction: lower_better
    tiers:
      - {threshold: 10,   score: +2, note: "저평가"}
      - {threshold: 15,   score: +1, note: "적정"}
      - {threshold: 25,   score:  0, note: "보통"}
      - {threshold: 40,   score: -1, note: "고평가"}
      - {threshold: 9999, score: -2, note: "거품"}
    null_behavior: skip   # 적자기업: 점수 미산정, agent narrative에서 설명

  price_to_book:
    direction: lower_better
    tiers:
      - {threshold: 1.0,  score: +2}
      - {threshold: 2.0,  score: +1}
      - {threshold: 4.0,  score:  0}
      - {threshold: 8.0,  score: -1}
      - {threshold: 9999, score: -2}

  roe_pct:
    direction: higher_better
    tiers:
      - {threshold: 20,   score: +2, note: "탁월"}
      - {threshold: 15,   score: +1, note: "양호"}
      - {threshold:  8,   score:  0, note: "보통"}
      - {threshold:  0,   score: -1, note: "저효율"}
      - {threshold: -9999, score: -2, note: "자본잠식 위험"}

  revenue_growth_yoy_pct:
    direction: higher_better
    tiers:
      - {threshold:  20,  score: +2}
      - {threshold:  10,  score: +1}
      - {threshold:   0,  score:  0}
      - {threshold: -10,  score: -1}
      - {threshold: -9999, score: -2}

  earnings_growth_yoy_pct:
    direction: higher_better
    tiers:
      - {threshold:  30,  score: +2}
      - {threshold:  10,  score: +1}
      - {threshold:   0,  score:  0}
      - {threshold: -20,  score: -1}
      - {threshold: -9999, score: -2}

  debt_to_equity:
    direction: lower_better
    tiers:
      - {threshold:  50,  score: +1}
      - {threshold: 100,  score:  0}
      - {threshold: 200,  score: -1}
      - {threshold: 9999, score: -2}

aggregation:
  # Sum of metric scores → direction + strength
  bull_strong:  6      # total >= 6
  bull_medium:  3      # 3 ≤ total < 6
  bull_weak:    1      # 1 ≤ total < 3
  bear_weak:   -1      # -2 < total ≤ -1
  bear_medium: -3      # -5 < total ≤ -3
  bear_strong: -6      # total ≤ -6
  # 0 → neutral
```

### 4.2 Tier Evaluation Semantics

- `direction: lower_better` (PER, PBR, D/E): walk tiers top-down. First tier whose `threshold`
  the value is **less than or equal to** wins.
- `direction: higher_better` (ROE, growth): walk tiers top-down. First tier whose `threshold`
  the value is **greater than or equal to** wins.
- `null_behavior: skip`: metric not in total. Total still aggregates remaining metrics.
- Score range: roughly [-12, +11] with all 6 metrics scoring (D/E tier is asymmetric:
  +1 max, -2 min). Aggregation mapping is set so +6 ≈ majority of metrics scoring +1 or
  better with at least one +2.

### 4.3 Channel Score Wiring

`compose_report.py` change: when reading the fundamentals channel for verdict synthesis,
the source is `$SESSION_DIR/scores/<ticker>-rubric.json` (deterministic), not
`$SESSION_DIR/agents/<ticker>-funda-agent.json` (LLM narrative). The agent file is still loaded
for `reasoning_kr` / `sector_context` / `red_flags` rendering — but its `direction` and `strength`
fields are ignored.

The fundamentals agent prompt explicitly states this contract so the agent doesn't try to "win"
a direction the rubric already decided.

## 5. Chart Rendering

### 5.1 Files Produced (Per Ticker)

```
$SESSION_DIR/charts/
├── <ticker>-daily.png       # 250 daily bars + SMA20/50/200 + volume sub-panel
└── <ticker>-intraday.png    # 30d × 15m bars + SMA20/60 + volume sub-panel
```

### 5.2 Visual Spec

- mplfinance `type='candle'`, style `'yahoo'`
- Daily: SMA20 (blue), SMA50 (orange), SMA200 (red) overlay
- Intraday: SMA20 (blue), SMA60 (orange) overlay
- Cross markers (golden / death / MACD bullish / MACD bearish): annotated arrows
- Volume sub-panel below (mplfinance default)
- Title: `{ticker} — {timeframe} as of {date}`
- 1200×800 px, 100 dpi

### 5.3 Report Embedding

Each per-ticker MD includes:

```markdown
## 📈 차트

![{ticker} daily]({ticker}-daily.png)
![{ticker} 15m]({ticker}-intraday.png)
```

PNG files are copied from session dir into the per-day report dir during compose to make
the report self-contained.

## 6. Pattern Library (Core 7)

### 6.1 Catalogue

| # | Pattern | Detection | Primary Timeframe |
|---|---------|-----------|-------------------|
| 1 | Golden / Death Cross (SMA20×SMA60 intraday, SMA50×SMA200 daily) | Automatic | Both |
| 2 | MACD Bullish / Bearish Cross | Automatic | Both |
| 3 | Head & Shoulders (+ Inverse) | Agent interpretation | Daily |
| 4 | Double Top / Double Bottom | Agent interpretation | Daily |
| 5 | Hammer / Inverted Hammer | Agent interpretation | Intraday |
| 6 | Engulfing (Bullish / Bearish) | Agent interpretation | Intraday |
| 7 | Doji (standard / dragonfly / gravestone / long-legged) | Agent interpretation | Intraday |

### 6.2 Reference File Structure

`references/chart-patterns.md` contains 7 sections, each with:
- ASCII shape diagram
- Identification criteria (numeric where possible)
- Implication (bullish / bearish / neutral reversal / continuation)
- False-positive guards ("절대 부르지 말 것")
- Strength scoring rubric (weak / medium / strong)

### 6.3 Agent Output Extension

```json
{
  "patterns_detected": [
    {
      "name": "golden_cross",
      "timeframe": "daily",
      "as_of": "2026-05-19",
      "detection_method": "automatic",
      "confidence": "high"
    },
    {
      "name": "hammer",
      "timeframe": "15m",
      "as_of": "2026-05-20T14:30",
      "detection_method": "agent_interpretation",
      "confidence": "medium",
      "context": "직전 5봉 -1.8% 하락 후 하단 그림자 2.3배"
    }
  ]
}
```

`patterns_detected` is a NEW field on the chart agent output. Existing fields
(`direction`, `strength`, `key_drivers`, `reasoning_kr`, etc.) are unchanged.

### 6.4 Report Section

Per-ticker MD gains a new section after the chart embed:

```markdown
## 📊 패턴 분석

### 자동 감지 (지표 기반)
- 🟢 **Golden Cross** (일봉, 2026-05-15)
- 🟢 **MACD Bullish Cross** (일봉, 2026-05-17)

### 캔들/형태 패턴 (해석)
- 🟡 **망치형** (15분봉, 2026-05-20 14:30) — confidence: medium
  - 직전 5봉 -1.8% 하락 후 하단 그림자 2.3배
```

## 7. Data Flow Per Ticker

```
fetch_ohlcv ──┐
fetch_intraday ──┐
                 ├─→ calc_indicators(daily) ──┐
                 │                            ├─→ render_chart ──→ PNG×2
                 └─→ calc_indicators(intraday)┘
fetch_fundamentals ──→ score_fundamentals ──→ rubric.json
                                                  │
                                                  ↓
        ┌────────────────┬─────────────────┬──────────────┐
        ↓                ↓                 ↓              ↓
    news-agent     funda-agent       chart-agent      compose_report
    (narrative)    (narrative only)  (+ patterns)         │
        │                │                 │              │
        └─────→ agents/ ─┴─────────────────┘              ↓
                                                    per-ticker MD/JSON
                                                    + portfolio MD/JSON
```

## 8. Error Handling

| Scenario | Behavior |
|----------|----------|
| Intraday fetch fails (network / weekend / unsupported ticker) | Skip intraday chart + intraday indicators; daily proceeds normally |
| mplfinance import fails | Skip PNG generation; report includes text analysis only; log warning |
| rubric.yml missing | Use skill default; copy to `~/.config/...` for next time |
| All rubric metrics null (e.g., new IPO, no financials) | direction=neutral, strength=weak, channel score=0; report flags |
| Fundamentals agent emits direction/strength contradicting rubric | Rubric wins; log mismatch as audit trail |
| OHLCV insufficient (< 30 bars) | Skip ticker with error in summary (existing behavior) |

## 9. Backward Compatibility

- Existing `holdings.yml` files: unchanged schema, no migration needed
- Existing `settings.yml` files: new `chart:` block is optional with sane defaults
- Existing reports: still readable (new sections appear at bottom; no schema migration)
- Existing `verdict-rubric.md` (3-channel weighted scoring): unchanged
- New deps: `mplfinance` (single new pip install in Phase 0)

## 10. Open Risks / Non-Goals

**Risks**:
- Pattern false positives: even with reference guards, the agent may "see" patterns. Mitigation:
  reference doc has explicit "절대 부르지 말 것" section per pattern; agent prompt requires
  pattern_detected entries to cite candle indices.
- Sector blindness in rubric: PER 8 = +2 globally even for low-PER-normal sectors (banks). Accepted
  as documented limitation; agent narrative compensates by stating sector context.
- yfinance intraday rate limits: 15m × 30d × multiple tickers may hit rate limit. Mitigation:
  yfinance handles this with internal throttling; failures degrade gracefully (see §8).

**Non-Goals** (deferred):
- Pattern detection via classical TA libraries (TA-Lib, pandas-ta) — keep agent-led interpretation
- Algorithmic backtesting of detected patterns
- Multi-timeframe correlation analysis beyond "both daily and intraday flagged X"
- Tick-level (1m) charts — 15m is the floor

## 11. Implementation Order

Plan (next phase, via writing-plans skill):

1. `scripts/fetch_intraday.py` — clone fetch_ohlcv.py structure, swap `interval` param
2. `scripts/calc_indicators.py` — add `--timeframe` flag, intraday code path
3. `scripts/render_chart.py` — mplfinance pipeline
4. `references/fundamentals-rubric.yml` — default thresholds (this spec's §4.1)
5. `scripts/score_fundamentals.py` — rubric evaluator
6. `references/chart-patterns.md` — Core 7 catalogue
7. `references/agent-prompts/chart-agent.md` — extend with patterns + intraday
8. `references/agent-prompts/fundamentals-agent.md` — narrative-only contract
9. `scripts/compose_report.py` — chart embed + rubric table + patterns section
10. `SKILL.md` — Phase 2 + Phase 4 docs updated, new files listed
11. `Phase 0` venv install adds `mplfinance`

## 12. User Contribution Point

`references/fundamentals-rubric.yml` is intentionally exposed as the primary user-customization
surface. The default thresholds in §4.1 are starter values calibrated for balanced equity
investing. Users with different philosophies (deep value, growth-tolerant, dividend-focused)
should edit `~/.config/portfolio-analysis/fundamentals-rubric.yml` to reshape the rubric. This is
the 5-10 line decision that personalizes the entire deterministic verdict.
