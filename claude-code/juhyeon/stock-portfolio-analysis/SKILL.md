---
name: stock-portfolio-analysis
description: >-
  한국(KOSPI/KOSDAQ)·미국(NASDAQ/NYSE/AMEX) 주식 포트폴리오를 뉴스·기본면·차트 3채널 병렬 분석해 종목별 강/중/약 매수·매도 판정과 가중 종합 판정 생성. 트리거: 주식 분석, 종목 분석, 포트폴리오 분석, 종목 진단, 매수/매도 판단, 강매수/강매도/중립, 보유 종목 평가, '이 종목 어때', '지금 사도 돼', holdings.yml, 또는 티커(005930.KS, NVDA, AAPL 등)를 대고 평가를 요청할 때.
---

# Stock Portfolio Analysis (한국 KRX + 미국)

This skill analyzes equity portfolios — Korean (KOSPI, KOSDAQ) and US (NASDAQ, NYSE, AMEX) — through **three independent parallel channels** and produces a weighted final verdict per ticker.

The three channels are deliberately separate so each can spot signals the others miss:

- **📰 News** — last 7 days of material headlines (Korean for KRX, English for US)
- **📊 Fundamentals** — PER/PBR/EPS (KRX) or Revenue/NetIncome/EPS/ROE growth (US)
- **📈 Chart** — RSI(14), MACD(12,26,9), SMA(20/50/200), Bollinger Bands

Each channel emits a `(direction, strength)` pair → weighted score → final verdict in 5 buckets: 🟢 강매수 / 🟡 중매수 / ⚪ 중립 / 🟠 중매도 / 🔴 강매도.

The three channels are dispatched as **3 parallel subagents within a single message** so they run concurrently. For N tickers, the skill dispatches up to 3N subagent calls in one batch.

---

## When to use

Trigger this skill when the user:
- Mentions their portfolio, holdings, or보유 종목 and asks for an analysis
- Names one or more stock tickers (e.g., "005930.KS analyze", "NVDA 분석", "삼성전자 어때")
- Asks "이 종목 사도 돼?", "팔까?", "강매수 종목 골라줘"
- Wants news + fundamentals + chart combined view
- References `holdings.yml` or `~/.config/portfolio-analysis/`

Don't trigger for:
- Pure macroeconomic questions ("연준 정책이 어떻게 될까")
- ETF construction / portfolio theory questions (Markowitz, Sharpe, asset allocation)
- Crypto-only requests (skill covers equities only)

---

## Workflow

### Phase 0: First-run setup

Check if `~/.claude/skills/stock-portfolio-analysis/.venv/bin/python3` exists. If not:

```bash
cd ~/.claude/skills/stock-portfolio-analysis
# uv-managed: pyproject.toml lists dependencies; uv sync creates/refreshes .venv
uv sync --extra dev
# zigzag (pure-Cython) requires --no-build-isolation against the project venv
uv pip install --python .venv/bin/python --no-build-isolation 'zigzag==0.2.2'
```

Falls back if `uv` is not installed:

```bash
python3 -m venv .venv
.venv/bin/pip install --quiet --upgrade pip setuptools wheel Cython 'numpy<2'
.venv/bin/pip install --quiet pykrx yfinance pandas requests pyyaml mplfinance pytest
.venv/bin/pip install --quiet --no-build-isolation 'zigzag==0.2.2'
```

Check if `~/.config/portfolio-analysis/holdings.yml` exists. If not, copy from `references/holdings.yml.example`:

```bash
mkdir -p ~/.config/portfolio-analysis
[ -f ~/.config/portfolio-analysis/holdings.yml ] || \
  cp ~/.claude/skills/stock-portfolio-analysis/references/holdings.yml.example \
     ~/.config/portfolio-analysis/holdings.yml
[ -f ~/.config/portfolio-analysis/settings.yml ] || \
  cp ~/.claude/skills/stock-portfolio-analysis/references/settings.yml.example \
     ~/.config/portfolio-analysis/settings.yml
[ -f ~/.config/portfolio-analysis/fundamentals-rubric.yml ] || \
  cp ~/.claude/skills/stock-portfolio-analysis/references/fundamentals-rubric.yml \
     ~/.config/portfolio-analysis/fundamentals-rubric.yml
```

If the user is running this for the first time, tell them: "**~/.config/portfolio-analysis/holdings.yml**에 본인 보유 종목을 먼저 입력해 주세요. 예시 종목으로 채워져 있으니 본인 보유로 교체 후 다시 호출해 주세요." Then STOP and wait. Do not analyze the example holdings.

Optional: check for `~/.config/portfolio-analysis/.env` with API keys. If absent, proceed in free-tier mode (no warning needed — graceful degradation).

### Phase 1: Universe resolution

Determine which tickers to analyze:

- If the user provided ticker arguments (e.g., "/portfolio-analysis 005930.KS NVDA"): use only those tickers, mark mode as **single-ticker**.
- Otherwise: parse `~/.config/portfolio-analysis/holdings.yml` and use all `holdings[].ticker` entries.

Read the file and build the ticker list. For each ticker, note the holding metadata (quantity, avg_buy_price, currency) for later use in the report.

If holdings.yml has 0 entries: tell the user "보유 종목이 비어 있습니다. holdings.yml에 종목을 추가해 주세요." and STOP.

### Phase 2: Bulk data fetch

Create a session workspace:

```bash
SESSION_ID="$(date +%Y%m%d-%H%M%S)-$$"
SESSION_DIR="/tmp/portfolio-session-${SESSION_ID}"
mkdir -p "$SESSION_DIR"/{data,agents}
cp ~/.config/portfolio-analysis/holdings.yml "$SESSION_DIR"/holdings.yml
echo "SESSION_DIR=$SESSION_DIR"
```

Then fetch data for all tickers in one go (these are independent and can run in parallel — but Python scripts already batch, so sequential bash calls are fine):

```bash
SKILL_DIR=~/.claude/skills/stock-portfolio-analysis
PY=$SKILL_DIR/.venv/bin/python3

$PY $SKILL_DIR/scripts/fetch_ohlcv.py        <TICKERS> --out "$SESSION_DIR/data" --days 250
$PY $SKILL_DIR/scripts/fetch_intraday.py     <TICKERS> --out "$SESSION_DIR/data" --interval 15m --days 30
$PY $SKILL_DIR/scripts/calc_indicators.py    <TICKERS> --in  "$SESSION_DIR/data" --timeframe daily
$PY $SKILL_DIR/scripts/calc_indicators.py    <TICKERS> --in  "$SESSION_DIR/data" --timeframe intraday
$PY $SKILL_DIR/scripts/detect_patterns.py    <TICKERS> --in  "$SESSION_DIR/data"
$PY $SKILL_DIR/scripts/render_chart.py       <TICKERS> --data "$SESSION_DIR/data" --out "$SESSION_DIR/charts"
$PY $SKILL_DIR/scripts/fetch_fundamentals.py <TICKERS> --out "$SESSION_DIR/data"
$PY $SKILL_DIR/scripts/score_fundamentals.py <TICKERS> --data "$SESSION_DIR/data" \
    --rubric ~/.config/portfolio-analysis/fundamentals-rubric.yml \
    --out "$SESSION_DIR/scores"
$PY $SKILL_DIR/scripts/currency.py --pair USD_KRW --out "$SESSION_DIR/exchange_rate.json"
```

Replace `<TICKERS>` with the space-separated list. Each script logs per-ticker success/failure to stderr. If a script reports `ok > 0` (some tickers worked), proceed. If 0 succeeded across all scripts, STOP and report the error.

`detect_patterns.py` runs after `calc_indicators.py` (because the renderer needs `*-patterns.json`) and before `render_chart.py` (so the annotated PNG can be emitted in the same pass). It produces `<ticker>-patterns.json` containing H&S / Inverse H&S / Double Top / Double Bottom candidates with `confidence` and `guards_passed/failed` — these feed both the annotated daily chart and the chart-agent's verification step.

### Phase 3: Parallel channel analysis ⚡

This is the heart of the skill. **Dispatch 3 subagents per ticker in a single message** using the Agent tool. The 3 calls MUST appear in the same tool-use block to actually run in parallel.

For each ticker, read the corresponding prompt file and substitute the ticker + data paths, then dispatch:

```
For ticker T:

(All three Agent calls in a single message — do NOT split across messages)

  Agent(subagent_type="general-purpose",
        description="News analysis for T",
        prompt="""<full content of references/agent-prompts/news-agent.md>

INPUTS:
- ticker: T
- company_name_local: <Korean name for KRX, English name for US>
- market: KRX | US
- output_path: $SESSION_DIR/agents/T-news.json
""")

  Agent(subagent_type="general-purpose",
        description="Fundamentals analysis for T",
        prompt="""<full content of references/agent-prompts/fundamentals-agent.md>

INPUTS:
- ticker: T
- market: KRX | US
- fundamentals_path: $SESSION_DIR/data/T-fundamentals.json
- output_path: $SESSION_DIR/agents/T-funda-agent.json
""")

  Agent(subagent_type="general-purpose",
        description="Chart analysis for T",
        prompt="""<full content of references/agent-prompts/chart-agent.md>

INPUTS:
- ticker: T
- indicators_path: $SESSION_DIR/data/T-indicators.json
- ohlcv_path: $SESSION_DIR/data/T-ohlcv.json
- output_path: $SESSION_DIR/agents/T-chart.json
""")
```

For N tickers, repeat the above pattern N times — but you can also batch all 3N calls in a single message if N is small (≤5). For N > 5, batch in groups of 5 tickers (15 agents at once) to keep cognitive load manageable.

Each subagent writes its result JSON to the specified `output_path`. You don't need to capture subagent stdout — just wait for them to finish and the orchestrator's next phase reads the files.

**Critical**: each agent prompt file is large (≥100 lines). Read it once and embed its full content into each Agent call's prompt parameter. The INPUTS section at the bottom is what you customize per call.

### Phase 4: Verdict synthesis (deterministic)

Once all subagents are done, run compose_report.py — it reads `$SESSION_DIR/agents/*.json` + data files + holdings.yml + exchange_rate.json and produces all reports:

```bash
$PY $SKILL_DIR/scripts/compose_report.py \
  --session "$SESSION_DIR" \
  --reports ~/.portfolio-analysis/reports \
  --settings ~/.config/portfolio-analysis/settings.yml
```

The script:
1. Reads each agent's JSON output
2. Maps (direction, strength) → raw score per `references/verdict-rubric.md`
3. Applies channel weights from settings.yml (auto-normalized to sum=1)
4. Computes weighted total per ticker
5. Maps total → final verdict (🟢 강매수 ~ 🔴 강매도)
6. Renders Markdown + JSON per ticker AND a portfolio composite
7. Prints a one-screen summary table to terminal

**Important contract change**: the fundamentals channel verdict comes from `score_fundamentals.py`
(deterministic, rubric-driven) — the LLM fundamentals agent is now narrative-only. News and chart
channels are still LLM-decided.

### Phase 5: Present results

Show the user:
1. The terminal summary table (it prints from compose_report.py)
2. The path to the portfolio composite report
3. A 1-2 sentence headline ("3종목 중 2개가 매수 추천, 1개 중립")
4. Offer to open the markdown file (`open ~/.portfolio-analysis/reports/...`)

If the user asked about a single ticker, also paste the inline contents of that ticker's markdown so they can see the full analysis without leaving the chat.

---

## Output file structure

```
~/.portfolio-analysis/reports/2026-05-20/
├── 143005-portfolio.md           # 포트폴리오 종합 (이거 먼저 보세요)
├── 143005-portfolio.json         # 기계 처리용
├── 143005-005930.KS.md           # 삼성전자 상세
├── 143005-005930.KS.json
├── 143005-NVDA.md                # 엔비디아 상세
└── 143005-NVDA.json
```

Each `*.md` file is self-contained and human-readable. Each `*.json` mirrors the same data for automation.

---

## Common scenarios

### Scenario A: 전체 포트폴리오 일괄 분석
User: "내 포트폴리오 분석해줘" or just "/portfolio-analysis"
→ Use holdings.yml, all tickers, full 5-phase flow.

### Scenario B: 특정 종목만 빠르게 확인
User: "NVDA 지금 어때?" or "005930.KS 분석"
→ Single-ticker mode. Skip holdings.yml. Dispatch 3 channels for 1 ticker.

### Scenario C: 모니터링 (이력 비교)
User: "지난주 본 삼성전자랑 비교"
→ Find most recent prior report in `~/.portfolio-analysis/reports/`, surface diff (verdict 변경, 점수 변동).

### Scenario D: 가중치 변경
User: "장기 가치 투자 관점으로 다시 봐줘"
→ Update settings.yml `preset: long_term_value`, rerun Phase 4 only (data + agent outputs cached for the day).

---

## Error handling

- **Network down**: fetch_ohlcv/fetch_fundamentals fail → emit partial report with "데이터 없음" for affected channels.
- **Ticker not found** (pykrx/yfinance): script logs per-ticker error, continues with others. Final report lists skipped tickers separately.
- **Agent subagent failure**: missing JSON → compose_report.py treats that channel as `direction=neutral, strength=weak, score=0` and flags in the report.
- **Invalid holdings.yml**: yaml parse error → STOP, show the parse error to the user, ask them to fix.
- **Settings.yml weights don't sum to 1**: auto-normalize, log a note.

---

## Reference files

- `references/agent-prompts/news-agent.md` — News subagent system prompt
- `references/agent-prompts/fundamentals-agent.md` — Fundamentals subagent system prompt
- `references/agent-prompts/chart-agent.md` — Chart subagent (dual-timeframe + patterns)
- `references/verdict-rubric.md` — Direction/strength → score mapping + thresholds
- `references/channel-weights.md` — Weight presets and selection guide
- `references/chart-patterns.md` — Core 7 chart pattern reference (auto-detected + agent-interpreted)
- `references/pattern-detection-spec.md` — Algorithm spec for `detect_patterns.py`: thresholds, guards, JSON schema
- `references/fundamentals-rubric.yml` — Deterministic value-tier thresholds for ROE/PBR/PER/...
- `references/holdings.yml.example` — Sample portfolio file
- `references/settings.yml.example` — Sample settings file

---

## Scripts

- `scripts/fetch_ohlcv.py` — yfinance for both KRX (.KS/.KQ) and US OHLCV → JSON
- `scripts/fetch_intraday.py` — yfinance 15m × 30d intraday OHLCV
- `scripts/calc_indicators.py` — pandas-free pure Python: RSI, MACD, SMA, EMA, Bollinger
- `scripts/detect_patterns.py` — zigzag pivots → H&S / Inverse H&S / Double Top / Double Bottom candidates with confidence + guard pass/fail
- `scripts/render_chart.py` — mplfinance candlestick + SMA overlay + volume → PNG; also emits `<ticker>-daily-annotated.png` overlaying detected pattern necklines, pivot markers, and target lines
- `scripts/fetch_fundamentals.py` — yfinance `.info` for both markets, optionally enriched with SEC EDGAR companyfacts for US
- `scripts/score_fundamentals.py` — Reads rubric YAML, emits deterministic per-ticker score
- `scripts/currency.py` — USD/KRW via yfinance `KRW=X`
- `scripts/compose_report.py` — Aggregates 3-channel agent outputs + data → Markdown/JSON

All scripts use yfinance + requests + pyyaml. No paid API required for v1.

**Note on KRX data source**: We rely on yfinance for KRX tickers (using the `.KS`/`.KQ` suffix). As of 2026-05, `pykrx 1.2.8` is broken due to KRX website changes — yfinance proxies KRX data reliably and also exposes the same `.info` fundamentals fields as US tickers, so the skill uses one library for both markets.

---

## Why three channels separated?

A single LLM "judge everything" prompt tends to converge on the loudest signal (often news, because it's the most vivid). By splitting into 3 isolated subagents with different evidence bases:

- **News** can't see the chart, so it won't say "주가가 오르고 있어서 bullish" (that's circular)
- **Fundamentals** can't see news, so it won't say "어닝 발표가 있을 거라 bullish" (that's news)
- **Chart** can't see fundamentals, so it won't say "PER가 낮아서 bullish" (that's funda)

Each channel must justify its verdict from its own evidence base. The weighted sum then reflects how much each evidence type matters to *the user's* investment style.

This avoids the common AI failure mode of "all the bullish reasons stack together to manufacture conviction".

---

## Limits and non-goals (v1)

- Equity only (no crypto, no bonds, no commodities, no FX positions)
- Long positions only (short / negative quantity not interpreted)
- Single-day snapshot (no intraday, no after-hours)
- No actual trading execution
- No portfolio optimization (Markowitz / risk parity / etc.) — that's a separate skill
- News agent cannot read paywalled articles
- US EDGAR fundamentals are at annual/quarterly granularity (no monthly KPIs)
