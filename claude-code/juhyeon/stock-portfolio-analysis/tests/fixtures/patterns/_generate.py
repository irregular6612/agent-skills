#!/usr/bin/env python3
"""Generate synthetic OHLCV fixtures for pattern detection regression tests.

This is a one-shot script — pytest does not run it. Re-run only when the fixture
schema changes (then commit the resulting JSONs).

Usage:
    python tests/fixtures/patterns/_generate.py
"""
from __future__ import annotations
import json
from datetime import date, timedelta
from pathlib import Path

FIXTURES = Path(__file__).resolve().parent


def linterp(a, b, n):
    """Linear interpolation between a and b in n steps, endpoint excluded."""
    if n <= 0:
        return []
    step = (b - a) / n
    return [a + step * i for i in range(n)]


def to_rows(closes: list[float], start: str = "2026-01-01",
            volume_fn=None) -> list[dict]:
    base = date.fromisoformat(start)
    rows = []
    for i, c in enumerate(closes):
        c = float(c)
        rows.append({
            "date": (base + timedelta(days=i)).isoformat(),
            "open":  c * 0.99,
            "high":  c * 1.005,
            "low":   c * 0.995,
            "close": c,
            "volume": float(volume_fn(i) if volume_fn else 1_000_000 - i * 1000),
        })
    return rows


def write(name: str, closes: list[float], volume_fn=None):
    rows = to_rows(closes, volume_fn=volume_fn)
    payload = {
        "market": "TEST", "currency": "USD", "ticker": name,
        "as_of": rows[-1]["date"], "data": rows,
    }
    (FIXTURES / f"{name}-ohlcv.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2))
    print(f"wrote {name}-ohlcv.json: {len(rows)} bars")


def main():
    # 1) Clean H&S with prior uptrend, neckline broken, declining volume
    write("synthetic_hs",
          linterp(50, 65, 20) +
          linterp(65, 70, 8) + linterp(70, 65, 7) +
          linterp(65, 80, 8) + linterp(80, 65, 7) +
          linterp(65, 70, 8) + linterp(70, 65, 7) +
          linterp(65, 58, 10))

    # 2) Clean Double Top, peaks ~75, neckline ~65, prior uptrend, breakout
    write("synthetic_double_top",
          linterp(50, 65, 20) +
          linterp(65, 75, 8) + linterp(75, 65, 12) +
          linterp(65, 75, 8) + linterp(75, 65, 12) +
          linterp(65, 58, 10))

    # 3) Random walk — no pattern (seeded for determinism)
    import random
    rnd = random.Random(42)
    rw = [100.0]
    for _ in range(149):
        rw.append(rw[-1] * (1 + rnd.uniform(-0.015, 0.015)))
    write("synthetic_no_pattern", rw)

    # 4) Uneven shoulders — right shoulder 12% higher than left (must fail
    # shoulder_equality with ±5% threshold) so NO H&S emitted
    write("synthetic_uneven_shoulders",
          linterp(50, 65, 20) +
          linterp(65, 70, 8) + linterp(70, 65, 7) +     # LS at 70
          linterp(65, 80, 8) + linterp(80, 65, 7) +     # head at 80
          linterp(65, 78, 8) + linterp(78, 65, 7) +     # RS at 78 (~11% > LS)
          linterp(65, 58, 10))

    # 5) Double Top with peaks too far apart in price (P1=75, P2=85 → 12%
    # apart, exceeds peak_equality 3% threshold)
    write("synthetic_peaks_too_far",
          linterp(50, 65, 20) +
          linterp(65, 75, 8) + linterp(75, 65, 12) +    # P1 at 75
          linterp(65, 85, 8) + linterp(85, 65, 12) +    # P2 at 85
          linterp(65, 58, 10))


if __name__ == "__main__":
    main()
