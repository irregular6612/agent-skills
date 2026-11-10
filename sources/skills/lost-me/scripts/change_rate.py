#!/usr/bin/env python3
"""변경률 계산 — 두 글이 얼마나 달라졌는지를 0~1 사이 비율로 잰다.

재는 방법은 "정규화 문자 diff 비율"이다. 공백과 구두점을 다 지운 뒤,
남은 글자열끼리 얼마나 겹치는지를 문자 단위 diff 로 구하고 1에서 뺀다.

왜 문자 단위인가:
  문장·문단 단위로 재면 자유 재작성에서는 정확히 일치하는 문장이 거의 0이라
  지표가 항상 100%에 붙어 죽는다. 의미 단위(명제 목록)로 재면 보존 대조가
  이미 보고 있는 것이라 지표가 항상 0에 붙어 죽는다.

왜 difflib 인가 — spec 8절은 괄호 안에서 "편집거리"라고 적었지만, 이 스크립트의
주 지표는 difflib 의 diff 비율이다. 두 값이 실제로 갈리기 때문이다. dry-run 라운드 1
(`.scratch/lost-me/_workspace/run-kdd-ko-intro/`)에서 관측된 값은 65.1%였고,
같은 한 쌍을 이 스크립트로 재면 diff 비율은 68.1%, 편집거리/최대길이는 73.5%가 나온다.
50/75 임계는 그 65.1% 관측을 근거로 정해진 값이므로, 편집거리를 주 지표로 쓰면
"지지된다"고 기록된 라운드 1이 곧바로 중단선에 닿는다. 그래서 주 지표는 관측값에
가까운 diff 비율로 두고, 편집거리는 `edit_distance_rate`로 같이 내보내 비교 가능하게 둔다.
(편집거리는 글이 길면 느려서 20,000자를 넘으면 계산하지 않고 null 로 둔다.)

사용:
  python3 change_rate.py 이전본.md 현재본.md
출력(JSON):
  {"change_rate": 0.6806, "level": "warn", "edit_distance_rate": 0.7354, ...}

level 은 세 가지다:
  ok    0.50 미만
  warn  0.50 이상 0.75 미만 — 알리고 진행한다(라운드는 소모된다)
  halt  0.75 이상 — 그 라운드 재작성을 롤백하고 루프를 멈춘 뒤 사용자 판단을 받는다
라운드 1은 halt 를 면제하고 경고만 한다. 면제 판단은 이 스크립트가 아니라 드라이버가 한다.
"""
import difflib
import json
import sys
import unicodedata

EDIT_DISTANCE_LIMIT = 20000


def normalize(text: str) -> str:
    """공백을 전부 지우고 구두점·기호를 지운다. 남는 것은 내용 글자뿐이다."""
    text = unicodedata.normalize("NFKC", text)
    out = []
    for ch in text:
        if ch.isspace():
            continue
        cat = unicodedata.category(ch)
        if cat.startswith("P") or cat in ("Sm", "Sk"):
            continue
        out.append(ch)
    return "".join(out)


def levenshtein(a: str, b: str) -> int:
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        curr = [i]
        for j, cb in enumerate(b, 1):
            curr.append(min(prev[j] + 1, curr[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = curr
    return prev[-1]


def main() -> int:
    if len(sys.argv) != 3:
        print("usage: change_rate.py <prev.md> <curr.md>", file=sys.stderr)
        return 2
    prev = normalize(open(sys.argv[1], encoding="utf-8").read())
    curr = normalize(open(sys.argv[2], encoding="utf-8").read())
    denom = max(len(prev), len(curr))

    if denom == 0:
        rate = 0.0
    else:
        rate = 1.0 - difflib.SequenceMatcher(None, prev, curr).ratio()

    if denom == 0:
        edit_rate = 0.0
    elif denom > EDIT_DISTANCE_LIMIT:
        edit_rate = None
    else:
        edit_rate = round(levenshtein(prev, curr) / denom, 4)

    level = "halt" if rate >= 0.75 else "warn" if rate >= 0.50 else "ok"
    print(json.dumps({
        "change_rate": round(rate, 4),
        "level": level,
        "edit_distance_rate": edit_rate,
        "prev_chars": len(prev),
        "curr_chars": len(curr),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
