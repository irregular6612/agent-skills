# Charts, Patterns & Deterministic Rubric — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add dual-timeframe candlestick charts (PNG-embedded), a Core 7 pattern reference library, and a deterministic fundamentals rubric (YAML-thresholded) to the `stock-portfolio-analysis` skill.

**Architecture:** Phase 2 of the skill grows from 4 to 7 script calls (intraday fetch, intraday indicators, chart rendering, deterministic scoring). Phase 4 (`compose_report.py`) gains chart-embed, rubric-breakdown, and patterns-detected sections. The fundamentals channel verdict now comes from a YAML rubric instead of LLM judgment; the LLM provides narrative only.

**Tech Stack:** Python 3.14, yfinance (existing), pandas (existing), pyyaml (existing), **mplfinance** (NEW), **pytest** (NEW dev dep).

**Spec:** `~/.claude/skills/stock-portfolio-analysis/docs/specs/2026-05-20-charts-patterns-deterministic-rubric.md`

**Working dir:** All paths in this plan are relative to `~/.claude/skills/stock-portfolio-analysis/` unless absolute. `SKILL_DIR=~/.claude/skills/stock-portfolio-analysis`. `PY=$SKILL_DIR/.venv/bin/python3`. `PIP=$SKILL_DIR/.venv/bin/pip`.

---

## File Structure

**New files (8):**
- `scripts/fetch_intraday.py` — yfinance 15m × 30d fetcher
- `scripts/render_chart.py` — mplfinance PNG renderer
- `scripts/score_fundamentals.py` — deterministic rubric evaluator
- `references/chart-patterns.md` — Core 7 vocabulary
- `references/fundamentals-rubric.yml` — default thresholds
- `tests/__init__.py` — empty marker
- `tests/test_score_fundamentals.py` — pure-logic unit tests
- `tests/test_calc_indicators.py` — intraday timeframe smoke test

**Modified files (5):**
- `scripts/calc_indicators.py` — add `--timeframe daily|intraday` flag
- `scripts/compose_report.py` — embed PNGs, render rubric/patterns sections, use rubric for funda channel score
- `references/agent-prompts/chart-agent.md` — extend with intraday + patterns
- `references/agent-prompts/fundamentals-agent.md` — narrative-only contract
- `references/settings.yml.example` — add `chart:` block
- `SKILL.md` — update Phase 2, Phase 4 docs, deps

---

## Task 1: Install new dependencies (mplfinance + pytest)

**Files:**
- Modify: skill venv (no source file change in this task)

- [ ] **Step 1: Install mplfinance and pytest into the skill venv**

```bash
$SKILL_DIR/.venv/bin/pip install --quiet mplfinance pytest
```

- [ ] **Step 2: Verify imports work**

```bash
$SKILL_DIR/.venv/bin/python3 -c "import mplfinance, pytest; print(mplfinance.__version__, pytest.__version__)"
```

Expected: prints two version strings, no ImportError.

- [ ] **Step 3: Commit nothing — venv is `.gitignored`, but update SKILL.md Phase 0 to mention new deps**

Edit `SKILL.md` Phase 0 install line. Find the existing pip install line and add the two new packages:

```bash
# In SKILL.md, replace this line:
#   .venv/bin/pip install --quiet pykrx yfinance pandas requests pyyaml
# With this line:
.venv/bin/pip install --quiet pykrx yfinance pandas requests pyyaml mplfinance pytest
```

- [ ] **Step 4: Commit**

```bash
git -C $SKILL_DIR add SKILL.md
git -C $SKILL_DIR commit -m "deps: add mplfinance + pytest for charts and TDD"
```

---

## Task 2: Create default fundamentals rubric YAML

**Files:**
- Create: `references/fundamentals-rubric.yml`

- [ ] **Step 1: Write the rubric file**

Create `$SKILL_DIR/references/fundamentals-rubric.yml`:

```yaml
# Deterministic Fundamentals Rubric
# Edit thresholds to match your investment philosophy.
# Override location: ~/.config/portfolio-analysis/fundamentals-rubric.yml

metrics:
  trailing_pe:
    direction: lower_better
    null_behavior: skip   # 적자기업 → 점수 미산정, agent narrative에서 설명
    tiers:
      - {threshold: 10,   score: +2, note: "저평가"}
      - {threshold: 15,   score: +1, note: "적정"}
      - {threshold: 25,   score:  0, note: "보통"}
      - {threshold: 40,   score: -1, note: "고평가"}
      - {threshold: 9999, score: -2, note: "거품"}

  price_to_book:
    direction: lower_better
    null_behavior: skip
    tiers:
      - {threshold: 1.0,  score: +2, note: "장부가 이하"}
      - {threshold: 2.0,  score: +1, note: "저평가"}
      - {threshold: 4.0,  score:  0, note: "보통"}
      - {threshold: 8.0,  score: -1, note: "고평가"}
      - {threshold: 9999, score: -2, note: "거품"}

  roe_pct:
    direction: higher_better
    null_behavior: skip
    tiers:
      - {threshold: 20,    score: +2, note: "탁월"}
      - {threshold: 15,    score: +1, note: "양호"}
      - {threshold:  8,    score:  0, note: "보통"}
      - {threshold:  0,    score: -1, note: "저효율"}
      - {threshold: -9999, score: -2, note: "자본잠식 위험"}

  revenue_growth_yoy_pct:
    direction: higher_better
    null_behavior: skip
    tiers:
      - {threshold:  20,   score: +2, note: "고성장"}
      - {threshold:  10,   score: +1, note: "성장"}
      - {threshold:   0,   score:  0, note: "정체"}
      - {threshold: -10,   score: -1, note: "감소"}
      - {threshold: -9999, score: -2, note: "역성장"}

  earnings_growth_yoy_pct:
    direction: higher_better
    null_behavior: skip
    tiers:
      - {threshold:  30,   score: +2, note: "어닝 모멘텀"}
      - {threshold:  10,   score: +1, note: "이익 성장"}
      - {threshold:   0,   score:  0, note: "보합"}
      - {threshold: -20,   score: -1, note: "이익 감소"}
      - {threshold: -9999, score: -2, note: "이익 급감"}

  debt_to_equity:
    direction: lower_better
    null_behavior: skip
    tiers:
      - {threshold:   50, score: +1, note: "보수적 레버리지"}
      - {threshold:  100, score:  0, note: "보통"}
      - {threshold:  200, score: -1, note: "고레버리지"}
      - {threshold: 9999, score: -2, note: "과다 차입"}

# Sum of metric scores → channel direction/strength
# (score range roughly [-12, +11] with all 6 metrics scoring)
aggregation:
  bull_strong:  6      # total >= 6
  bull_medium:  3      # 3 <= total < 6
  bull_weak:    1      # 1 <= total < 3
  bear_weak:   -1      # -3 < total <= -1
  bear_medium: -3      # -6 < total <= -3
  bear_strong: -6      # total <= -6
  # 0 → neutral
```

- [ ] **Step 2: Verify YAML parses**

```bash
$PY -c "import yaml; d=yaml.safe_load(open('$SKILL_DIR/references/fundamentals-rubric.yml')); print(len(d['metrics']), 'metrics'); print('agg keys:', list(d['aggregation'].keys()))"
```

Expected output: `6 metrics` and 6 aggregation keys.

- [ ] **Step 3: Commit**

```bash
git -C $SKILL_DIR add references/fundamentals-rubric.yml
git -C $SKILL_DIR commit -m "feat(rubric): add default deterministic fundamentals rubric"
```

---

## Task 3: TDD `scripts/score_fundamentals.py` — pure scoring logic

**Files:**
- Create: `tests/__init__.py`
- Create: `tests/test_score_fundamentals.py`
- Create: `scripts/score_fundamentals.py`

- [ ] **Step 1: Create empty tests package marker**

```bash
mkdir -p $SKILL_DIR/tests
touch $SKILL_DIR/tests/__init__.py
```

- [ ] **Step 2: Write failing tests**

Create `$SKILL_DIR/tests/test_score_fundamentals.py`:

```python
"""Unit tests for the deterministic fundamentals scorer."""
import sys
from pathlib import Path

import pytest

SKILL_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SKILL_DIR / "scripts"))

from score_fundamentals import (  # noqa: E402
    evaluate_metric,
    aggregate,
    score_ticker,
)


RUBRIC = {
    "metrics": {
        "trailing_pe": {
            "direction": "lower_better",
            "null_behavior": "skip",
            "tiers": [
                {"threshold": 10, "score": 2, "note": "저평가"},
                {"threshold": 15, "score": 1, "note": "적정"},
                {"threshold": 25, "score": 0, "note": "보통"},
                {"threshold": 40, "score": -1, "note": "고평가"},
                {"threshold": 9999, "score": -2, "note": "거품"},
            ],
        },
        "roe_pct": {
            "direction": "higher_better",
            "null_behavior": "skip",
            "tiers": [
                {"threshold": 20, "score": 2, "note": "탁월"},
                {"threshold": 15, "score": 1, "note": "양호"},
                {"threshold": 8, "score": 0, "note": "보통"},
                {"threshold": 0, "score": -1, "note": "저효율"},
                {"threshold": -9999, "score": -2, "note": "자본잠식"},
            ],
        },
    },
    "aggregation": {
        "bull_strong": 6,
        "bull_medium": 3,
        "bull_weak": 1,
        "bear_weak": -1,
        "bear_medium": -3,
        "bear_strong": -6,
    },
}


# ---- evaluate_metric: lower_better ----

def test_lower_better_picks_first_matching_tier():
    """PER 5 matches tier threshold 10 with score +2."""
    spec = RUBRIC["metrics"]["trailing_pe"]
    out = evaluate_metric(5.0, spec)
    assert out["score"] == 2
    assert out["tier_note"] == "저평가"


def test_lower_better_picks_middle_tier():
    """PER 12 skips 10, matches 15 with +1."""
    spec = RUBRIC["metrics"]["trailing_pe"]
    out = evaluate_metric(12.0, spec)
    assert out["score"] == 1


def test_lower_better_picks_worst_tier():
    """PER 200 falls to worst tier (9999, -2)."""
    spec = RUBRIC["metrics"]["trailing_pe"]
    out = evaluate_metric(200.0, spec)
    assert out["score"] == -2


# ---- evaluate_metric: higher_better ----

def test_higher_better_picks_top_tier():
    """ROE 25 matches >=20 with +2."""
    spec = RUBRIC["metrics"]["roe_pct"]
    out = evaluate_metric(25.0, spec)
    assert out["score"] == 2


def test_higher_better_picks_middle_tier():
    """ROE 10 skips 20 and 15, matches 8 with 0."""
    spec = RUBRIC["metrics"]["roe_pct"]
    out = evaluate_metric(10.0, spec)
    assert out["score"] == 0


def test_higher_better_negative_value():
    """ROE -5 matches -9999 tier with -2."""
    spec = RUBRIC["metrics"]["roe_pct"]
    out = evaluate_metric(-5.0, spec)
    assert out["score"] == -2


# ---- null handling ----

def test_null_value_returns_skip():
    """None value with skip → no score, returns skip marker."""
    spec = RUBRIC["metrics"]["trailing_pe"]
    out = evaluate_metric(None, spec)
    assert out["skipped"] is True
    assert out["score"] is None


# ---- aggregate ----

def test_aggregate_bull_strong():
    assert aggregate(7, RUBRIC["aggregation"]) == ("bull", "strong")


def test_aggregate_bull_medium():
    assert aggregate(4, RUBRIC["aggregation"]) == ("bull", "medium")


def test_aggregate_bull_weak():
    assert aggregate(1, RUBRIC["aggregation"]) == ("bull", "weak")


def test_aggregate_neutral_zero():
    assert aggregate(0, RUBRIC["aggregation"]) == ("neutral", "weak")


def test_aggregate_bear_weak():
    assert aggregate(-2, RUBRIC["aggregation"]) == ("bear", "weak")


def test_aggregate_bear_strong():
    assert aggregate(-7, RUBRIC["aggregation"]) == ("bear", "strong")


# ---- score_ticker integration ----

def test_score_ticker_full_pipeline():
    funda = {
        "ticker": "X",
        "trailing_pe": 5.3,
        "roe_pct": 18.86,
    }
    result = score_ticker(funda, RUBRIC)
    assert result["ticker"] == "X"
    # PE 5.3 → +2, ROE 18.86 → +1, total +3 → bull medium
    assert result["total_score"] == 3
    assert result["direction"] == "bull"
    assert result["strength"] == "medium"
    assert len(result["breakdown"]) == 2
    assert result["skipped_metrics"] == []


def test_score_ticker_skips_null_metrics():
    funda = {"ticker": "X", "trailing_pe": None, "roe_pct": 18.86}
    result = score_ticker(funda, RUBRIC)
    assert result["total_score"] == 1  # only ROE counted (+1)
    assert len(result["breakdown"]) == 1
    assert result["skipped_metrics"] == [{"metric": "trailing_pe", "reason": "null_value"}]


def test_score_ticker_all_null_returns_neutral():
    funda = {"ticker": "X"}
    result = score_ticker(funda, RUBRIC)
    assert result["total_score"] == 0
    assert result["direction"] == "neutral"
    assert result["strength"] == "weak"
```

- [ ] **Step 3: Run tests and verify they fail with ImportError**

```bash
cd $SKILL_DIR && .venv/bin/pytest tests/test_score_fundamentals.py -x 2>&1 | tail -20
```

Expected: `ModuleNotFoundError: No module named 'score_fundamentals'`.

- [ ] **Step 4: Implement `scripts/score_fundamentals.py`**

Create `$SKILL_DIR/scripts/score_fundamentals.py`:

```python
#!/usr/bin/env python3
"""
Deterministic fundamentals scorer.

Reads a fundamentals JSON (output of fetch_fundamentals.py) and a rubric YAML,
emits a per-ticker score JSON with direction/strength derived from metric tier
scores summed against aggregation thresholds.

Usage:
  python score_fundamentals.py <ticker1> [<ticker2> ...] \\
      --data <session_dir>/data \\
      --rubric <path-to-fundamentals-rubric.yml> \\
      --out <session_dir>/scores

Output schema per ticker (<out>/<ticker>-rubric.json):
  {
    "ticker": "005930.KS",
    "total_score": 7,
    "direction": "bull",
    "strength": "strong",
    "breakdown": [
      {"metric": "trailing_pe", "value": 5.3, "score": 2, "tier_note": "저평가"},
      ...
    ],
    "skipped_metrics": [{"metric": "...", "reason": "null_value"}]
  }
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    yaml = None


def evaluate_metric(value, spec: dict) -> dict:
    """Evaluate one metric value against its tier spec.

    Returns a dict with either score+tier_note or skipped=True.
    """
    if value is None:
        if spec.get("null_behavior", "skip") == "skip":
            return {"skipped": True, "score": None, "tier_note": None}
        # default fallthrough: treat as neutral
        return {"skipped": False, "score": 0, "tier_note": "null_neutral"}

    direction = spec["direction"]
    tiers = spec["tiers"]

    for tier in tiers:
        thr = tier["threshold"]
        if direction == "lower_better":
            if value <= thr:
                return {
                    "skipped": False,
                    "score": int(tier["score"]),
                    "tier_note": tier.get("note", ""),
                }
        else:  # higher_better
            if value >= thr:
                return {
                    "skipped": False,
                    "score": int(tier["score"]),
                    "tier_note": tier.get("note", ""),
                }

    # No tier matched (e.g., all thresholds passed). Last tier as fallback.
    last = tiers[-1]
    return {
        "skipped": False,
        "score": int(last["score"]),
        "tier_note": last.get("note", ""),
    }


def aggregate(total: int, agg_spec: dict) -> tuple[str, str]:
    """Sum → (direction, strength)."""
    if total >= agg_spec["bull_strong"]:
        return "bull", "strong"
    if total >= agg_spec["bull_medium"]:
        return "bull", "medium"
    if total >= agg_spec["bull_weak"]:
        return "bull", "weak"
    if total <= agg_spec["bear_strong"]:
        return "bear", "strong"
    if total <= agg_spec["bear_medium"]:
        return "bear", "medium"
    if total <= agg_spec["bear_weak"]:
        return "bear", "weak"
    return "neutral", "weak"


def score_ticker(funda: dict, rubric: dict) -> dict:
    """Score one fundamentals dict against the rubric."""
    breakdown = []
    skipped = []
    total = 0

    for metric_name, spec in rubric["metrics"].items():
        value = funda.get(metric_name)
        result = evaluate_metric(value, spec)
        if result.get("skipped"):
            skipped.append({"metric": metric_name, "reason": "null_value"})
            continue
        breakdown.append({
            "metric": metric_name,
            "value": value,
            "score": result["score"],
            "tier_note": result["tier_note"],
        })
        total += result["score"]

    direction, strength = aggregate(total, rubric["aggregation"])
    return {
        "ticker": funda.get("ticker"),
        "total_score": total,
        "direction": direction,
        "strength": strength,
        "breakdown": breakdown,
        "skipped_metrics": skipped,
    }


def load_yaml(p: Path) -> dict:
    if yaml is None:
        raise RuntimeError("PyYAML not installed")
    return yaml.safe_load(p.read_text())


def main():
    ap = argparse.ArgumentParser(description="Score fundamentals deterministically")
    ap.add_argument("tickers", nargs="+")
    ap.add_argument("--data", required=True, help="dir with <ticker>-fundamentals.json")
    ap.add_argument("--rubric", required=True, help="rubric yaml path")
    ap.add_argument("--out", required=True, help="output dir for score json")
    args = ap.parse_args()

    data_dir = Path(args.data).expanduser()
    out_dir = Path(args.out).expanduser()
    out_dir.mkdir(parents=True, exist_ok=True)
    rubric = load_yaml(Path(args.rubric).expanduser())

    ok = 0
    results = []
    for t in args.tickers:
        f = data_dir / f"{t}-fundamentals.json"
        if not f.exists():
            print(f"ERR {t}: missing {f}", file=sys.stderr)
            results.append({"ticker": t, "status": "error", "error": "fundamentals file missing"})
            continue
        try:
            funda = json.loads(f.read_text())
            scored = score_ticker(funda, rubric)
            (out_dir / f"{t}-rubric.json").write_text(
                json.dumps(scored, ensure_ascii=False, indent=2)
            )
            results.append({"ticker": t, "status": "ok",
                            "total": scored["total_score"],
                            "verdict": f"{scored['direction']} {scored['strength']}"})
            ok += 1
            print(f"OK  {t}: total={scored['total_score']:+d} "
                  f"({scored['direction']} {scored['strength']})", file=sys.stderr)
        except Exception as e:
            results.append({"ticker": t, "status": "error", "error": str(e)})
            print(f"ERR {t}: {e}", file=sys.stderr)

    print(json.dumps({"total": len(args.tickers), "ok": ok, "results": results},
                     ensure_ascii=False, indent=2))
    sys.exit(0 if ok > 0 else 1)


if __name__ == "__main__":
    main()
```

- [ ] **Step 5: Run tests and verify they pass**

```bash
cd $SKILL_DIR && .venv/bin/pytest tests/test_score_fundamentals.py -v 2>&1 | tail -25
```

Expected: all 14 tests pass.

- [ ] **Step 6: Commit**

```bash
git -C $SKILL_DIR add tests/__init__.py tests/test_score_fundamentals.py scripts/score_fundamentals.py
git -C $SKILL_DIR commit -m "feat(scoring): add deterministic fundamentals rubric scorer with tests"
```

---

## Task 4: Extend `scripts/calc_indicators.py` with `--timeframe` flag

**Files:**
- Modify: `scripts/calc_indicators.py`
- Create: `tests/test_calc_indicators.py`

- [ ] **Step 1: Write failing test for intraday timeframe**

Create `$SKILL_DIR/tests/test_calc_indicators.py`:

```python
"""Smoke tests for the indicator computation extension (intraday timeframe)."""
import json
import sys
from pathlib import Path

import pytest

SKILL_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SKILL_DIR / "scripts"))

from calc_indicators import process  # noqa: E402


def _synthetic_payload(num_bars: int, base: float = 100.0) -> dict:
    """Build a fake OHLCV payload with a gentle uptrend."""
    data = []
    for i in range(num_bars):
        close = base + i * 0.5
        data.append({
            "date": f"2026-01-{(i % 28) + 1:02d}",
            "open": close - 0.2, "high": close + 0.3,
            "low": close - 0.3, "close": close, "volume": 1000 + i,
        })
    return {"market": "US", "currency": "USD", "data": data}


def test_intraday_skips_sma200(tmp_path):
    """Intraday timeframe must compute SMA20/60 but skip SMA200."""
    in_dir = tmp_path
    payload = _synthetic_payload(120)  # < 200 bars; daily would partially fail
    (in_dir / "TEST-intraday.json").write_text(json.dumps(payload))

    result = process("TEST", in_dir, in_dir, timeframe="intraday")

    out_path = in_dir / "TEST-indicators-intraday.json"
    assert out_path.exists()
    data = json.loads(out_path.read_text())
    ind = data["indicators"]
    assert ind["sma20"] is not None
    assert ind["sma60"] is not None
    assert "sma200" not in ind or ind["sma200"] is None
    assert ind["sma50"] is None or "sma50" not in ind


def test_daily_keeps_sma200(tmp_path):
    """Daily timeframe (existing behavior) keeps SMA50/200."""
    in_dir = tmp_path
    payload = _synthetic_payload(250)
    (in_dir / "TEST-ohlcv.json").write_text(json.dumps(payload))

    result = process("TEST", in_dir, in_dir, timeframe="daily")

    out_path = in_dir / "TEST-indicators.json"
    assert out_path.exists()
    data = json.loads(out_path.read_text())
    ind = data["indicators"]
    assert ind["sma20"] is not None
    assert ind["sma50"] is not None
    assert ind["sma200"] is not None
```

- [ ] **Step 2: Run the test and verify it fails**

```bash
cd $SKILL_DIR && .venv/bin/pytest tests/test_calc_indicators.py -x 2>&1 | tail -15
```

Expected: TypeError or AssertionError because `process()` doesn't accept `timeframe`.

- [ ] **Step 3: Modify `scripts/calc_indicators.py` — add `--timeframe` flag and intraday branch**

Edit `$SKILL_DIR/scripts/calc_indicators.py`. Replace the `process` function signature and body, and the `main()` argparse, with the version below. Keep the helper functions (`ema`, `sma`, `rsi`, `macd`, `bollinger`, `label_rsi`, `label_macd`, `detect_signals`) unchanged.

Replace function `process(ticker, in_dir, out_dir)` with:

```python
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
        indicators["sma60"] = round(sma_short[last], 4) if sma_short[last] is not None else None

    recent_5 = []
    for i in range(max(0, len(rows) - 5), len(rows)):
        recent_5.append({
            "date": rows[i]["date"],
            "close": rows[i]["close"],
            "rsi14": round(rsi_v[i], 2) if rsi_v[i] is not None else None,
            "macd_hist": round(macd_hist[i], 4),
        })

    # Signal detection: pick the right MA pair for the timeframe
    if timeframe == "daily":
        signals = detect_signals(closes, rsi_v, sma50, sma200, macd_hist)
    else:
        signals = detect_signals(closes, rsi_v, sma20, sma_short, macd_hist)

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
```

Then in `main()`, replace the argparse block and the call to `process` with:

```python
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
```

- [ ] **Step 4: Run tests and verify they pass**

```bash
cd $SKILL_DIR && .venv/bin/pytest tests/test_calc_indicators.py -v 2>&1 | tail -10
```

Expected: both tests pass.

- [ ] **Step 5: Verify legacy daily invocation still works**

```bash
cd $SKILL_DIR && .venv/bin/pytest tests/ -v 2>&1 | tail -25
```

Expected: all tests in both files pass.

- [ ] **Step 6: Commit**

```bash
git -C $SKILL_DIR add scripts/calc_indicators.py tests/test_calc_indicators.py
git -C $SKILL_DIR commit -m "feat(indicators): add --timeframe intraday with SMA20/60 (skip SMA200)"
```

---

## Task 5: Create `scripts/fetch_intraday.py`

**Files:**
- Create: `scripts/fetch_intraday.py`

- [ ] **Step 1: Write the fetcher**

Create `$SKILL_DIR/scripts/fetch_intraday.py`:

```python
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
    t = ticker.strip().upper()
    if KRX_CODE.match(t):
        code = t.split(".")[0]
        suffix = t.split(".")[1] if "." in t else None
        return "KRX", f"{code}.{suffix or 'KS'}", "KRW"
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
            if fetched.startswith(date.today().isoformat()):
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
```

- [ ] **Step 2: Smoke test against a live ticker (NVDA)**

```bash
cd $SKILL_DIR && .venv/bin/python3 scripts/fetch_intraday.py NVDA --out /tmp/intraday-smoke 2>&1 | tail -5
ls -la /tmp/intraday-smoke/NVDA-intraday.json
.venv/bin/python3 -c "import json; d=json.load(open('/tmp/intraday-smoke/NVDA-intraday.json')); print('rows:', len(d['data']), 'first:', d['data'][0]['date'], 'last:', d['data'][-1]['date'])"
```

Expected: file exists, > 100 rows, dates in 15-minute granularity.

- [ ] **Step 3: Commit**

```bash
git -C $SKILL_DIR add scripts/fetch_intraday.py
git -C $SKILL_DIR commit -m "feat(fetch): add fetch_intraday.py for 15m yfinance bars"
```

---

## Task 6: Create `scripts/render_chart.py`

**Files:**
- Create: `scripts/render_chart.py`

- [ ] **Step 1: Write the chart renderer**

Create `$SKILL_DIR/scripts/render_chart.py`:

```python
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
import sys
from pathlib import Path


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
            cross_markers: list[dict] | None = None):
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

    mpf.plot(df, type="candle", style="yahoo", volume=True,
             addplot=addplots if addplots else None,
             title=title, savefig=dict(fname=str(out_path), dpi=100, bbox_inches="tight"),
             figratio=(12, 8), figscale=1.0)


def render_daily(ticker: str, data_dir: Path, out_dir: Path) -> Path:
    df = _load_df(data_dir / f"{ticker}-ohlcv.json")
    # Read indicators for cross markers
    cross_markers = []
    ind_path = data_dir / f"{ticker}-indicators.json"
    if ind_path.exists():
        ind = json.loads(ind_path.read_text())
        for s in ind.get("signals", []):
            if s == "golden_cross":
                cross_markers.append({"date": ind["as_of"], "kind": "bull"})
            elif s == "death_cross":
                cross_markers.append({"date": ind["as_of"], "kind": "bear"})
            elif s.startswith("macd_bullish_cross"):
                cross_markers.append({"date": ind["as_of"], "kind": "bull"})
            elif s.startswith("macd_bearish_cross"):
                cross_markers.append({"date": ind["as_of"], "kind": "bear"})
    out_path = out_dir / f"{ticker}-daily.png"
    _render(df, [20, 50, 200], f"{ticker} daily as of {df.index[-1].date()}",
            out_path, cross_markers=cross_markers)
    return out_path


def render_intraday(ticker: str, data_dir: Path, out_dir: Path) -> Path:
    df = _load_df(data_dir / f"{ticker}-intraday.json")
    cross_markers = []
    ind_path = data_dir / f"{ticker}-indicators-intraday.json"
    if ind_path.exists():
        ind = json.loads(ind_path.read_text())
        for s in ind.get("signals", []):
            if s == "golden_cross":
                cross_markers.append({"date": ind["as_of"], "kind": "bull"})
            elif s == "death_cross":
                cross_markers.append({"date": ind["as_of"], "kind": "bear"})
    out_path = out_dir / f"{ticker}-intraday.png"
    _render(df, [20, 60], f"{ticker} 15m as of {df.index[-1]}",
            out_path, cross_markers=cross_markers)
    return out_path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("tickers", nargs="+")
    ap.add_argument("--data", required=True)
    ap.add_argument("--out", required=True)
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
        if "daily" in per or "intraday" in per:
            ok += 1
        results.append(per)
        print(f"{t}: daily={'ok' if 'daily' in per else 'fail'} "
              f"intraday={'ok' if 'intraday' in per else 'fail'}", file=sys.stderr)

    print(json.dumps({"total": len(args.tickers), "ok": ok, "results": results},
                     ensure_ascii=False, indent=2))
    sys.exit(0 if ok > 0 else 1)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Smoke test (end-to-end one ticker) — fetch + indicators + render**

```bash
TMP=/tmp/chart-smoke
mkdir -p $TMP
$PY $SKILL_DIR/scripts/fetch_ohlcv.py NVDA --out $TMP
$PY $SKILL_DIR/scripts/fetch_intraday.py NVDA --out $TMP
$PY $SKILL_DIR/scripts/calc_indicators.py NVDA --in $TMP --timeframe daily
$PY $SKILL_DIR/scripts/calc_indicators.py NVDA --in $TMP --timeframe intraday
$PY $SKILL_DIR/scripts/render_chart.py NVDA --data $TMP --out $TMP/charts
ls -la $TMP/charts/
```

Expected: both `NVDA-daily.png` and `NVDA-intraday.png` exist, > 50 KB each.

- [ ] **Step 3: Commit**

```bash
git -C $SKILL_DIR add scripts/render_chart.py
git -C $SKILL_DIR commit -m "feat(chart): render dual-timeframe candlestick PNGs with SMA + volume"
```

---

## Task 7: Create `references/chart-patterns.md`

**Files:**
- Create: `references/chart-patterns.md`

- [ ] **Step 1: Write the Core 7 pattern reference**

Create `$SKILL_DIR/references/chart-patterns.md`. This is a long static document — write the file with all 7 patterns following the structure below for each (ASCII shape, identification, implication, false-positive guards, strength scoring). Use the spec §6 catalogue as the source of truth.

Here is the complete file content:

````markdown
# Core 7 Chart Patterns — Reference Vocabulary

The chart agent uses this document as its pattern vocabulary. Each pattern has
identification criteria, implications, false-positive guards, and strength scoring.

**Detection split:**
- Patterns 1-2 (MA cross, MACD cross): auto-detected by `calc_indicators.py` and surfaced
  as `signals[]`. Agent treats them as **given**.
- Patterns 3-7 (shape/candle): agent interprets from OHLCV + chart PNG using this vocabulary.

Agent output field `patterns_detected` lists matched patterns with `name`, `timeframe`,
`as_of`, `detection_method`, `confidence`, and (for interpretation) a `context` string.

---

## 1. Golden Cross / Death Cross (automatic)

### Shape
```
   SMA-fast (e.g., SMA50 daily, SMA20 intraday)
       ╱
      ╱     ← crosses above (golden) or below (death)
─────╳──────
    ╱
   SMA-slow (SMA200 daily, SMA60 intraday)
```

### Identification (auto)
- Daily: `sma50 > sma200` (golden) or `sma50 < sma200` (death)
- Intraday: `sma20 > sma60` (golden) or `sma20 < sma60` (death)
- Detected in `signals[]` as `golden_cross` / `death_cross`

### Implication
- **Golden cross**: trend confirmation bullish; works best when price is also above both MAs
- **Death cross**: trend confirmation bearish

### False-positive guards
- Whipsaws on flat markets — if SMAs cross repeatedly within 10 bars, treat as noise
- Daily golden cross alone is not a buy trigger; needs alignment with price-above-MA + volume

### Strength scoring
- weak: cross just formed (< 5 bars old), no volume confirmation
- medium: cross 5-30 bars old, price holding above (golden) or below (death) the slow MA
- strong: cross 5-60 bars old + price above all MAs + rising MACD histogram

---

## 2. MACD Bullish / Bearish Cross (automatic)

### Shape
```
MACD histogram
   ▲▲▲                  ← positive (bullish)
─────────  ← zero
   ▼▼▼                  ← negative (bearish)
```

### Identification (auto)
- `macd_hist` flips sign within last 5 bars
- Detected as `macd_bullish_cross_{n}d_ago` / `macd_bearish_cross_{n}d_ago`

### Implication
- Momentum reversal signal — earlier than MA crosses but noisier

### False-positive guards
- Don't trust isolated MACD crosses against the broader MA trend (e.g., bullish MACD cross
  while price is in death-cross territory)

### Strength scoring
- weak: cross just formed, histogram still small
- medium: cross + histogram accelerating in cross direction
- strong: cross + price-above-SMA50 (bullish) or price-below-SMA50 (bearish) alignment

---

## 3. Head and Shoulders / Inverse Head and Shoulders (agent interpretation)

### Shape (regular — bearish top)
```
              Head
              ╱╲
   Shoulder  ╱  ╲  Shoulder
      ╱╲   ╱    ╲   ╱╲
─────╱──╲─╱──────╲─╱──╲────  ← neckline
                  ╲╱
```

### Identification
- Three peaks: left shoulder, higher head, right shoulder (approximately equal to left)
- Two troughs between peaks form a neckline (roughly horizontal or slightly sloping)
- Volume typically declining from left to right
- Pattern completes when price closes below the neckline

### Inverse (bullish bottom)
- Same shape mirrored — three troughs, middle trough is lowest

### Implication
- Bearish reversal (regular) — target = head height projected down from neckline
- Bullish reversal (inverse) — target = head depth projected up from neckline

### Absolute false-positive guards
- A pattern is NOT H&S if right shoulder is materially higher than left (then it's a continuation)
- A pattern is NOT H&S without three distinct peaks
- Random triple touches in a sideways range are NOT H&S — needs a prior trend
- Do not call H&S on intraday timeframes < 1h — too noisy

### Strength scoring
- weak: pattern still forming (right shoulder in progress), neckline not yet broken
- medium: neckline broken once with low volume
- strong: neckline broken with volume spike + pullback test of neckline holding

---

## 4. Double Top / Double Bottom (agent interpretation)

### Shape (double top)
```
   Peak 1       Peak 2
    ╱╲           ╱╲
   ╱  ╲   ╱╲   ╱  ╲
──╱────╲─╱──╲─╱────╲──  ← neckline (intervening trough)
                   ╲
```

### Identification
- Two roughly equal peaks (within 3% in price)
- Separated by 10-50 bars typically
- Intervening trough defines the neckline
- Volume usually lower on the second peak

### Implication
- Bearish reversal (double top) — target = peak height to neckline projected down
- Bullish reversal (double bottom) — mirror

### False-positive guards
- Peaks more than 5% apart are NOT a double top
- Peaks within 5 bars of each other are just a single wide top, not a double
- A double top in an established downtrend is just a relief rally — needs prior uptrend

### Strength scoring
- weak: second peak forming
- medium: neckline broken
- strong: neckline broken with volume + pullback to neckline holding

---

## 5. Hammer / Inverted Hammer (agent interpretation)

### Shape (hammer)
```
   ┃              open or close (small body at top)
  ┃┃             
   ┃             
   ┃             
   ┃           ← long lower shadow
   ┃           
   ┃           ← low
```

### Identification
- Body (`|open - close|`) ≤ 30% of total `high - low` range
- Lower shadow ≥ 2× body length
- Upper shadow ≤ 10% of body length (almost none)
- Must form after a clear preceding downtrend (last 5-10 bars trending down)

### Inverted hammer
- Same body proportions but the LONG shadow is on TOP
- Appears at bottom of downtrend, but needs confirmation candle next bar

### Implication
- **Bullish reversal signal** — buyers stepped in at the low

### Absolute false-positive guards
- Same shape in an uptrend is NOT a hammer — it's just intra-bar noise
- Same shape after sideways/range is NOT a hammer — needs a clear preceding downtrend
- A single hammer is weak — confirmation candle (next bar bullish) is required for medium+

### Strength scoring
- weak: hammer alone, no confirmation
- medium: hammer + next bar bullish (close > hammer close)
- strong: hammer + next bar bullish + volume spike + occurs at major support (SMA50/200)

---

## 6. Engulfing — Bullish / Bearish (agent interpretation)

### Shape (bullish engulfing)
```
   Day 1 (red)        Day 2 (green)
       ┃                  ┃
      ┃ ┃                 ┃
       ┃                 ┃ ┃
                          ┃     ← Day 2 body engulfs Day 1 body entirely
```

### Identification
- Two-candle pattern
- Day 1 has a small body in the prior trend direction
- Day 2 has a body that completely engulfs Day 1's body (open lower than Day 1 close, close higher than Day 1 open — bullish)
- Bearish engulfing: mirror

### Implication
- Bullish engulfing after downtrend = reversal
- Bearish engulfing after uptrend = reversal

### False-positive guards
- Engulfing in a sideways market = noise
- Day 2 must engulf the BODY, not just the wick — wick overlap is not engulfing
- Body size of Day 2 should be at least 1.5× Day 1 (otherwise low conviction)

### Strength scoring
- weak: engulfing without volume increase
- medium: engulfing + Day 2 volume > Day 1 volume
- strong: engulfing + volume spike + occurs at SMA or pattern boundary

---

## 7. Doji — Standard / Dragonfly / Gravestone / Long-legged (agent interpretation)

### Shapes
```
Standard:        Dragonfly:      Gravestone:     Long-legged:
                                    ┃                  ┃
   ┃                                ┃                  ┃
 ──┼──         ──┼──             ──┼──              ──┼──
   ┃                ┃                                  ┃
                    ┃                                  ┃
                                                        
```

### Identification
- Body is extremely small (`|open - close|` ≤ 5% of total range)
- Standard: small body in the middle, balanced shadows
- Dragonfly: small body at top, long lower shadow only
- Gravestone: small body at bottom, long upper shadow only
- Long-legged: small body in middle, both shadows long

### Implication
- **Indecision signal** — neither buyers nor sellers won the session
- Dragonfly at bottom of downtrend = potential bullish reversal
- Gravestone at top of uptrend = potential bearish reversal
- Standard / long-legged = trend pause / potential reversal pending confirmation

### False-positive guards
- A doji in a low-volume session is just noise — needs context (volume + location)
- Multiple consecutive dojis = trendless market, not a reversal signal

### Strength scoring
- weak: doji alone in any context
- medium: dragonfly at major support OR gravestone at major resistance
- strong: doji + next bar confirms the implied direction with volume

---

## Output schema reminder

Chart agent emits patterns like this in its JSON output:

```json
{
  "patterns_detected": [
    {
      "name": "golden_cross",            // matches a "## N. Name" header above
      "timeframe": "daily" | "15m",
      "as_of": "2026-05-19" | "2026-05-20T14:30",
      "detection_method": "automatic" | "agent_interpretation",
      "confidence": "high" | "medium" | "low",
      "context": "직전 5봉 -1.8% 하락 후 ..."   // required for agent_interpretation
    }
  ]
}
```

If no patterns match cleanly, emit `"patterns_detected": []`. Do not invent patterns to
fill the array.
````

- [ ] **Step 2: Verify file readable + non-empty**

```bash
wc -l $SKILL_DIR/references/chart-patterns.md
head -5 $SKILL_DIR/references/chart-patterns.md
```

Expected: > 200 lines, header shows "# Core 7 Chart Patterns".

- [ ] **Step 3: Commit**

```bash
git -C $SKILL_DIR add references/chart-patterns.md
git -C $SKILL_DIR commit -m "docs(patterns): add Core 7 chart pattern reference vocabulary"
```

---

## Task 8: Rewrite `references/agent-prompts/fundamentals-agent.md` — narrative-only contract

**Files:**
- Modify: `references/agent-prompts/fundamentals-agent.md`

- [ ] **Step 1: Replace the file contents with the narrative-only version**

Overwrite `$SKILL_DIR/references/agent-prompts/fundamentals-agent.md` with the following complete file:

````markdown
# Fundamentals Channel Subagent Prompt (narrative-only contract)

You are a fundamental analyst providing **narrative context** for a single equity.

**IMPORTANT CONTRACT** — your `direction` and `strength` are NOT chosen by you. They are computed
by a deterministic rubric. Your job is to copy them from the score file and write narrative.

## Inputs

- `ticker`: canonical symbol (e.g., `005930.KS`, `NVDA`)
- `market`: `KRX` | `US`
- `fundamentals_path`: JSON at `/tmp/portfolio-session-XXX/data/{ticker}-fundamentals.json`
- `rubric_score_path`: JSON at `/tmp/portfolio-session-XXX/scores/{ticker}-rubric.json`
- `output_path`: where to write your JSON

## Schema of `rubric_score_path`

```json
{
  "ticker": "005930.KS",
  "total_score": 7,
  "direction": "bull",        // ← copy this verbatim
  "strength": "strong",        // ← copy this verbatim
  "breakdown": [
    {"metric": "trailing_pe", "value": 5.3, "score": 2, "tier_note": "저평가"},
    {"metric": "price_to_book", "value": 1.05, "score": 1, "tier_note": "저평가"},
    {"metric": "roe_pct", "value": 18.86, "score": 1, "tier_note": "양호"},
    {"metric": "revenue_growth_yoy_pct", "value": 69.2, "score": 2},
    {"metric": "earnings_growth_yoy_pct", "value": 492.1, "score": 2},
    {"metric": "debt_to_equity", "value": 25.4, "score": 1}
  ],
  "skipped_metrics": []
}
```

## Your job

1. **Read both files** — fundamentals (raw values) and rubric score (deterministic verdict).
2. **Copy** `direction` and `strength` verbatim from rubric — **DO NOT OVERRIDE**.
3. **Add narrative**: explain sector context, red flags, and what the rubric score *means*
   for this specific company.

## Sector context examples

The rubric does not adjust for sector. Banks, utilities, and REITs naturally have low PER (5-10)
and your narrative should explain when the deterministic +2 "저평가" is actually sector-normal
and not real undervaluation. Conversely, high-growth tech with PER 50 might be deterministically
-2 "거품" but justified by 100%+ revenue growth.

- 반도체/배터리/자동차 (cyclicals): high PER OK during cycle bottom; treat rubric -1/-2 with caveat
- 은행/보험/통신 (utilities/financials): low PER is sector normal; rubric +2 not a real signal alone
- 고성장 테크 (AI, biotech, cloud): negative EPS often — PER skipped, revenue growth carries signal
- REIT / dividend payers: dividend yield + payout ratio matter more than PER

## Output JSON

Write to `output_path`:

```json
{
  "ticker": "005930.KS",
  "channel": "fundamentals",
  "direction": "bull",           // COPIED from rubric — must match exactly
  "strength": "strong",          // COPIED from rubric — must match exactly
  "rubric_total_score": 7,       // COPIED from rubric — auditable
  "key_drivers": [
    "forward_pe 5.3 — 메모리 사이클 회복 기대",
    "ROE 18.86% — 자본효율 양호",
    "revenue YoY +69.2%, earnings YoY +492.1% — 어닝 모멘텀 폭발적"
  ],
  "red_flags": [
    "메모리 가격 사이클 정점 우려",
    "지정학적 리스크 (중국 매출 비중)"
  ],
  "sector_context": "반도체 사이클주 — 현재 cycle bottom 진입 단계. 저PER이 진짜 저평가일 가능성 높음.",
  "reasoning_kr": "Rubric +7 (bull strong). PER 5.3 / PBR 1.05 / ROE 18.86%로 핵심 지표 모두 통과. 반도체 사이클 회복 기대를 시장이 이미 반영 중이지만 어닝 모멘텀이 워낙 강해 추가 상승 여력 존재. 단, 메모리 가격 사이클 정점 우려는 1-2분기 내 모니터링 필요.",
  "as_of": "2026-05-20"
}
```

## Constraints

- **Direction/strength must match rubric exactly.** If you disagree, voice it in `red_flags` —
  but the score wins.
- **Cite specific numbers** from the breakdown in `key_drivers`.
- **Sector context is required** when the rubric verdict is strong (|score| >= 6). Without
  sector framing, an extreme rubric score may mislead.
- **No forward forecasts.** Stick to reported numbers + sector benchmarks.

## Self-check

- Did I copy direction/strength from rubric exactly (no override)?
- Did I quote at least 3 metrics from `breakdown`?
- Did I explain sector context if rubric verdict is strong?
- Are red flags included even when direction is bull?
````

- [ ] **Step 2: Verify the file**

```bash
head -10 $SKILL_DIR/references/agent-prompts/fundamentals-agent.md
grep -c "COPIED from rubric" $SKILL_DIR/references/agent-prompts/fundamentals-agent.md
```

Expected: file starts with the new header; grep finds at least 2 mentions.

- [ ] **Step 3: Commit**

```bash
git -C $SKILL_DIR add references/agent-prompts/fundamentals-agent.md
git -C $SKILL_DIR commit -m "feat(agent): make fundamentals agent narrative-only; rubric drives verdict"
```

---

## Task 9: Extend `references/agent-prompts/chart-agent.md` — intraday + patterns

**Files:**
- Modify: `references/agent-prompts/chart-agent.md`

- [ ] **Step 1: Replace the file with the extended version**

Overwrite `$SKILL_DIR/references/agent-prompts/chart-agent.md` with the following:

````markdown
# Chart Channel Subagent Prompt (dual-timeframe + patterns)

You are a technical analyst evaluating **price action + indicators + patterns** for a single equity
across **two timeframes**: daily (250d) and 15-minute (30d).

## Inputs

- `ticker`: canonical symbol
- `daily_indicators_path`: `/tmp/portfolio-session-XXX/data/{ticker}-indicators.json`
- `intraday_indicators_path`: `/tmp/portfolio-session-XXX/data/{ticker}-indicators-intraday.json`
- `daily_ohlcv_path`: `/tmp/portfolio-session-XXX/data/{ticker}-ohlcv.json` (for candle pattern inspection)
- `intraday_ohlcv_path`: `/tmp/portfolio-session-XXX/data/{ticker}-intraday.json`
- `daily_chart_png`: `/tmp/portfolio-session-XXX/charts/{ticker}-daily.png` (reference — for the human reviewer)
- `intraday_chart_png`: `/tmp/portfolio-session-XXX/charts/{ticker}-intraday.png` (reference)
- `patterns_reference_path`: skill's `references/chart-patterns.md` — you have already received its full content embedded below
- `output_path`: where to write your JSON

## Embedded patterns reference

The full content of `references/chart-patterns.md` is embedded in this prompt below the INPUTS
section by the orchestrator. Use Core 7 vocabulary exactly — do not invent pattern names.

## Schema of indicators files

Daily (`{ticker}-indicators.json`) — has SMA20/50/200:
```json
{
  "ticker": "005930.KS", "as_of": "2026-05-19", "close": 75200,
  "currency": "KRW", "market": "KRX", "bars_used": 250, "timeframe": "daily",
  "indicators": {
    "rsi14": 58.3, "rsi14_label": "bullish",
    "macd": 142.3, "macd_signal": 110.1, "macd_hist": 32.2,
    "macd_label": "bullish_cross_3d_ago",
    "sma20": 73500, "sma50": 71200, "sma200": 68900,
    "bb_mid": 73500, "bb_upper": 76200, "bb_lower": 70800, "bb_position": 0.81
  },
  "recent_5": [...],
  "signals": ["price_above_sma50", "golden_cross", "macd_bullish_cross_3d_ago"]
}
```

Intraday (`{ticker}-indicators-intraday.json`) — has SMA20/60 instead:
```json
{
  "ticker": "005930.KS", "as_of": "2026-05-20T14:30:00", "close": 75450,
  "timeframe": "intraday",
  "indicators": {
    "rsi14": 62.1, "rsi14_label": "bullish",
    "macd_hist": 8.4, "macd_label": "bullish_trend",
    "sma20": 75100, "sma60": 74600,
    "bb_position": 0.72
  },
  "signals": ["price_above_sma20", "golden_cross", "macd_bullish_trend"]
}
```

## Your job

1. **Read both indicators files** plus a window of recent OHLCV from `*_ohlcv_path` for candle
   pattern inspection. Look at the last 10-15 daily bars for shape patterns (H&S, double top),
   and the last 30-40 15m bars for candle patterns (hammer, engulfing, doji).

2. **Identify patterns using ONLY the Core 7 vocabulary** from `chart-patterns.md`:
   - Auto-detected (already in `signals[]`): golden/death cross, MACD cross → add to `patterns_detected`
     with `detection_method: "automatic"`, `confidence: "high"`
   - Agent interpretation: H&S, double top/bottom, hammer, engulfing, doji → add only if all
     identification criteria in chart-patterns.md are met AND the false-positive guards do not fire

3. **Synthesize direction + strength** using standard TA rules + patterns evidence:

   **Bullish evidence**
   - Price > SMA200 (long-term uptrend)
   - Golden cross (both timeframes alignment is strongest)
   - MACD bullish cross within last 5 bars
   - RSI 50~70 (momentum without overbought)
   - Bullish patterns from chart-patterns.md (hammer, bullish engulfing, inverse H&S, double bottom)

   **Bearish evidence**
   - Price < SMA200
   - Death cross
   - MACD bearish cross
   - RSI < 40 or > 80 with diverging price
   - Bearish patterns (H&S top, bearish engulfing, double top, gravestone doji)

   **Strength rating**
   - `bull strong`: 4+ aligned bullish signals across both timeframes
   - `bull medium`: 2-3 aligned, no contradiction
   - `bull weak`: 1 mildly positive signal or recovery from oversold
   - `bear strong/medium/weak`: mirror with bearish
   - `neutral`: contradictory signals or both timeframes diverge

4. **Identify the most actionable observation**: golden cross? hammer at SMA50? Name it concretely
   in `key_drivers`.

5. **Write `reasoning_kr`**: 2-3 sentences citing both timeframes and any pattern detected.

## Output JSON

```json
{
  "ticker": "005930.KS",
  "channel": "chart",
  "direction": "bull",
  "strength": "strong",
  "key_drivers": [
    "골든 크로스 (일봉 SMA50 71,200 > SMA200 68,900, 65일 경과)",
    "MACD 3거래일 전 양전환 + 히스토그램 가속(+32.2)",
    "15분봉 망치형 (2026-05-20 14:30) — SMA60 지지선 부근",
    "RSI 일봉 58.3 / 15분봉 62.1 — 모멘텀 영역"
  ],
  "caution_signals": [
    "볼린저 상단 위치(0.81) — 단기 76,200 저항 테스트 가능"
  ],
  "key_levels": {
    "support_sma50_daily": 71200,
    "support_sma200_daily": 68900,
    "support_sma60_intraday": 74600,
    "resistance_bb_upper": 76200
  },
  "patterns_detected": [
    {
      "name": "golden_cross",
      "timeframe": "daily",
      "as_of": "2026-03-15",
      "detection_method": "automatic",
      "confidence": "high"
    },
    {
      "name": "macd_bullish_cross",
      "timeframe": "daily",
      "as_of": "2026-05-17",
      "detection_method": "automatic",
      "confidence": "high"
    },
    {
      "name": "hammer",
      "timeframe": "15m",
      "as_of": "2026-05-20T14:30",
      "detection_method": "agent_interpretation",
      "confidence": "medium",
      "context": "직전 5봉 -1.2% 하락 후 하단 그림자 2.3배, SMA60 지지선에서 형성"
    }
  ],
  "reasoning_kr": "일봉 골든크로스 65일 경과 + MACD 양전환으로 추세 강도 명확. 15분봉에서도 SMA60 지지선에서 망치형 형성, 단기 진입 신호 확인. RSI 두 timeframe 모두 모멘텀 영역에 있어 추가 상승 여력. 단 볼린저 상단 근접으로 76,200 저항 테스트 가능성, 그래도 추세 강도가 압도적이라 strong.",
  "as_of": "2026-05-20"
}
```

## Constraints

- **Cite specific numbers** from both timeframe indicators files. "RSI is high" → "RSI 일봉 58.3 / 15분봉 62.1".
- **Use Core 7 names only** in `patterns_detected.name`. No "rounding bottom", "wedge", etc.
- **Confidence**: `high` only for automatic patterns OR agent-interpreted patterns where ALL
  identification criteria in chart-patterns.md are met AND a confirmation candle has occurred.
  Otherwise `medium` (criteria met but no confirmation) or `low` (partial criteria).
- **False-positive guards from chart-patterns.md are absolute.** If any guard fires, do NOT
  add the pattern.
- **Acknowledge timeframe conflict**: if daily is bullish but intraday is bearish, say so in
  `reasoning_kr` and reflect in strength (likely medium not strong).
- **No forward forecasts** beyond next 1-5 sessions.
- **Don't quote news** — that's the news agent's job.

## Self-check

- Did I cite indicators from BOTH timeframes?
- Did all patterns_detected entries use Core 7 names exactly?
- For each agent_interpretation pattern: did I check the false-positive guards?
- Did I include caution_signals even when direction is bull?
- Are my `key_levels` actual values from indicator files?
````

- [ ] **Step 2: Verify the file**

```bash
head -10 $SKILL_DIR/references/agent-prompts/chart-agent.md
grep -c "patterns_detected" $SKILL_DIR/references/agent-prompts/chart-agent.md
```

Expected: file shows new header; grep finds 5+ mentions.

- [ ] **Step 3: Commit**

```bash
git -C $SKILL_DIR add references/agent-prompts/chart-agent.md
git -C $SKILL_DIR commit -m "feat(agent): extend chart agent with intraday + Core 7 patterns vocabulary"
```

---

## Task 10: Modify `scripts/compose_report.py` — embed PNGs, rubric, patterns

**Files:**
- Modify: `scripts/compose_report.py`

- [ ] **Step 1: Modify the file in three targeted edits**

**Edit A** — add `load_rubric_score()` helper and modify Phase 4 wiring. After the existing
`load_holdings()` function in `compose_report.py`, add:

```python
def load_rubric_score(p: Path) -> dict | None:
    """Load deterministic rubric score for a ticker. Returns None if missing."""
    return load_json(p)


def copy_chart_pngs(session_dir: Path, day_dir: Path, ticker: str, stamp: str) -> dict:
    """Copy chart PNGs from session into the day_dir using <stamp>-<ticker>-{daily,intraday}.png.

    Returns dict with bools for which charts succeeded.
    """
    import shutil
    out = {"daily": False, "intraday": False}
    charts_src = session_dir / "charts"
    for kind in ("daily", "intraday"):
        src = charts_src / f"{ticker}-{kind}.png"
        if src.exists():
            dst = day_dir / f"{stamp}-{ticker}-{kind}.png"
            shutil.copyfile(src, dst)
            out[kind] = True
    return out
```

**Edit B** — modify `compute_verdict()` to use rubric score for fundamentals. Replace the
existing `compute_verdict()` function with:

```python
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
        raw = DIR_STR_TO_SCORE.get((d, s), 0)
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
        raw = DIR_STR_TO_SCORE.get((d, s), 0)
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
        raw = DIR_STR_TO_SCORE.get((d, s), 0)
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
```

**Edit C** — modify `render_ticker_md()` to add chart embeds, rubric breakdown table, patterns
section. Update its signature and body. Find the existing function and change the signature
from:

```python
def render_ticker_md(ticker, holding, ind, funda, news_a, funda_a, chart_a, verdict, fx):
```

to:

```python
def render_ticker_md(ticker, holding, ind, funda, news_a, funda_a, chart_a, verdict, fx,
                     rubric_score=None, chart_pngs=None, stamp=""):
```

Then in the function body, insert these three new section blocks. (a) Just after the
"## 채널별 판단" table renders (after `lines.append("")` following that table), insert the
chart embed block:

```python
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
```

(b) Just after the chart block, insert the rubric breakdown table:

```python
    # === NEW: Deterministic fundamentals rubric breakdown ===
    if rubric_score:
        lines.append("## 펀더멘털 Rubric (deterministic)")
        lines.append("")
        lines.append(f"**Total**: {rubric_score['total_score']:+d} → "
                     f"{rubric_score['direction']} {rubric_score['strength']}")
        lines.append("")
        lines.append("| 지표 | 값 | 점수 | 등급 |")
        lines.append("|------|----|----|-----|")
        for b in rubric_score.get("breakdown", []):
            val = b.get("value")
            val_str = f"{val:.2f}" if isinstance(val, (int, float)) else str(val)
            note = b.get("tier_note", "")
            lines.append(f"| {b['metric']} | {val_str} | **{b['score']:+d}** | {note} |")
        if rubric_score.get("skipped_metrics"):
            lines.append("")
            lines.append("_Skipped (null values)_: " +
                         ", ".join(s["metric"] for s in rubric_score["skipped_metrics"]))
        lines.append("")
```

(c) Just after the chart-agent narrative section renders (after the existing chart agent
`key_drivers` rendering, **but before** the `if ind:` block), insert the patterns_detected
section:

```python
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
```

**Edit D** — modify `main()` to wire it all together. Find the per-ticker loop and replace the
relevant section. Specifically, the block that currently reads:

```python
        verdict = compute_verdict(news_a, funda_a, chart_a, weights)
        holding = by_ticker.get(t)

        # per-ticker files
        md = render_ticker_md(t, holding, ind, funda, news_a, funda_a, chart_a, verdict, fx)
```

Replace it with:

```python
        # Load deterministic rubric score (None if missing)
        rubric_score = load_rubric_score(scores_dir / f"{t}-rubric.json")

        verdict = compute_verdict(news_a, funda_a, chart_a, weights, rubric_score=rubric_score)
        holding = by_ticker.get(t)

        # Copy chart PNGs into the day directory
        chart_pngs = copy_chart_pngs(session, day_dir, t, stamp)

        # per-ticker files
        md = render_ticker_md(t, holding, ind, funda, news_a, funda_a, chart_a, verdict, fx,
                              rubric_score=rubric_score, chart_pngs=chart_pngs, stamp=stamp)
```

Also above the loop, add `scores_dir`:

```python
    scores_dir = session / "scores"
```

right after the existing line `data_dir = session / "data"`.

And in the per_json dict, add the new fields. Find:

```python
        per_json = {
            "ticker": t,
            ...
            "fundamentals": funda,
        }
```

Add these two keys to that dict (before the closing `}`):

```python
            "rubric_score": rubric_score,
            "chart_pngs": chart_pngs,
```

- [ ] **Step 2: Sanity-run on an empty session (verify no syntax errors)**

```bash
$PY -c "import sys; sys.path.insert(0, '$SKILL_DIR/scripts'); import compose_report; print('import OK')"
```

Expected: prints `import OK`.

- [ ] **Step 3: Commit**

```bash
git -C $SKILL_DIR add scripts/compose_report.py
git -C $SKILL_DIR commit -m "feat(report): embed chart PNGs + rubric breakdown + patterns section; use rubric for funda channel"
```

---

## Task 11: Update `references/settings.yml.example` and `SKILL.md`

**Files:**
- Modify: `references/settings.yml.example`
- Modify: `SKILL.md`

- [ ] **Step 1: Add `chart:` block to settings.yml.example**

Append to `$SKILL_DIR/references/settings.yml.example`:

```yaml

# 차트 렌더링 옵션 (Phase 2.5)
chart:
  intraday_interval: "15m"     # 1m | 5m | 15m | 30m | 60m
  intraday_days: 30
  render_chart: true           # PNG 생성 on/off

# 펀더멘털 deterministic rubric 경로 (생략 시 스킬 default 사용)
# fundamentals_rubric: ~/.config/portfolio-analysis/fundamentals-rubric.yml
```

- [ ] **Step 2: Update SKILL.md Phase 2 section**

In `$SKILL_DIR/SKILL.md`, find the Phase 2 bash block that lists the four `fetch_*` and `calc_*`
script calls. Replace it with the extended 7-call sequence:

```bash
SKILL_DIR=~/.claude/skills/stock-portfolio-analysis
PY=$SKILL_DIR/.venv/bin/python3

$PY $SKILL_DIR/scripts/fetch_ohlcv.py        <TICKERS> --out "$SESSION_DIR/data" --days 250
$PY $SKILL_DIR/scripts/fetch_intraday.py     <TICKERS> --out "$SESSION_DIR/data" --interval 15m --days 30
$PY $SKILL_DIR/scripts/calc_indicators.py    <TICKERS> --in  "$SESSION_DIR/data" --timeframe daily
$PY $SKILL_DIR/scripts/calc_indicators.py    <TICKERS> --in  "$SESSION_DIR/data" --timeframe intraday
$PY $SKILL_DIR/scripts/render_chart.py       <TICKERS> --data "$SESSION_DIR/data" --out "$SESSION_DIR/charts"
$PY $SKILL_DIR/scripts/fetch_fundamentals.py <TICKERS> --out "$SESSION_DIR/data"
$PY $SKILL_DIR/scripts/score_fundamentals.py <TICKERS> --data "$SESSION_DIR/data" \
    --rubric ~/.config/portfolio-analysis/fundamentals-rubric.yml \
    --out "$SESSION_DIR/scores"
$PY $SKILL_DIR/scripts/currency.py --pair USD_KRW --out "$SESSION_DIR/exchange_rate.json"
```

In the same SKILL.md, add a "rubric copy" line to Phase 0 setup after the existing `settings.yml`
copy:

```bash
[ -f ~/.config/portfolio-analysis/fundamentals-rubric.yml ] || \
  cp ~/.claude/skills/stock-portfolio-analysis/references/fundamentals-rubric.yml \
     ~/.config/portfolio-analysis/fundamentals-rubric.yml
```

In the "Reference files" section, add three new entries:

```markdown
- `references/chart-patterns.md` — Core 7 chart pattern reference (auto-detected + agent-interpreted)
- `references/fundamentals-rubric.yml` — Deterministic value-tier thresholds for ROE/PBR/PER/...
- `references/agent-prompts/chart-agent.md` — Chart subagent (dual-timeframe + patterns)
```

In the "Scripts" section, add:

```markdown
- `scripts/fetch_intraday.py` — yfinance 15m × 30d intraday OHLCV
- `scripts/render_chart.py` — mplfinance candlestick + SMA overlay + volume → PNG
- `scripts/score_fundamentals.py` — Reads rubric YAML, emits deterministic per-ticker score
```

In the "Phase 4: Verdict synthesis" section, add this note at the end:

```markdown
**Important contract change**: the fundamentals channel verdict comes from `score_fundamentals.py`
(deterministic, rubric-driven) — the LLM fundamentals agent is now narrative-only. News and chart
channels are still LLM-decided.
```

- [ ] **Step 3: Verify the docs**

```bash
grep -c "fetch_intraday" $SKILL_DIR/SKILL.md
grep -c "score_fundamentals" $SKILL_DIR/SKILL.md
grep -c "render_chart" $SKILL_DIR/SKILL.md
grep -c "chart:" $SKILL_DIR/references/settings.yml.example
```

Expected: each grep returns ≥ 1.

- [ ] **Step 4: Commit**

```bash
git -C $SKILL_DIR add SKILL.md references/settings.yml.example
git -C $SKILL_DIR commit -m "docs: update SKILL.md Phase 0/2/4 and settings.yml.example for new pipeline"
```

---

## Task 12: End-to-end smoke test on one ticker

**Files:** (read-only verification)

- [ ] **Step 1: Run full Phase 2 sequence in a temp session**

```bash
SESSION=/tmp/portfolio-e2e-$(date +%s)
mkdir -p "$SESSION/data" "$SESSION/charts" "$SESSION/scores"
TICKER=NVDA

$PY $SKILL_DIR/scripts/fetch_ohlcv.py        $TICKER --out "$SESSION/data"
$PY $SKILL_DIR/scripts/fetch_intraday.py     $TICKER --out "$SESSION/data"
$PY $SKILL_DIR/scripts/calc_indicators.py    $TICKER --in  "$SESSION/data" --timeframe daily
$PY $SKILL_DIR/scripts/calc_indicators.py    $TICKER --in  "$SESSION/data" --timeframe intraday
$PY $SKILL_DIR/scripts/render_chart.py       $TICKER --data "$SESSION/data" --out "$SESSION/charts"
$PY $SKILL_DIR/scripts/fetch_fundamentals.py $TICKER --out "$SESSION/data"
$PY $SKILL_DIR/scripts/score_fundamentals.py $TICKER --data "$SESSION/data" \
    --rubric $SKILL_DIR/references/fundamentals-rubric.yml \
    --out "$SESSION/scores"

ls -la "$SESSION/data" "$SESSION/charts" "$SESSION/scores"
cat "$SESSION/scores/$TICKER-rubric.json"
```

Expected:
- `data/` has 4 JSONs: `NVDA-ohlcv.json`, `NVDA-intraday.json`, `NVDA-indicators.json`, `NVDA-indicators-intraday.json`, `NVDA-fundamentals.json`
- `charts/` has 2 PNGs: `NVDA-daily.png`, `NVDA-intraday.png`
- `scores/` has 1 JSON: `NVDA-rubric.json` with `total_score`, `direction`, `strength`, `breakdown`

- [ ] **Step 2: Run unit tests one more time to confirm no regressions**

```bash
cd $SKILL_DIR && .venv/bin/pytest tests/ -v 2>&1 | tail -30
```

Expected: all tests pass.

- [ ] **Step 3: Cleanup**

```bash
rm -rf "$SESSION"
```

- [ ] **Step 4: Final summary commit (optional — only if anything changed during e2e)**

```bash
git -C $SKILL_DIR status --short
```

If status is clean: no commit. If anything changed: commit with `chore: post-e2e cleanups`.

---

## Self-Review

**Spec coverage** (matched §X → Task N):
- Spec §3.1 New Files (5) → Tasks 2, 3, 5, 6, 7
- Spec §3.2 Modified Files (4) → Tasks 4, 8, 9, 10
- Spec §3.3 Configuration → Task 11
- Spec §4 Rubric format + tier semantics + channel wiring → Tasks 2, 3, 10
- Spec §5 Chart rendering visual spec → Task 6
- Spec §6 Pattern library (Core 7) → Task 7, 9
- Spec §7 Data flow per ticker → Task 12 (e2e verifies)
- Spec §8 Error handling — built into individual scripts (graceful skip on missing files) and partially tested in Task 12
- Spec §9 Backward compatibility — preserved by Task 4 (default `--timeframe daily`) and Task 10 (rubric fallback to agent)
- Spec §10 Risks / non-goals — accepted, not implemented (out of scope)
- Spec §11 Implementation order — matches this plan's task order
- Spec §12 User contribution point — Task 2 ships the rubric defaults that the user customizes

**Placeholder scan**: no "TBD" / "fill in" remain. Steps that say "see spec §X" reference the
spec doc the engineer also has. All code blocks are complete.

**Type consistency**:
- `score_ticker()` return type matches `load_rubric_score()` consumer in `compose_report.py` ✓
- `evaluate_metric()` returns `{"skipped", "score", "tier_note"}` consistently ✓
- `patterns_detected[].name` values referenced in chart-agent.md match Core 7 headers in chart-patterns.md ✓
- `process()` signature in calc_indicators.py is `(ticker, in_dir, out_dir, timeframe="daily")` — tested in Task 4 with both positional and keyword ✓

**Type / path conventions**:
- Output files use `<ticker>-<kind>.json` consistently (`-ohlcv`, `-intraday`, `-indicators`, `-indicators-intraday`, `-fundamentals`, `-rubric`)
- Report assets use `<stamp>-<ticker>-{daily,intraday}.png` (with the existing `<stamp>-` prefix used by other report files)

---

## Execution Handoff

Plan complete and saved to `~/.claude/skills/stock-portfolio-analysis/docs/plans/2026-05-21-charts-patterns-deterministic-rubric.md`. Two execution options:

**1. Subagent-Driven (recommended)** — fresh subagent per task, review between tasks, fast iteration
**2. Inline Execution** — execute tasks in this session using executing-plans, batch execution with checkpoints

Which approach?
