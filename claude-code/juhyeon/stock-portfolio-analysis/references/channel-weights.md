# Channel Weights

3-channel weighted scoring: news + fundamentals + chart.

## Default (balanced)

```yaml
weights:
  news: 0.30
  fundamentals: 0.40
  chart: 0.30
```

Rationale: fundamentals get a slight edge as the most durable signal; news and chart roughly equal for catalyst-detection and momentum.

## Presets (편집해서 settings.yml에 복붙)

```yaml
# 장기 가치 투자자 (Warren Buffett 스타일)
preset: long_term_value
weights:
  news: 0.10
  fundamentals: 0.70
  chart: 0.20

# 모멘텀 트레이더 (스윙/단타)
preset: momentum_trader
weights:
  news: 0.40
  fundamentals: 0.10
  chart: 0.50

# 뉴스 드리븐 (이벤트 베팅)
preset: news_driven
weights:
  news: 0.60
  fundamentals: 0.20
  chart: 0.20

# 기술적 분석 위주 (차트 신뢰)
preset: technical
weights:
  news: 0.20
  fundamentals: 0.10
  chart: 0.70

# 균형형 (default)
preset: balanced
weights:
  news: 0.30
  fundamentals: 0.40
  chart: 0.30

# 펀더멘털 무시 (성장주 추격)
preset: growth_chase
weights:
  news: 0.45
  fundamentals: 0.15
  chart: 0.40
```

## 가중치 자체 정의

직접 `settings.yml`에 적어도 OK. 합이 1.0이 아니어도 자동 정규화됩니다 (compose_report.py가 sum으로 나눠 줌).

```yaml
weights:
  news: 35
  fundamentals: 45
  chart: 20
# → 자동으로 0.35 / 0.45 / 0.20 으로 변환
```

## 가중치 선택 가이드

| 만약 당신이... | 권장 preset |
|---------------|-------------|
| 1년 이상 보유할 핵심 자산을 평가 | long_term_value |
| 분기 단위로 회전매매 | balanced |
| 1~5일 스윙 트레이드 | momentum_trader |
| 실적 발표·M&A 이벤트로 단기 베팅 | news_driven |
| 차트 패턴 위주로 진입/탈출 | technical |
| AI/바이오 등 고성장 섹터 | growth_chase |

## 가중치는 verdict만 영향, 원시 판단은 동일

- 가중치를 바꿔도 **각 채널의 강/중/약 판단은 변하지 않음** (LLM agent가 채널 내에서 결정).
- 가중치는 **합산 단계**에만 영향. 따라서 같은 데이터로 두 명의 사용자가 다른 verdict를 받을 수 있음 → 이게 의도된 동작.

## 임계값 커스터마이즈 (선택)

`settings.yml`에서:

```yaml
thresholds:
  strong_buy: 1.5
  buy: 0.5
  reduce: -0.5
  strong_sell: -1.5
```

위 4개 미만 사이는 자동으로 hold/중립. 임계값을 좁히면(예: 0.3) 더 자주 verdict가 변하고, 넓히면(예: 2.0) 보수적이 됨.
