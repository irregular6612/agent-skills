#!/usr/bin/env python3
"""드롭의 `quote`가 현재본에 한 글자도 안 틀리고 들어 있는지 확인한다.

왜 확인하는가: `quote` 정확 일치는 두 가지를 동시에 한다.
  1. 환각 방지 — 판정자가 글에 없는 구절을 지어내면 여기서 걸린다.
  2. 진동 탐지의 유일한 입력 — 지난 라운드 blocker 의 quote 가 이번 본문에
     그대로 살아 있으면 그 지점이 안 고쳐졌다는 뜻이다. 스니펫 생존이
     동일성 판정의 전부이므로, 한 글자라도 흔들리면 이 신호가 죽는다.

불일치가 나오면 그 판정자에게 1회만 재요청하고, 재차 실패하면 그 드롭은
폐기하고 로그에 남긴다(드라이버가 한다).

사용:
  python3 verify_quotes.py 현재본.md drops-readability.json [drops-academic.json ...]
출력(JSON):
  {"ok": false, "checked": 20, "missing": [{"file": "...", "index": 3, "quote": "..."}]}
종료 코드는 전부 일치하면 0, 하나라도 어긋나면 1.
"""
import json
import sys


def main() -> int:
    if len(sys.argv) < 3:
        print("usage: verify_quotes.py <current.md> <drops.json> [...]", file=sys.stderr)
        return 2
    text = open(sys.argv[1], encoding="utf-8").read()
    missing = []
    checked = 0
    for path in sys.argv[2:]:
        drops = json.load(open(path, encoding="utf-8"))
        if isinstance(drops, dict):          # 봉투로 감싸 온 경우
            drops = drops.get("drops", [])
        for i, drop in enumerate(drops):
            checked += 1
            if drop.get("quote", "") not in text:
                missing.append({"file": path, "index": i, "quote": drop.get("quote", "")})
    print(json.dumps({"ok": not missing, "checked": checked, "missing": missing},
                     ensure_ascii=False, indent=2))
    return 0 if not missing else 1


if __name__ == "__main__":
    sys.exit(main())
