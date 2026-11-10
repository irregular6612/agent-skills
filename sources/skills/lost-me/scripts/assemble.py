#!/usr/bin/env python3
"""판정자 3인의 드롭을 하나의 재작성 지시로 조립한다.

조립은 정렬이 전부다. 병합하지 않고, 자르지 않고, 라벨을 붙이지 않는다.

정렬 규칙(spec 6절):
  1. blocker 가 있는 지점이 먼저 온다. 다만 "blocker" 라는 표시는 어디에도 안 붙는다.
     순서만으로 드러낸다. writer 가 blocker 여부를 보면 non-blocker 를 무시하고,
     그러면 사람다움 축이 통째로 죽는다(사람다움 blocker 는 구조적으로 0에 가깝다).
  2. 같은 등급 안에서는 글에 등장하는 순서.
  3. 겹침 그룹 — 서로 다른 판정자가 같은 문장을 잡은 경우 — 은 붙여서 배치하고,
     그룹 안에서는 학술 → 읽힘 → 사람다움 순으로 둔다. 이 순서가 축 우선순위를
     집행하는 유일한 지점이다. 처방이 없으므로 드롭에는 방향이 없고, 방향이 없으면
     축 사이 충돌이 리포트에서 관측되지 않는다. 겹침 그룹만이 관측 가능한 충돌이다.

  겹침 그룹에 blocker 가 하나라도 섞여 있으면 그룹 전체가 앞 등급으로 간다.
  안 그러면 그룹이 쪼개져 3번 규칙이 깨진다.

진동 표시:
  지난 라운드에 blocker 였던 quote 가 이번 본문에 그대로 살아 있고, 이번 라운드에도
  같은 quote 의 드롭이 잡혔으면, 그 지점을 목록 맨 위로 올리고 지시에 한 문장을 더한다.
  본문에는 살아 있는데 이번 라운드 드롭에는 없으면 올릴 좌표가 없으므로 아무것도 안 한다.
  없는 드롭을 지어내는 것이 되기 때문이다.

사용:
  python3 assemble.py --text round-2/current.md \
      --academic drops-academic.json --readability drops-readability.json \
      --humanness drops-humanness.json \
      [--prev-blockers prev_blocker_quotes.json] [--lang ko|en]
출력: 재작성 지시 전문을 표준출력으로.
"""
import argparse
import json
import re
import sys

AXIS_RANK = {"academic": 0, "readability": 1, "humanness": 2}

TEMPLATE_KO = """아래 지점에서 독자가 멈췄다.

{drops}

이건 고치라는 목록이 아니라 독자가 어디서 떨어졌는지의 좌표다.
문장을 살려두고 주변을 손봐도 되고, 문단을 통째로 버려도 된다. 다시 써라."""

TEMPLATE_EN = """Readers stopped at the places below.

{drops}

This is not a list of fixes. It is a set of coordinates showing where readers fell off.
You can keep a sentence and rework what surrounds it, or throw a paragraph out entirely. Rewrite it."""

OSCILLATION_KO = "이 중 첫 번째 지점은 지난 라운드에도 독자가 멈춘 곳이다."
OSCILLATION_EN = "The first of these is a place where a reader stopped last round as well."

SENTENCE_END = re.compile(r"[.!?…。？！]+[\s\"'”’)\]]*|\n{2,}")


def sentence_spans(text: str):
    """글을 문장 단위로 잘라 (시작, 끝) 목록을 만든다. 겹침 판정에만 쓴다."""
    spans = []
    start = 0
    for m in SENTENCE_END.finditer(text):
        end = m.end()
        if end > start:
            spans.append((start, end))
            start = end
    if start < len(text):
        spans.append((start, len(text)))
    return spans


def sentence_index(spans, offset: int) -> int:
    for i, (s, e) in enumerate(spans):
        if s <= offset < e:
            return i
    return len(spans)


def load_drops(path, axis):
    if not path:
        return []
    data = json.load(open(path, encoding="utf-8"))
    if isinstance(data, dict):
        data = data.get("drops", [])
    return [dict(d, axis=axis) for d in data]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--text", required=True)
    ap.add_argument("--academic")
    ap.add_argument("--readability")
    ap.add_argument("--humanness")
    ap.add_argument("--prev-blockers", help="지난 라운드 blocker 의 quote 목록 JSON")
    ap.add_argument("--lang", default="ko", choices=["ko", "en"])
    args = ap.parse_args()

    text = open(args.text, encoding="utf-8").read()
    spans = sentence_spans(text)

    drops = (load_drops(args.academic, "academic")
             + load_drops(args.readability, "readability")
             + load_drops(args.humanness, "humanness"))

    for d in drops:
        off = text.find(d.get("quote", ""))
        if off < 0:
            print(f"quote not found in text: {d.get('quote','')!r}", file=sys.stderr)
            return 1
        d["_offset"] = off
        d["_sent"] = sentence_index(spans, off)

    prev_blockers = []
    if args.prev_blockers:
        prev_blockers = json.load(open(args.prev_blockers, encoding="utf-8"))
        if isinstance(prev_blockers, dict):
            prev_blockers = prev_blockers.get("quotes", [])

    # 그룹 = 같은 문장을 잡은 드롭들
    groups = {}
    for d in drops:
        groups.setdefault(d["_sent"], []).append(d)

    oscillating = set()
    for sent, members in groups.items():
        for d in members:
            if d.get("quote") in prev_blockers and d.get("quote") in text:
                oscillating.add(sent)

    def group_key(item):
        sent, members = item
        has_blocker = any(m.get("blocker") for m in members)
        return (0 if sent in oscillating else 1,
                0 if has_blocker else 1,
                min(m["_offset"] for m in members))

    ordered = []
    for _, members in sorted(groups.items(), key=group_key):
        ordered.extend(sorted(members, key=lambda m: (AXIS_RANK[m["axis"]], m["_offset"])))

    lines = "\n".join(f'- "{d["quote"]}" — {d["reason"]}' for d in ordered)
    template = TEMPLATE_KO if args.lang == "ko" else TEMPLATE_EN
    out = template.format(drops=lines)
    if oscillating:
        out += "\n" + (OSCILLATION_KO if args.lang == "ko" else OSCILLATION_EN)
    print(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
