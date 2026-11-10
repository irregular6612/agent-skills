# 독자 정하기

판정자에게 "너는 이런 사람이다"라고 알려주는 문단을 **독자 정의**라고 부른다.
드라이버가 이걸 만들어서 판정자 셋에게 똑같이 넘긴다.

## 사용자가 지정하는 형식

세 가지다.

```
독자: @adjacent-phd                       # 아무 말이 없으면 이게 기본값
독자: @adjacent-phd, 단 통계는 나보다 잘 앎
독자: <자유 문장 전체>
```

두 번째 형식은 프리셋 뒤에 사용자의 단서를 그대로 이어 붙인다.
세 번째 형식은 프리셋을 통째로 사용자의 문장으로 갈아끼운다.

**프리셋은 하나뿐이다. 늘리지 마라.** 고를 수 있게 되는 순간 사람은 제일 빡센 독자를
고르고, 빡센 독자는 대개 안 덮는 독자다. 안 덮는 독자에게서는 "여기서 멈췄다"가 안 나온다.

**라운드가 시작된 뒤에는 독자를 못 바꾼다.** 바꾸고 싶으면 라운드 0부터 다시 시작한다.
중간에 바뀌면 라운드끼리 비교가 안 되기 때문이다.

## 프리셋 `@adjacent-phd`

### KO

```
너는 인접 분야 박사과정 3년차다. 이 글의 큰 주제는 안다. 하위 분야의 표준 기법 · 약어 · 자주 인용되는 선행연구는 모른다.

읽는 이유: 이 글이 네 연구에 쓸 만한지 판단하려고. 아니면 덮는다. 아무도 뭐라 안 한다.

저자를 모르고, 물어볼 수 없다. 막히면 막힌 채로 남는다.

시간은 15분 있고, 오늘 읽어야 할 다른 글이 네 편 더 있다.
```

### EN

```
You are a third-year PhD student in an adjacent field. You know the broad topic. You do not know this subfield's standard methods, its abbreviations, or the work it usually cites.

Why you are reading: to decide whether this is useful for your own research. If it isn't, you stop. Nobody minds.

You don't know the author and you can't ask. If you get stuck, you stay stuck.

You have fifteen minutes, and four more things to read today.
```

## 덮을-자유 문장 — 항상 붙인다, 예외 없다

독자 정의가 프리셋이든 사용자의 자유 문장이든, 드라이버는 그 **끝에** 아래 한 문장을 이어 붙인다.

KO:

```
그리고 너는 이 글을 끝까지 읽을 의무가 없다. 언제든 덮어도 되고, 덮어도 아무 일도 일어나지 않는다.
```

EN:

```
And you are under no obligation to finish this. You can stop at any point, and nothing happens if you do.
```

**프리셋 문구에 이미 같은 뜻이 들어 있어도 중복해서 붙인다.** 중복이 아깝다고 빼면,
사용자가 자유 문장으로 독자를 갈아끼운 경로에서 이 문장이 통째로 사라진다.
그 경로에서는 이게 유일한 방어선이다.

왜 이 문장이 방어선인가: 이 스킬의 종료 조건은 "덮은 지점이 0건"이다.
사용자가 `독자: 학회 리뷰어`라고 적으면 그 독자는 직업상 끝까지 읽는 사람이라
아무리 막혀도 안 덮고, 그러면 "덮었다"가 영영 0이 되어 종료 조건이 무너진다.
규칙으로 사용자에게 "그런 독자는 쓰지 마세요"라고 미는 대신,
프롬프트 안에서 덮을 자유를 되돌려 주는 방식으로 닫는다.

## 판정자와 writer는 같은 독자 문구를 받지 않는다

판정자는 위의 네 문단짜리 풀버전을 받는다. writer는 한 줄짜리 요약만 받는다
(초안 없이 처음 쓰는 부수 경로에서만, `독자는 <한 줄>이다` 형태로).

**의도적인 비대칭이다.** writer가 풀버전을 보면 "15분밖에 없고 언제든 덮는 독자"에 맞춰
방어적으로 쓴다 — 약어를 다 풀고, 지나치게 친절해지고, 길어지고, 학술적인 밀도가 떨어진다.
일관성이 좋아 보인다고 양쪽을 같게 맞추지 마라.
