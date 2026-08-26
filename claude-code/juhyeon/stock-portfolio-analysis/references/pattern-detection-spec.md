# Pattern Detection — Algorithm Specification

> **Companion to `chart-patterns.md`.** That doc defines the vocabulary (what the
> patterns *mean* and when an agent should *call* them). This doc defines the
> executable contract: how `scripts/detect_patterns.py` emits candidates and which
> numeric guards are baked into code vs. left to the chart-agent.

**Scope (v1):** daily timeframe only — Head & Shoulders (regular + inverse) and
Double Top / Double Bottom. Intraday `< 1h` is explicitly out of scope per the
`chart-patterns.md` §3 guard "Do not call H&S on intraday timeframes < 1h".

---

## Pivot extraction

We use `zigzag.peak_valley_pivots(close, up_thresh, down_thresh)` from the
`zigzag` PyPI package (jbn/ZigZag). It returns an array aligned with the input
series where `+1 = peak`, `-1 = valley`, `0 = neither`.

| Input series | Choice |
|---|---|
| `close` | Used for the pivot driver — close-to-close moves drive the threshold |
| `high` | Used for the *price* of detected peaks (avoids intra-bar bias) |
| `low` | Used for the *price* of detected valleys |

**Why split**: zigzag thresholds on close so it doesn't oscillate on wicks, but
once a pivot bar is identified we read its actual high/low for accurate target
projection and visualization.

---

## Tunable parameters (defaults)

| Parameter | Value | Source / rationale |
|---|---|---|
| `pivot_threshold_pct` | 3.0 | Tuned for daily 250-bar window — balances noise vs missed patterns. zigzag `up_thresh=0.03, down_thresh=-0.03`. |
| `min_bars_between_pivots` | 5 | `chart-patterns.md` §4 guard: "peaks within 5 bars = single wide top" |
| `shoulder_equality_pct` | 5.0 | `chart-patterns.md` §3 guard: "right shoulder materially higher = not H&S" — *materially* ≡ ±5% |
| `peak_equality_pct` | 3.0 | `chart-patterns.md` §4: "two roughly equal peaks (within 3% in price)" |
| `head_prominence_pct` | 3.0 | Head must exceed both shoulders by ≥ 3% to count as a true *head* |
| `prior_trend_lookback_bars` | 20 | Bars before left shoulder to confirm uptrend (H&S) / downtrend (inverse) |
| `prior_trend_min_pct` | 5.0 | Net price movement % over lookback to qualify as a meaningful "prior trend" |
| `max_pattern_bars` | 120 | Patterns spanning > 120 bars are usually two unrelated formations chained |
| `volume_check` | enabled | If volume data present: `vol[RS] < min(vol[LS], vol[H])` for H&S, `vol[P2] < vol[P1]` for double top |

All defaults can be overridden via `~/.config/portfolio-analysis/settings.yml`
under the optional `pattern_detection:` block (see `references/settings.yml.example`).

---

## What the algorithm checks (numeric guards)

These are coded in `scripts/detect_patterns.py`. A candidate is emitted to
`*-patterns.json` only when all numeric guards pass; each individual guard's
pass/fail goes into the candidate's `guards_passed` / `guards_failed` arrays.

### H&S (regular) — 5-pivot window

Sequence (after pivot extraction): `peak(LS), valley(left_neck), peak(H), valley(right_neck), peak(RS)`.

1. **Head prominence**: `H.price > max(LS.price, RS.price) × (1 + head_prominence_pct/100)`
2. **Shoulder equality**: `abs(LS.price - RS.price) / max(LS.price, RS.price) ≤ shoulder_equality_pct/100`
3. **Spacing**: `min_bars_between_pivots ≤ (gap between any two consecutive pivots)`
4. **Total span**: `RS.bar_idx - LS.bar_idx ≤ max_pattern_bars`
5. **Prior trend (up)**: `closes[LS.bar_idx - prior_trend_lookback_bars : LS.bar_idx]` net change ≥ `prior_trend_min_pct`
6. **Volume**: `vol[RS] < min(vol[LS], vol[H])` (skipped if volume missing/zero)

### Inverse H&S — mirror

Sequence: `valley(LS), peak(left_neck), valley(H), peak(right_neck), valley(RS)`.
Same guards with peak↔valley flipped and "prior trend" expected **down**.

### Double Top — 3-pivot window

Sequence: `peak(P1), valley(neck), peak(P2)`.

1. **Peak equality**: `abs(P1.price - P2.price) / max(P1.price, P2.price) ≤ peak_equality_pct/100`
2. **Spacing**: `min_bars_between_pivots ≤ (P2.bar_idx - P1.bar_idx) ≤ max_pattern_bars`
3. **Prior trend (up)** through P1
4. **Volume**: `vol[P2] < vol[P1]` (skipped if missing)

### Double Bottom — mirror

Sequence: `valley(P1), peak(neck), valley(P2)`. Prior trend **down**.

---

## Neckline + target + completion

### H&S neckline

Linear interpolation through the two intermediate pivots `(left_neck, right_neck)`.
Extends from `left_neck` to `last_bar`. Slope retained — necklines often slope
slightly (mildly sloped neckline is still valid per textbook).

### Double T/B neckline

Horizontal — the intervening pivot's price. Double T/B necklines are typically
flat per `chart-patterns.md` §4.

### Target price

- H&S: `neckline_at(H.date) - (H.price - neckline_at(H.date))` (height projected from breakout)
- Inverse H&S: `neckline_at(H.date) + (neckline_at(H.date) - H.price)`
- Double Top: `neckline.price - (max(P1.price, P2.price) - neckline.price)`
- Double Bottom: `neckline.price + (neckline.price - min(P1.price, P2.price))`

### Completion (`neckline_broken`)

- Bearish (H&S, Double Top): any close in `[last_pivot.bar_idx + 1 : end]` strictly below the neckline at that bar
- Bullish (Inverse H&S, Double Bottom): any close strictly above the neckline at that bar

A pattern is reported regardless of completion status — the chart-agent uses
`neckline_broken` to grade confidence (see below).

---

## Confidence grading (emitted by algorithm)

The algorithm assigns one of `low | medium | high`:

| Grade | Condition |
|---|---|
| `high` | All numeric guards pass **and** `neckline_broken == True` **and** volume confirmation passed |
| `medium` | All numeric guards pass **and** `neckline_broken == False` (pattern formed, awaiting breakout) |
| `low` | Exactly one guard failed but the rest pass and pivot sequence is correct |
| (not emitted) | ≥ 2 guards failed, or pivot sequence does not match |

The chart-agent may *downgrade* high→medium based on vocabulary guards not coded
here (e.g., "this is a relief rally in a downtrend, not a true reversal" — context
the algorithm cannot judge). It may **not** upgrade.

---

## What the algorithm does NOT check (delegated to chart-agent)

These vocabulary guards from `chart-patterns.md` are not encoded in numeric form
and the chart-agent must verify them visually using the annotated PNG:

- **Reversal vs continuation context**: Is the prior trend a genuine, accepted
  trend, or a relief rally inside a larger countertrend?
- **Range vs trend**: "Random triple touches in a sideways range are NOT H&S"
  — sideways detection is fuzzy; algorithm only enforces `prior_trend_min_pct`
  net change, which a chop range can occasionally satisfy by accident.
- **Visual coherence**: Even when guards pass numerically, the markers should
  "look right" on the chart — the agent's vision pass is the final filter.

---

## Output schema (`{ticker}-patterns.json`)

```json
{
  "ticker": "005930.KS",
  "timeframe": "daily",
  "as_of": "2026-05-19",
  "params": {
    "pivot_threshold_pct": 3.0,
    "min_bars_between_pivots": 5,
    ...
  },
  "patterns": [
    {
      "name": "head_and_shoulders",
      "pivots": [
        {"date": "2026-03-12", "price": 75200, "role": "left_shoulder", "bar_idx": 110},
        {"date": "2026-03-21", "price": 71500, "role": "left_neck",      "bar_idx": 119},
        {"date": "2026-04-02", "price": 78100, "role": "head",           "bar_idx": 131},
        {"date": "2026-04-15", "price": 71800, "role": "right_neck",     "bar_idx": 144},
        {"date": "2026-04-26", "price": 75400, "role": "right_shoulder", "bar_idx": 155}
      ],
      "neckline": {
        "start_date": "2026-03-21", "start_price": 71500,
        "end_date":   "2026-05-19", "end_price":   71900
      },
      "target_price": 65300,
      "neckline_broken": true,
      "break_date": "2026-05-10",
      "confidence": "high",
      "guards_passed": [
        "head_prominence", "shoulder_equality", "spacing", "total_span",
        "prior_trend", "volume_declining"
      ],
      "guards_failed": []
    }
  ]
}
```

---

## Golden test fixtures (Task 8)

| Fixture | Expected detection |
|---|---|
| `synthetic_hs.json` | exactly 1 `head_and_shoulders`, confidence ≥ medium |
| `synthetic_double_top.json` | exactly 1 `double_top` |
| `synthetic_no_pattern.json` | empty patterns array |
| `synthetic_uneven_shoulders.json` | no H&S (shoulder_equality guard fails) |
| `synthetic_peaks_too_far.json` | no double top (peak_equality guard fails) |

---

## Known limitations

1. **Lookahead in `peak_valley_pivots`**: The last pivot zigzag returns is
   provisional — it could shift as more bars arrive. Acceptable for "today's
   formed pattern" use; not for backtesting.
2. **No multi-timeframe confirmation**: A pattern detected on daily is not
   cross-checked against weekly. The chart-agent can do this contextually.
3. **No triangle / wedge / flag**: Out of v1 scope; reserved for v2.
