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


def test_nan_value_treated_as_null():
    """NaN must skip just like None (yfinance sometimes returns NaN)."""
    spec = RUBRIC["metrics"]["trailing_pe"]
    out = evaluate_metric(float("nan"), spec)
    assert out["skipped"] is True
    assert out["score"] is None


def test_unknown_direction_raises():
    """Typo in `direction` must raise, not silently misclassify."""
    spec = {
        "direction": "highbetter",  # typo
        "null_behavior": "skip",
        "tiers": [{"threshold": 0, "score": 0}],
    }
    with pytest.raises(ValueError, match="unknown direction"):
        evaluate_metric(5.0, spec)


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
