# Core 7 Chart Patterns — Reference Vocabulary

The chart agent uses this document as its pattern vocabulary. Each pattern has
identification criteria, implications, false-positive guards, and strength scoring.

**Detection split:**
- Patterns 1-2 (MA cross, MACD cross): auto-detected by `calc_indicators.py` and surfaced
  as `signals[]`. Agent treats them as **given**.
- Patterns 3-4 (H&S regular + inverse, Double Top + Double Bottom — daily timeframe only):
  auto-detected by `detect_patterns.py` as **candidates** in `{ticker}-patterns.json`. Agent
  *verifies* (not re-detects) each candidate against the vocabulary guards in this document
  that are NOT coded in the algorithm (see `references/pattern-detection-spec.md` for the
  encoded numeric guards). Agent may downgrade the algorithm's confidence but never upgrade.
- Patterns 5-7 (candle: hammer, engulfing, doji): agent interprets from intraday OHLCV +
  intraday chart PNG using this vocabulary.

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

## 3. Head and Shoulders / Inverse Head and Shoulders (automatic candidate + agent verification)

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

## 4. Double Top / Double Bottom (automatic candidate + agent verification)

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
