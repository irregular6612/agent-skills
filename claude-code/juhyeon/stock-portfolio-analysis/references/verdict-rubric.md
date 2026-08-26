# Verdict Rubric

How channel outputs convert to numbers, and numbers convert to final verdicts.

## Step 1: Channel output → numeric score

Each of the 3 channels (news, fundamentals, chart) emits `(direction, strength)`:

| direction | strength | raw score |
|-----------|----------|-----------|
| bull      | strong   | **+3** |
| bull      | medium   | **+2** |
| bull      | weak     | **+1** |
| neutral   | (any)    | **0** |
| bear      | weak     | **-1** |
| bear      | medium   | **-2** |
| bear      | strong   | **-3** |

A missing channel (agent failed, no data) contributes **0** but the report flags it.

## Step 2: Apply channel weights

Default (balanced):
```
total = news_score × 0.30 + funda_score × 0.40 + chart_score × 0.30
```

User can override via `~/.config/portfolio-analysis/settings.yml`. See `channel-weights.md` for presets.

Range: minimum `-3.00` (all channels bear-strong), maximum `+3.00` (all bull-strong).

## Step 3: Final verdict thresholds

| weighted total | verdict | emoji | meaning |
|----------------|---------|-------|---------|
| ≥ +1.5         | 강매수  | 🟢    | Strong Buy — 비중 확대 검토 |
| +0.5 ~ +1.49   | 중매수  | 🟡    | Buy — 보유 + 추가 진입 검토 |
| -0.49 ~ +0.49  | 중립    | ⚪    | Hold — 유지 |
| -1.49 ~ -0.5   | 중매도  | 🟠    | Reduce — 비중 축소 검토 |
| ≤ -1.5         | 강매도  | 🔴    | Strong Sell — 청산 검토 |

These thresholds are calibrated for the default weights (0.30/0.40/0.30). If weights change significantly, the thresholds still hold because the weighted total is bounded by [-3, +3].

## Examples

### Example 1: 삼성전자 (005930.KS) — 균형형 가중치

| 채널 | direction | strength | raw | weight | weighted |
|------|-----------|----------|-----|--------|----------|
| news | bull | strong | +3 | 0.30 | +0.90 |
| funda | bull | weak | +1 | 0.40 | +0.40 |
| chart | bull | medium | +2 | 0.30 | +0.60 |
| **Total** | | | | | **+1.90** |

→ **🟢 강매수**

### Example 2: NVDA — momentum_trader 가중치

(news 0.40, funda 0.10, chart 0.50)

| 채널 | direction | strength | raw | weight | weighted |
|------|-----------|----------|-----|--------|----------|
| news | bull | medium | +2 | 0.40 | +0.80 |
| funda | bull | strong | +3 | 0.10 | +0.30 |
| chart | bear | weak | -1 | 0.50 | -0.50 |
| **Total** | | | | | **+0.60** |

→ **🟡 중매수** (momentum 채널 weight 높여 차트의 음의 신호가 더 반영됨)

### Example 3: Mixed conflict

| 채널 | direction | strength | raw | weight | weighted |
|------|-----------|----------|-----|--------|----------|
| news | bear | medium | -2 | 0.30 | -0.60 |
| funda | bull | medium | +2 | 0.40 | +0.80 |
| chart | bear | strong | -3 | 0.30 | -0.90 |
| **Total** | | | | | **-0.70** |

→ **🟠 중매도** (펀더멘털은 좋지만 뉴스+차트가 부정적)

## Why these thresholds?

- ±1.5 cutoff = ~50% of max range. Reaching this means at least 2 channels meaningfully aligned (e.g., one medium + one strong same direction).
- ±0.5 cutoff = ~17% of max range. Reaching this means at least one channel medium-or-better, others not strongly opposing.
- Inside [-0.5, +0.5]: noise zone, channels canceling out → genuinely neutral.

Adjustable via `~/.config/portfolio-analysis/settings.yml` field `thresholds:` (advanced).

## How agents should NOT game the rubric

- "Strong" is reserved for **multiple aligned, concrete catalysts** (3+ news sources, 4+ TA signals, 2+ fundamental signals). Not for "I feel strongly".
- "Weak" includes "thin/no data". Don't promote weak to medium without evidence.
- Direction must reflect the data, not the user's hope. If you can't justify a direction, use `neutral` / `weak`.
