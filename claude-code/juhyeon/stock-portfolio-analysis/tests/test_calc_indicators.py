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


def test_intraday_signal_labels_match_timeframe(tmp_path):
    """Intraday signals must use sma20/sma60 labels, not sma50/sma200."""
    in_dir = tmp_path
    payload = _synthetic_payload(120)
    (in_dir / "TEST-intraday.json").write_text(json.dumps(payload))

    process("TEST", in_dir, in_dir, timeframe="intraday")
    data = json.loads((in_dir / "TEST-indicators-intraday.json").read_text())
    signals = " ".join(data["signals"])

    assert "sma50" not in signals
    assert "sma200" not in signals
    assert "sma20" in signals or "sma60" in signals


def test_daily_signal_labels_unchanged(tmp_path):
    """Daily signals keep sma50/sma200 labels (backward compatibility)."""
    in_dir = tmp_path
    payload = _synthetic_payload(250)
    (in_dir / "TEST-ohlcv.json").write_text(json.dumps(payload))

    process("TEST", in_dir, in_dir, timeframe="daily")
    data = json.loads((in_dir / "TEST-indicators.json").read_text())
    signals = " ".join(data["signals"])

    assert "sma50" in signals or "sma200" in signals
