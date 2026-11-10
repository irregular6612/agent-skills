#!/usr/bin/env python3
"""Check Q&A-style book notes (Obsidian vault, Public/Books) against the observed format.

Read-only. Standard library only.

Usage:
  check_book_note.py NOTE.md [NOTE.md ...]
  check_book_note.py --scan "<vault>/Public/Books"      # every .md under the folder
  options: --quiet (only FAIL/WARN lines), --no-style (hide separator/style warnings)

A file is treated as a Q&A book note when its linked-bases contain [[QA-Books.base]] or
[[SNU-100.base]], or its body has the "> 공부 방식:" line. Other files are reported as SKIP.

Exit code: 0 = no FAIL, 1 = at least one FAIL, 2 = usage error.
"""
import argparse
import re
import sys
from pathlib import Path

SNU_DIR_NAME = "서울대 권장도서 100선"
KEYS_SNU = ["Reading-Status", "Author", "Topic", "Comment", "URL", "linked-bases",
            "SNU-No", "Start-Date", "End-date", "type"]
KEYS_QA = [k for k in KEYS_SNU if k != "SNU-No"]
H2_ORDER = ["이 책의 핵심", "목차", "장별 핵심", "문답 기록", "출처와 불확실한 점"]
READING_STATUS = {"☑️ Not Started", "▶️ In progress", "✅ Done"}
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
QUOTE_CALLOUT = re.compile(r"^> \[!quote\] 저자가 가장 하고 싶은 말")
FM_RE = re.compile(r"^---\n(.*?)\n---\n?(.*)\Z", re.S)


def parse_frontmatter(text):
    """Minimal YAML subset parser: top-level keys, scalar values, '- item' lists.
    Returns (ordered list of (key, value), duplicate keys, body)."""
    m = FM_RE.match(text)
    if not m:
        return None, [], text
    items, seen, dups = [], set(), []
    cur = None
    for line in m.group(1).split("\n"):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        km = re.match(r"^([^\s\-#][^:]*):(.*)$", line)
        if km and not line.startswith((" ", "\t")):
            key, val = km.group(1).strip(), km.group(2).strip()
            if key in seen:
                dups.append(key)
            seen.add(key)
            cur = [key, val if val else None]
            items.append(cur)
            continue
        lm = re.match(r"^\s+-\s*(.*)$", line)
        if lm and cur is not None:
            if not isinstance(cur[1], list):
                cur[1] = [] if cur[1] is None else [cur[1]]
            cur[1].append(lm.group(1).strip())
    return [(k, v) for k, v in items], dups, m.group(2)


def unquote(s):
    s = s.strip()
    if len(s) >= 2 and s[0] == s[-1] and s[0] in "\"'":
        return s[1:-1]
    return s


def as_list(v):
    if v is None:
        return []
    if isinstance(v, list):
        return [unquote(x) for x in v if x.strip()]
    return [unquote(v)]


def strip_fences(body):
    """Return body lines with fenced code blocks blanked (keeps line count)."""
    out, fence = [], None
    for line in body.split("\n"):
        fm = re.match(r"^\s*(```|~~~)", line)
        if fm:
            tok = fm.group(1)
            if fence is None:
                fence = tok
            elif tok == fence:
                fence = None
            out.append("")  # fence lines themselves are not content headings
            continue
        out.append("" if fence else line)
    return out


def sections(lines):
    """Map H2 title -> (start, end) line indexes (exclusive end)."""
    idx = [(i, l[3:].strip()) for i, l in enumerate(lines) if l.startswith("## ")]
    res = []
    for n, (i, t) in enumerate(idx):
        end = idx[n + 1][0] if n + 1 < len(idx) else len(lines)
        res.append((t, i, end))
    return res


def find_vault_root(path):
    for p in [path.resolve().parent, *path.resolve().parents]:
        if (p / "_wiki").is_dir() and (p / "Public").is_dir():
            return p
    return None


def check(path, style=True, snu_seen=None):
    msgs = []  # (level, text)
    add = lambda lvl, t: msgs.append((lvl, t))
    text = path.read_text(encoding="utf-8")
    if text.startswith("﻿") or "\r\n" in text:
        add("FAIL", "BOM 또는 CRLF가 있다")
    fm, dups, body = parse_frontmatter(text.replace("\r\n", "\n").lstrip("﻿"))
    raw_lines = body.split("\n")
    lines = strip_fences(body)
    fmd = dict(fm or [])
    bases = as_list(fmd.get("linked-bases"))
    is_qa = (any(b in ("[[QA-Books.base]]", "[[SNU-100.base]]") for b in bases)
             or any(l.startswith("> 공부 방식:") for l in lines))
    if fm is None:
        return ("SKIP", [("INFO", "frontmatter 없음 — 문답 책 노트가 아님")]) if not is_qa else \
               ("FAIL", [("FAIL", "frontmatter 없음")])
    if not is_qa:
        return "SKIP", [("INFO", "QA-Books/SNU-100 base도 '공부 방식' 줄도 없음 — 문답 책 노트가 아님")]

    # ---------- frontmatter ----------
    keys = [k for k, _ in fm]
    has_snu = "SNU-No" in fmd
    expected = KEYS_SNU if has_snu else KEYS_QA
    for d in dups:
        add("FAIL", f"frontmatter 키 중복: {d}")
    missing = [k for k in expected if k not in fmd]
    extra = [k for k in keys if k not in expected]
    if missing:
        add("FAIL", f"frontmatter 키 누락: {', '.join(missing)}")
    if extra:
        add("WARN", f"관찰된 형식에 없는 frontmatter 키: {', '.join(extra)}")
    ordered = [k for k in keys if k in expected]
    if not missing and ordered != expected:
        add("FAIL", "frontmatter 키 순서가 다르다: " + " → ".join(ordered)
            + "  (기대: " + " → ".join(expected) + ")")

    if fmd.get("type") != "project":
        add("FAIL", f"type은 project여야 한다 (현재: {fmd.get('type')!r})")
    rs = as_list(fmd.get("Reading-Status"))
    if not rs:
        add("FAIL", "Reading-Status가 비어 있다 (새 노트는 ☑️ Not Started)")
    else:
        if not isinstance(fmd.get("Reading-Status"), list):
            add("WARN", "Reading-Status는 기존 노트처럼 YAML 리스트(  - ☑️ Not Started)로 쓴다")
        for v in rs:
            if v not in READING_STATUS:
                add("WARN", f"Reading-Status 값이 관찰된 값이 아니다: {v!r}")
    for k in ("Author", "Topic"):
        if not as_list(fmd.get(k)):
            add("FAIL", f"{k}가 비어 있다")
        elif not isinstance(fmd.get(k), list):
            add("WARN", f"{k}는 기존 노트처럼 YAML 리스트로 쓴다")
    for k in ("Comment", "URL"):
        if not fmd.get(k) or isinstance(fmd.get(k), list):
            add("FAIL", f"{k}는 한 줄 스칼라 값이어야 한다")
    for k in ("Start-Date", "End-date"):
        v = fmd.get(k)
        if v is not None and (isinstance(v, list) or not DATE_RE.match(unquote(v))):
            add("FAIL", f"{k}는 비우거나 YYYY-MM-DD여야 한다 (현재: {v!r})")

    # ---------- placement / bases ----------
    in_snu_dir = path.resolve().parent.name == SNU_DIR_NAME
    if has_snu:
        raw = unquote(str(fmd.get("SNU-No") or ""))
        if not raw.isdigit() or not 1 <= int(raw) <= 100:
            add("FAIL", f"SNU-No는 1~100 정수여야 한다 (현재: {raw!r})")
        else:
            if snu_seen is not None:
                if raw in snu_seen:
                    add("FAIL", f"SNU-No {raw} 중복: {snu_seen[raw]}")
                snu_seen[raw] = path.name
        if "[[SNU-100.base]]" not in bases:
            add("FAIL", "SNU-No가 있는데 linked-bases에 [[SNU-100.base]]가 없다")
        if not in_snu_dir:
            add("WARN", f"SNU 책인데 '{SNU_DIR_NAME}/' 폴더 밖에 있다 (97번 이기적 유전자만 예외)")
    else:
        if in_snu_dir:
            add("FAIL", f"'{SNU_DIR_NAME}/' 폴더 안인데 SNU-No가 없다")
        if "[[QA-Books.base]]" not in bases:
            add("FAIL", "100선 밖 책은 linked-bases에 [[QA-Books.base]]가 있어야 한다")
        if "[[SNU-100.base]]" in bases:
            add("FAIL", "SNU-No 없이 [[SNU-100.base]]를 달았다")
    root = find_vault_root(path)
    if root is not None:
        for b in bases:
            m = re.match(r"^\[\[(.+?)\]\]$", b)
            if m and not list((root / "_wiki" / "bases").rglob(m.group(1))):
                add("FAIL", f"linked-bases 대상이 _wiki/bases/에 없다: {b}")

    # ---------- body ----------
    h1 = [l for l in lines if l.startswith("# ")]
    if len(h1) != 1:
        add("FAIL", f"H1(# 제목 (저자))이 정확히 1개여야 한다 (현재 {len(h1)}개)")
    elif not re.search(r"\(.+\)\s*$", h1[0]):
        add("WARN", "H1은 '# 제목 (저자 한국어 이름)' 꼴이 보통이다")
    if not any(l.startswith("> 공부 방식:") for l in lines):
        add("WARN", "머리 인용문 '> 공부 방식: …' 줄이 없다")
    if not any(re.match(r"^> (정리한|공부한) 날짜: \d{4}-\d{2}-\d{2}", l) for l in lines):
        add("WARN", "머리 인용문 '> 정리한 날짜: YYYY-MM-DD (아직 문답 전)' 또는 '> 공부한 날짜:' 줄이 없다")
    if not any(l.startswith("| 항목 |") for l in lines):  # 두 권 묶음은 '| 항목 | 책A | 책B |'
        add("WARN", "서지 표(| 항목 | 내용 |)가 없다")

    secs = sections(lines)
    titles = [t for t, _, _ in secs]
    pos = [titles.index(h) if h in titles else -1 for h in H2_ORDER]
    absent = [h for h, p in zip(H2_ORDER, pos) if p < 0]
    if absent:
        add("FAIL", "필수 H2 누락: " + ", ".join(absent))
    present = [p for p in pos if p >= 0]
    if present != sorted(present):
        add("FAIL", "필수 H2 순서가 다르다: " + " → ".join(t for t in titles if t in H2_ORDER))
    others = [t for t in titles if t not in H2_ORDER]
    if others:
        add("WARN", "관찰된 형식에 없는 H2: " + ", ".join(others))
    sec = {t: (s, e) for t, s, e in secs}

    def content(t, raw=False):
        s, e = sec[t]
        src = raw_lines if raw else lines
        return src[s + 1:e]

    if "이 책의 핵심" in sec:
        c = content("이 책의 핵심")
        if not any(l.startswith("**한 줄로 먼저:") for l in c):
            add("WARN", "이 책의 핵심 첫머리에 '**한 줄로 먼저: …**' 줄이 없다")
        h3 = [l[4:] for l in c if l.startswith("### ")]
        if not any(x.startswith("꼭 잡아야 할") for x in h3):
            add("WARN", "'### 꼭 잡아야 할 개념 N개'(또는 인물과 주제) 소절이 없다")
        if not any(x.startswith("흔한 오해") for x in h3):
            add("WARN", "'### 흔한 오해' 소절이 없다")
    if "목차" in sec:
        c = content("목차", raw=True)
        if not any(re.match(r"^\s*(```|~~~)", l) for l in c):
            add("WARN", "목차가 코드블록에 원문 그대로 들어 있지 않다")
        if any(re.match(r"^L\d+: ", l) for l in c):
            add("WARN", "목차에 웹 추출 흔적(L123: …)이 남아 있다")
    if "장별 핵심" in sec:
        c = content("장별 핵심")
        nq = sum(1 for l in c if QUOTE_CALLOUT.match(l))
        if nq == 0:
            add("FAIL", "장별 핵심에 '> [!quote] 저자가 가장 하고 싶은 말' callout이 없다")
        for i, l in enumerate(c):
            if QUOTE_CALLOUT.match(l):
                nxt = c[i + 1] if i + 1 < len(c) else ""
                if not nxt.startswith("> ") or not nxt[2:].strip():
                    add("FAIL", f"'저자가 가장 하고 싶은 말' callout 다음 줄에 한 문장이 없다 (장별 핵심 {i + 1}번째 줄)")
    sessions = []
    if "문답 기록" in sec:
        c = content("문답 기록")
        for l in c:
            if l.startswith("### "):
                t = l[4:].strip()
                if DATE_RE.match(t):
                    sessions.append(t)
                else:
                    add("FAIL", f"문답 기록의 소절 제목은 '### YYYY-MM-DD'여야 한다: {t!r}")
        if sessions != sorted(sessions):
            add("WARN", "문답 기록 날짜가 오래된 순서가 아니다")
    if "출처와 불확실한 점" in sec:
        if not any(l.strip() for l in content("출처와 불확실한 점")):
            add("FAIL", "출처와 불확실한 점이 비어 있다")

    # ---------- status consistency (warn only; status is human-owned) ----------
    start = fmd.get("Start-Date")
    end = fmd.get("End-date")
    if sessions and not start:
        add("WARN", f"문답 기록({sessions[0]})이 있는데 Start-Date가 비어 있다")
    if start and sessions and unquote(start) != sessions[0]:
        add("WARN", f"Start-Date({unquote(start)})가 첫 문답 날짜({sessions[0]})와 다르다")
    if "✅ Done" in rs and not end:
        add("WARN", "Reading-Status가 ✅ Done인데 End-date가 비어 있다")
    if end and "✅ Done" not in rs:
        add("WARN", "End-date가 있는데 Reading-Status가 ✅ Done이 아니다")
    if has_snu and sessions and "[[QA-Books.base]]" not in bases:
        add("WARN", "문답을 시작한 100선 책인데 [[QA-Books.base]]가 없다 (이기적 유전자 선례)")

    # ---------- style ----------
    if style:
        for t, s, _ in secs[1:]:
            prev = [l for l in lines[:s] if l.strip()]
            if not prev or prev[-1].strip() != "---":
                add("STYLE", f"'## {t}' 앞에 구분선(---)이 없다")

    levels = {lvl for lvl, _ in msgs}
    status = "FAIL" if "FAIL" in levels else ("WARN" if levels & {"WARN", "STYLE"} else "PASS")
    return status, msgs


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("paths", nargs="*", type=Path)
    ap.add_argument("--scan", type=Path, help="이 폴더 아래 .md 전부 검사")
    ap.add_argument("--quiet", action="store_true", help="PASS/SKIP 줄 숨기기")
    ap.add_argument("--no-style", action="store_true", help="구분선 등 STYLE 경고 숨기기")
    a = ap.parse_args(argv)
    files = list(a.paths)
    if a.scan:
        files += sorted(p for p in a.scan.rglob("*.md") if "assets" not in p.parts)
    if not files:
        ap.print_usage(sys.stderr)
        return 2
    counts, snu_seen = {}, {}
    for f in files:
        status, msgs = check(f, style=not a.no_style, snu_seen=snu_seen)
        counts[status] = counts.get(status, 0) + 1
        if a.quiet and status in ("PASS", "SKIP"):
            continue
        print(f"{status:5} {f}")
        for lvl, t in msgs:
            if lvl == "INFO" and a.quiet:
                continue
            print(f"      [{lvl}] {t}")
    print("요약: " + ", ".join(f"{k} {v}" for k, v in sorted(counts.items())))
    return 1 if counts.get("FAIL") else 0


if __name__ == "__main__":
    sys.exit(main())
