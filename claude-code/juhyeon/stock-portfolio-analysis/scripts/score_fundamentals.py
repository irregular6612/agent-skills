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
import math
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    yaml = None


def evaluate_metric(value, spec: dict) -> dict:
    """Evaluate one metric value against its tier spec.

    Tier-ordering contract: `lower_better` tiers ascend by threshold;
    `higher_better` tiers descend. First match wins.
    Returns a dict with either score+tier_note or skipped=True.
    """
    is_nan = isinstance(value, float) and math.isnan(value)
    if value is None or is_nan:
        if spec.get("null_behavior", "skip") == "skip":
            return {"skipped": True, "score": None, "tier_note": None}
        # default fallthrough: treat as neutral
        return {"skipped": False, "score": 0, "tier_note": "null_neutral"}

    direction = spec["direction"]
    if direction not in ("lower_better", "higher_better"):
        raise ValueError(f"unknown direction {direction!r} in metric spec")
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
