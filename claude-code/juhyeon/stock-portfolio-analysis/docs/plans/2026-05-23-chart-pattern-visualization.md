# Chart Pattern Visualization Overlay — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` (single-session) or `superpowers:subagent-driven-development` (multi-task parallel) to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add deterministic detection + visual overlay (neckline, shoulder/peak markers, target projection) for two shape patterns — **Head & Shoulders (regular + inverse)** and **Double Top / Double Bottom (W-shape)** — to the `stock-portfolio-analysis` skill. The chart agent's `confidence: high` is upgraded so it requires BOTH algorithm candidates AND vocabulary-guard agreement, eliminating the current "LLM-only with no visual evidence" failure mode.

**Architecture:** Phase 2 of the skill grows by one script (`detect_patterns.py`) inserted between `calc_indicators.py` and `render_chart.py`. `render_chart.py` reads the new `*-patterns.json` and overlays detected patterns onto the existing daily candle PNG, producing `{ticker}-daily-annotated.png`. The chart-agent's contract changes from "detect patterns from OHLCV" to "verify algorithmically detected candidates against vocabulary guards." `compose_report.py` embeds the annotated PNG into each ticker's markdown report so the user can visually verify any pattern the LLM claims.

**Tech Stack:** Python 3.14, mplfinance (existing — `alines`/`hlines`/scatter `addplot`), pandas (existing), **npzigzag** (NEW — single new dep, pure numpy peak/valley extractor). No torch, no Streamlit, no GPL libraries.

**Scope (1차)**:
- **In scope**: H&S, Inverse H&S, Double Top, Double Bottom — **daily timeframe only** (per `chart-patterns.md` guard: "intraday <1h H&S 금지")
- **Out of scope (future)**: Hammer/Engulfing/Doji visualization (single-bar — already legible), Triangle/Wedge/Flag/Cup-and-Handle (vocabulary expansion), intraday formations

**Spec source:** This plan is self-contained — generated from the 2026-05-23 analysis session that compared 5 GitHub candidates (BennyThadikaran/stock-pattern, zeta-zetra/chart_patterns, keithorange/PatternPy, white07S/TradingPatternScanner, Omar-Karimov/ChartScanAI) and selected the "self-built" path (경로 2) for license cleanliness and minimal dependency footprint.

**Working dir:** All paths relative to `~/.claude/skills/stock-portfolio-analysis/` unless absolute. `SKILL_DIR=~/.claude/skills/stock-portfolio-analysis`. `PY=$SKILL_DIR/.venv/bin/python3`. `PIP=$SKILL_DIR/.venv/bin/pip`.

**Decisions locked in (2026-05-23 session):**
1. ✅ Self-built path — no external pattern library, only `npzigzag` for pivot extraction
2. ✅ H&S + Double Top/Bottom only for v1 (not full Core 7)
3. ✅ PNG用途 dual: 사용자 최종 보고서 임베드 + chart-agent 시각 입력

---

## File Structure

**New files (4):**
- `scripts/detect_patterns.py` — zigzag pivot extraction + H&S + Double T/B detection → `*-patterns.json`
- `references/pattern-detection-spec.md` — algorithm specification (parameter choices, false-positive guards in code form, golden test cases)
- `tests/test_detect_patterns.py` — unit tests + golden fixtures
- `tests/fixtures/patterns/` — synthetic OHLCV CSVs with known patterns for regression tests

**Modified files (6):**
- `scripts/render_chart.py` — read `*-patterns.json`, overlay via `mplfinance.alines` (neckline, shoulder-to-shoulder line), scatter (peak/trough markers), `hlines` (target projection); emit `*-daily-annotated.png` separately from existing `*-daily.png`
- `scripts/compose_report.py` — embed `*-daily-annotated.png` in ticker markdown when patterns exist; render `## 감지된 패턴` section listing each pattern's coordinates + confidence
- `references/agent-prompts/chart-agent.md` — add `patterns_path` + `annotated_png` inputs; rewrite "Your job" §2 from "identify patterns" to "verify algorithmic candidates against false-positive guards"; redefine confidence levels: `high` requires algorithm-detected AND all vocabulary guards pass AND (for completed patterns) neckline broken
- `references/chart-patterns.md` — mark §3 (H&S) and §4 (Double T/B) as `detection_method: automatic` for candidate emission, with agent providing `confidence` and `context`
- `SKILL.md` — insert `detect_patterns.py` call in Phase 2 between `calc_indicators.py` and `render_chart.py`; update Phase 0 install line to include `npzigzag`; update reference file list
- `references/settings.yml.example` — add optional `pattern_detection:` block (min_pivot_distance_bars, peak_equality_pct, neckline_break_required)

---

## Task 1: Install npzigzag + scaffold detect_patterns.py

**Files:**
- Modify: skill venv (no source change in this step)
- Create: `scripts/detect_patterns.py` (skeleton)

- [x] **Step 1: Install npzigzag into the skill venv** — *npzigzag and zigzag both failed on Python 3.14; fell back to `zigzag==0.2.2` with `numpy<2` + `--no-build-isolation`. Switched dep management to uv per user direction.*

```bash
$SKILL_DIR/.venv/bin/pip install --quiet npzigzag
$SKILL_DIR/.venv/bin/python3 -c "import npzigzag; print(npzigzag.__version__)"
```

Expected: prints version string, no ImportError. If the package is missing/renamed, fall back to `jbn/ZigZag` (`pip install zigzag`) and adjust the import in Task 2 Step 1.

- [x] **Step 2: Update `SKILL.md` Phase 0 install line** — replaced with uv sync + pip fallback block including Cython, numpy<2, and `--no-build-isolation zigzag`

Find the existing pip install line in SKILL.md (around line 48) and append `npzigzag`:

```bash
.venv/bin/pip install --quiet pykrx yfinance pandas requests pyyaml mplfinance pytest npzigzag
```

- [x] **Step 3: Create skeleton `scripts/detect_patterns.py`** — 54 lines, scaffold prints "scaffold" to stderr; main() argparse stub ready for Tasks 2-3

```python
#!/usr/bin/env python3
"""
Detect shape patterns (H&S, Double Top/Bottom) from OHLCV using zigzag pivots.

Reads:
  <data>/<ticker>-ohlcv.json   (daily OHLCV)

Writes:
  <data>/<ticker>-patterns.json

Output schema:
  {
    "ticker": "005930.KS",
    "timeframe": "daily",
    "as_of": "2026-05-19",
    "patterns": [
      {
        "name": "head_and_shoulders" | "inverse_head_and_shoulders"
              | "double_top" | "double_bottom",
        "pivots": [
          {"date": "2026-03-12", "price": 75200, "role": "left_shoulder"},
          {"date": "2026-04-02", "price": 78100, "role": "head"},
          ...
        ],
        "neckline": {"start_date": "...", "start_price": ...,
                     "end_date": "...",   "end_price": ...},
        "target_price": 68500,
        "neckline_broken": true | false,
        "confidence": "high" | "medium" | "low",
        "guards_passed": ["volume_declining", "prior_trend_present", ...],
        "guards_failed": []
      }
    ]
  }

Usage:
  python detect_patterns.py <ticker1> [...] --in <session>/data
"""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("tickers", nargs="+")
    ap.add_argument("--in", dest="in_dir", required=True)
    args = ap.parse_args()
    # TODO Task 2-3: implement
    print("scaffold", file=sys.stderr)

if __name__ == "__main__":
    main()
```

- [x] **Step 4: Commit** — `b8860d6` "deps(stock): add zigzag via uv-managed pyproject.toml; scaffold detect_patterns.py"

---

## Task 2: Implement zigzag pivot extraction + H&S detection

**Files:**
- Modify: `scripts/detect_patterns.py`
- Create: `references/pattern-detection-spec.md`

- [x] **Step 1: Write `references/pattern-detection-spec.md`** — 204 lines, all 6 guards + neckline/target math + output schema + golden fixture catalog + known limitations

| Parameter | Value | Source |
|---|---|---|
| `pivot_threshold_pct` | 3.0 (zigzag min %change) | Tuned for daily 250-bar window — balances noise vs missed patterns |
| `min_bars_between_pivots` | 5 | `chart-patterns.md` §4 guard "peaks within 5 bars = single wide top" |
| `shoulder_equality_pct` | 5.0 | `chart-patterns.md` §3 guard "right shoulder materially higher = not H&S" — interpret materially = ±5% |
| `peak_equality_pct` | 3.0 | `chart-patterns.md` §4 "two roughly equal peaks (within 3% in price)" |
| `head_prominence_pct` | 3.0 | head must exceed both shoulders by ≥ 3% |
| `prior_trend_lookback_bars` | 20 | Bars before left shoulder to confirm uptrend (H&S) / downtrend (inverse) |
| `prior_trend_min_pct` | 5.0 | Net price movement % over lookback to qualify as "prior trend" |
| `volume_check` | enabled | volume of right shoulder < volume of left shoulder & head |

- [x] **Step 2: Implement `extract_pivots(rows, threshold_pct)`** — close-driven zigzag, high/low for pivot prices

Use npzigzag to extract alternating peaks/troughs from `closes` (use `highs` for peak prices, `lows` for trough prices to avoid intra-bar bias). Output list of `(date, price, kind: 'peak'|'trough', bar_idx)`.

- [x] **Step 3: Implement `detect_head_and_shoulders(pivots, ohlcv) -> list[dict]`** — 5-pivot window, all 6 guards, confidence high/medium/low

Algorithm:
1. Slide a 5-pivot window across `pivots`
2. Require sequence pattern: `trough, peak(LS), trough(left_neck), peak(H), trough(right_neck), peak(RS), trough`
   — minimum 5 pivots: LS / left_neck / H / right_neck / RS
3. Apply guards from spec table above:
   - `abs(LS.price - RS.price) / max(LS, RS) ≤ shoulder_equality_pct`
   - `H.price > max(LS.price, RS.price) × (1 + head_prominence_pct/100)`
   - `min_bars_between_pivots ≤ all gaps`
   - Prior trend in `closes[LS.bar_idx - prior_trend_lookback_bars : LS.bar_idx]` must trend up by `prior_trend_min_pct`
   - Volume: `vol[RS] < min(vol[LS], vol[H])`
4. Compute `neckline` = line through (left_neck, right_neck) — linear extrapolation
5. Compute `target_price = neckline_at(H.date) - (H.price - neckline_at(H.date))` (height projection)
6. Check `neckline_broken`: any close in `[RS.bar_idx : last]` crosses neckline downward
7. Confidence:
   - `high`: all guards pass + neckline broken + volume confirmation
   - `medium`: all guards pass + neckline not yet broken
   - `low`: 1 guard failed (record which in `guards_failed`)

- [x] **Step 4: Implement `detect_inverse_head_and_shoulders` as mirror** — single `_detect_hs(inverse=bool)` body, public functions are thin wrappers

- [x] **Step 5: Smoke test on a synthetic series** — H&S happy/inverse/random-walk all behave correctly (see commit msg)

```bash
$PY -c "
import json
# Build synthetic H&S: 60, 70, 65, 80, 65, 70, 60 with linear fills
# (full smoke test deferred to Task 8)
"
```

- [x] **Step 6: Commit** — `09f5543` "feat(patterns): zigzag pivots + H&S detection with false-positive guards"

---

## Task 3: Implement Double Top / Double Bottom detection

**Files:**
- Modify: `scripts/detect_patterns.py`

- [x] **Step 1: Implement `detect_double_top(pivots, ohlcv) -> list[dict]`** — 3-pivot window, 4 guards (peak_equality 3%, spacing 5..120, prior_trend, volume)

Algorithm:
1. Slide a 3-pivot window: `peak(P1), trough(neck), peak(P2)`
2. Guards from `chart-patterns.md` §4:
   - `abs(P1.price - P2.price) / max(P1, P2) ≤ peak_equality_pct` (3%)
   - `min_bars_between_pivots ≤ P2.bar_idx - P1.bar_idx ≤ 50`
   - Prior uptrend before P1 (lookback / threshold from spec)
   - Volume: `vol[P2] < vol[P1]` (chart-patterns.md "usually lower")
3. `neckline_price = neck.price` (horizontal — double T/B necklines are typically flat)
4. `target_price = neckline_price - (max(P1.price, P2.price) - neckline_price)`
5. `neckline_broken`: any close in `[P2.bar_idx : last]` below neckline
6. Confidence rules same as H&S

- [x] **Step 2: Implement `detect_double_bottom` as mirror** — `_detect_double(inverse=True)` wrapper

- [x] **Step 3: Implement `process(ticker, in_dir)`** — already shipped in Task 2; in this task only added DT/DB calls

```python
def process(ticker, in_dir):
    ohlcv = json.loads((in_dir / f"{ticker}-ohlcv.json").read_text())
    rows = ohlcv["data"]
    pivots = extract_pivots(rows)
    patterns = []
    patterns += detect_head_and_shoulders(pivots, rows)
    patterns += detect_inverse_head_and_shoulders(pivots, rows)
    patterns += detect_double_top(pivots, rows)
    patterns += detect_double_bottom(pivots, rows)
    out = {"ticker": ticker, "timeframe": "daily",
           "as_of": rows[-1]["date"], "patterns": patterns}
    out_path = in_dir / f"{ticker}-patterns.json"
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2))
    return {"ticker": ticker, "status": "ok", "patterns_found": len(patterns)}
```

- [x] **Step 4: Wire `main()` to iterate tickers** — already shipped in Task 2 mirroring `calc_indicators.py:295-322`

- [x] **Step 5: Commit** — `8f526fc` "feat(patterns): Double Top/Bottom detection + process() wiring"

---

## Task 4: Extend render_chart.py to overlay detected patterns

**Files:**
- Modify: `scripts/render_chart.py`

- [x] **Step 1: Add `_load_patterns(data_dir, ticker)` helper**

Returns the parsed `*-patterns.json` or `{"patterns": []}` if missing.

- [x] **Step 2: Build mplfinance overlay arguments from patterns** — alines (neckline + polyline), scatter (pivot markers), hlines (targets); bullish/bearish color encoding

For each pattern in `patterns["patterns"]`:

```python
# Neckline as alines
alines.append([(pattern["neckline"]["start_date"], pattern["neckline"]["start_price"]),
               (pattern["neckline"]["end_date"],   pattern["neckline"]["end_price"])])

# Shoulder-to-head-to-shoulder connector (H&S only)
if pattern["name"].endswith("head_and_shoulders"):
    shoulder_line = [(pivot.date, pivot.price) for pivot in pattern["pivots"]]
    alines.append(shoulder_line)

# Peak/trough markers as scatter
marker_series = pd.Series([nan]*len(df), index=df.index)
for pivot in pattern["pivots"]:
    idx = df.index.get_indexer([pd.Timestamp(pivot["date"])], method="nearest")[0]
    marker_series.iloc[idx] = pivot["price"]
addplots.append(mpf.make_addplot(marker_series, type="scatter",
                                  markersize=120, marker="o",
                                  color="purple" if "head" in pattern["name"] else "blue"))

# Target as horizontal line
if pattern.get("target_price"):
    hlines_targets.append(pattern["target_price"])
```

Pass to `mpf.plot(... alines=dict(alines=alines, colors=['orange']*len(alines), linewidths=1.2),
                    hlines=dict(hlines=hlines_targets, colors=['red']*len(hlines_targets),
                                linestyle='--'),
                    addplot=addplots, ...)`

- [x] **Step 3: Output a separate file `{ticker}-daily-annotated.png`** — new `render_daily_annotated()` returns None when patterns empty

Keep the original `{ticker}-daily.png` untouched (used by chart-agent intraday workflow). Emit annotated PNG only if `patterns_json["patterns"]` is non-empty; otherwise skip and signal "no patterns detected" in stderr.

- [x] **Step 4: Update `render_daily()` signature** — kept `render_daily()` unchanged (per plan "original untouched") and added a sibling `render_daily_annotated()`. `--annotated/--no-annotated` CLI flag added.

- [x] **Step 5: Manual visual check** — synthetic H&S + Inverse H&S PNGs inspected; markers, neckline, polyline, target all rendered with correct bullish/bearish color encoding

Run on a ticker with a known pattern (e.g., NVDA last 250d) and open the PNG:

```bash
$PY $SKILL_DIR/scripts/detect_patterns.py NVDA --in /tmp/portfolio-session-XXX/data
$PY $SKILL_DIR/scripts/render_chart.py NVDA --data /tmp/portfolio-session-XXX/data --out /tmp/portfolio-session-XXX/charts
open /tmp/portfolio-session-XXX/charts/NVDA-daily-annotated.png
```

Visually verify: neckline drawn, shoulder/peak circles align with actual pivots, target line horizontal at expected price.

- [x] **Step 6: Commit** — `67bac20` "feat(chart): overlay neckline + pivot markers + target on daily PNG"

---

## Task 5: Wire detect_patterns.py into SKILL.md Phase 2

**Files:**
- Modify: `SKILL.md`

- [x] **Step 1: Insert call between `calc_indicators.py` (intraday) and `render_chart.py`**

Edit `SKILL.md` around lines 95-109. Add this line:

```bash
$PY $SKILL_DIR/scripts/detect_patterns.py    <TICKERS> --in  "$SESSION_DIR/data"
```

It should come AFTER both `calc_indicators.py` invocations and BEFORE `render_chart.py` so the renderer can read `*-patterns.json`.

- [x] **Step 2: Update the "Scripts" list at bottom of SKILL.md** — added detect_patterns.py + updated render_chart.py description for the annotated PNG output

- [x] **Step 3: Update Phase 2 narrative** — added paragraph explaining why detect_patterns must run between calc_indicators and render_chart

- [x] **Step 4: Commit** — `d09ef50` "docs(skill): wire detect_patterns into Phase 2"

---

## Task 6: Rewrite chart-agent.md contract for candidate verification

**Files:**
- Modify: `references/agent-prompts/chart-agent.md`
- Modify: `references/chart-patterns.md`

- [x] **Step 1: Add new INPUTS to chart-agent.md**

```markdown
- `daily_patterns_path`: `/tmp/portfolio-session-XXX/data/{ticker}-patterns.json`
- `daily_annotated_png`: `/tmp/portfolio-session-XXX/charts/{ticker}-daily-annotated.png` (if patterns detected)
```

- [x] **Step 2: Rewrite §2 ("Identify patterns")** — now verification-not-detection; algorithm + vocabulary + visual triangulation; downgrade-only rule

Replace existing §2 with:

```markdown
2. **Verify algorithmic pattern candidates**:
   - Read `daily_patterns_path` — this contains candidates already filtered by false-positive guards in code
   - For each candidate, cross-check against `chart-patterns.md` vocabulary one more time
     (the algorithm covers numeric guards; you cover contextual guards: e.g.,
     "is this a true reversal or just a relief rally in a downtrend?")
   - Inspect `daily_annotated_png` to confirm the visual makes sense
   - Decide which candidates survive to `patterns_detected`:
     - ✅ Include if algorithm + vocabulary + visual all agree
     - ❌ Discard if vocabulary guard not coded in algorithm fails (record reason in `caution_signals`)
   - For candle patterns (hammer/engulfing/doji) on 15m: continue agent_interpretation as before
```

- [x] **Step 3: Update confidence semantics** — high requires algorithm+vocabulary+visual triangulation; explicit downgrade-only rule

```markdown
- `high`: algorithm-detected (confidence=high in patterns.json — neckline broken + volume confirm) + vocabulary all pass + visual coherent
- `medium`: algorithm-detected (confidence=medium — pattern formed, neckline not yet broken) + agent agrees
- `low`: algorithm-detected with 1 guard failed OR agent-only candle pattern without confirmation
```

- [x] **Step 4: Update `references/chart-patterns.md` §3 and §4 headers** — both retitled "(automatic candidate + agent verification)"; detection-split paragraph rewritten

Change the `Detection split` block at top of file to reflect that #3, #4 are now also auto-detected (with agent verification), updating `Patterns 1-2` to `Patterns 1-4` for automatic candidate emission.

- [x] **Step 5: Commit** — `c637322` "feat(agent): chart-agent verifies algorithmic pattern candidates instead of inventing"

---

## Task 7: Embed annotated PNG in compose_report.py output

**Files:**
- Modify: `scripts/compose_report.py`

- [x] **Step 1: Locate the ticker markdown rendering section in compose_report.py** — `## 🔍 감지된 패턴 (알고리즘)` section inserted right after `## 📈 차트`

Search for where `{ticker}-daily.png` is currently embedded. Add a parallel block for `{ticker}-daily-annotated.png` that triggers only when patterns exist:

```python
patterns_path = data_dir / f"{ticker}-patterns.json"
if patterns_path.exists():
    patterns_data = json.loads(patterns_path.read_text())
    if patterns_data.get("patterns"):
        annotated_png = charts_dir / f"{ticker}-daily-annotated.png"
        if annotated_png.exists():
            md.append(f"![{ticker} 패턴 시각화]({annotated_png})")
            md.append("")
            md.append("## 감지된 패턴")
            for p in patterns_data["patterns"]:
                md.append(f"- **{p['name']}** ({p['confidence']}): "
                          f"target {p.get('target_price', 'N/A')}, "
                          f"neckline {'broken' if p['neckline_broken'] else 'intact'}")
```

- [x] **Step 2: Update the JSON sibling output** — `patterns` key added to per-ticker JSON

- [x] **Step 3: Sanity run** — end-to-end synthetic H&S session at /tmp/compose_smoke validated md + json + annotated PNG copy

- [x] **Step 4: Commit** — `fb538d2` "feat(report): embed annotated pattern chart + 감지된 패턴 section in ticker.md"

---

## Task 8: Golden-fixture regression tests

**Files:**
- Create: `tests/test_detect_patterns.py`
- Create: `tests/fixtures/patterns/synthetic_hs.json`
- Create: `tests/fixtures/patterns/synthetic_double_top.json`
- Create: `tests/fixtures/patterns/synthetic_no_pattern.json` (negative control)

- [x] **Step 1: Generate 5 synthetic OHLCV fixtures** — committed alongside `_generate.py`. Added 2 negative fixtures (uneven_shoulders, peaks_too_far) beyond the 3 in the plan to cover the per-guard regression.

```python
# fixtures/patterns/_generate.py — one-shot script, not run by pytest
# Produce 3 JSON files in the same schema as fetch_ohlcv.py output:
#   synthetic_hs.json:         clean H&S — peaks at 70/80/70 over 60 bars
#   synthetic_double_top.json: two peaks at 100 ± 1% separated by 30 bars
#   synthetic_no_pattern.json: random walk, no detectable formation
# Each with prior trend, linear interpolation between pivots, plausible volume
```

- [x] **Step 2: Write pytest cases** — 7 cases (5 plan-spec + 2 extras: schema check + short-series safety)

```python
def test_detects_clean_hs():
    result = process("synthetic_hs", FIXTURE_DIR)
    patterns = json.loads((FIXTURE_DIR / "synthetic_hs-patterns.json").read_text())["patterns"]
    assert any(p["name"] == "head_and_shoulders" for p in patterns)

def test_detects_double_top():
    result = process("synthetic_double_top", FIXTURE_DIR)
    patterns = json.loads((FIXTURE_DIR / "synthetic_double_top-patterns.json").read_text())["patterns"]
    assert any(p["name"] == "double_top" for p in patterns)

def test_no_false_positive_on_random_walk():
    result = process("synthetic_no_pattern", FIXTURE_DIR)
    patterns = json.loads((FIXTURE_DIR / "synthetic_no_pattern-patterns.json").read_text())["patterns"]
    assert len(patterns) == 0

def test_guards_reject_unequal_shoulders():
    # Fixture with right shoulder 10% higher than left → must NOT be H&S
    ...

def test_guards_reject_peaks_too_far_apart():
    # Fixture with peaks 8% apart (> 3%) → must NOT be double top
    ...
```

- [x] **Step 3: Run tests** — 7/7 new + 22/22 existing = 29/29 pytest pass

- [x] **Step 4: Commit** — `821c01c` "test(patterns): golden fixtures for H&S + DT + false-positive guards"

---

## Task 9: Real-data validation + final docs

**Files:**
- No source changes; validation + doc tidy

- [x] **Step 1: Run end-to-end on a small portfolio** — NVDA / AAPL / 005930.KS over 250d. All 3 annotated PNGs scored 2 (markers on actual peaks/troughs). 3/3 = 100% acceptance, exceeds 60% threshold. Real-data finding: NVDA emitted 18 candidates → added medium+ default filter (commit d4e7e2a).

```bash
$PY $SKILL_DIR/scripts/fetch_ohlcv.py NVDA AAPL 005930.KS --out /tmp/e2e/data --days 250
$PY $SKILL_DIR/scripts/calc_indicators.py NVDA AAPL 005930.KS --in /tmp/e2e/data
$PY $SKILL_DIR/scripts/detect_patterns.py NVDA AAPL 005930.KS --in /tmp/e2e/data
$PY $SKILL_DIR/scripts/render_chart.py NVDA AAPL 005930.KS --data /tmp/e2e/data --out /tmp/e2e/charts
ls /tmp/e2e/charts/*-annotated.png
```

For each annotated PNG produced, open it and manually score on a 3-point scale:
- 3: Pattern visually obvious and well-marked
- 2: Pattern present but markers slightly off
- 1: Spurious / clearly wrong

Acceptance: ≥ 60% of annotated PNGs scoring 2+. If below, return to Task 2-3 to retune guards (likely `pivot_threshold_pct` or `prior_trend_min_pct`).

- [x] **Step 2: Update `references/chart-patterns.md`** — completed inside Task 6 commit `c637322`

- [x] **Step 3: Update `SKILL.md`** — completed inside Task 5 commit `d09ef50`

- [x] **Step 4: Final commit** — `d4e7e2a` bundled the real-data finding (medium+ default filter) + .gitignore cleanup. The "finalize" doc updates from plan steps 2 & 3 already landed in their respective task commits.

---

## Open risks & escalation triggers

| Risk | Mitigation | Trigger to escalate |
|---|---|---|
| npzigzag has lookahead bias (pivots placed at points only known later) | Acceptable for "today's formed pattern" use case, not for backtest | If user wants to add backtest mode, swap for non-lookahead pivot logic |
| Real-data H&S/DT acceptance rate < 60% (Task 9 Step 1) | Retune `pivot_threshold_pct` (try 2.0 / 4.0) or `prior_trend_lookback_bars` | If still < 60% after 3 retunes, reconsider switching to PatternPy(C) for detection + keep our own visualization |
| chart-agent ignores annotated PNG (LLM vision unreliable) | Pass pattern coordinates as text in prompt explicitly; treat PNG as supplementary | If confidence accuracy drops vs current LLM-only baseline (measure on 10 known-pattern tickers), revert §2 prompt change |
| mplfinance `alines` rendering across daily gaps (weekends) | Test on a real ticker spanning multiple weeks; if line jumps look weird, snap to bar indices | If unfixable, draw connecting lines via `addplot` with line type instead of `alines` |

---

## Done criteria (whole plan)

- [x] `scripts/detect_patterns.py` exists, processes 1+ tickers, emits valid `*-patterns.json`
- [x] `render_chart.py` produces `*-daily-annotated.png` when patterns present
- [x] 5+ pytest cases pass in `tests/test_detect_patterns.py` — 7 cases
- [x] `chart-agent.md` rewritten — confidence semantics tied to algorithm + vocabulary + visual
- [x] `compose_report.py` embeds annotated PNG + "감지된 패턴" section in ticker.md
- [x] End-to-end real-data run (Task 9) ≥ 60% subjective accuracy on annotated PNGs — 3/3 (100%)
- [x] All commits land on the skill repo with no failing tests — 29/29 pytest pass

---

## Next Session Kickoff Prompt

Paste this into the next Claude Code session to resume:

> 다음 plan을 `superpowers:executing-plans` 스킬로 실행해줘:
> `~/.claude/skills/stock-portfolio-analysis/docs/plans/2026-05-23-chart-pattern-visualization.md`
>
> 이전 세션(2026-05-23)에서 결정된 사항:
> - 경로 2: 자체 구현 (npzigzag pivot + 자체 H&S/DT 알고리즘 + mplfinance alines/scatter 오버레이)
> - 1차 범위: Head & Shoulders (regular + inverse) + Double Top + Double Bottom, daily timeframe만
> - 시각화 PNG는 (a) compose_report.py가 ticker.md에 임베드하는 사용자용 + (b) chart-agent의 시각 입력용 둘 다 활용
>
> Task 1부터 순서대로 진행. 각 Task의 step 체크박스를 plan 파일에서 직접 업데이트하면서 가줘. 각 Task의 commit step 전에 한번 멈추고 작업 결과를 보여줘 — 내가 확인 후 진행 동의하면 commit하고 다음 Task로.
