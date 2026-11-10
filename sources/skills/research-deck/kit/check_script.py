#!/usr/bin/env python3
"""Mechanical gate for speaker scripts. Run after build.js (needs out/manifest.json).

usage: python3 check_script.py <talk>/build [--sources <talk>/sources] [--lang ko]

Checks, per build:
  missing   build has no script
  numbers   a number in the script appears nowhere in the deck (slides, notes) or in sources/*.md
  banned    punctuation/phrases the voice never uses (ko list below; en: dashes, semicolons, "!")
  opener    three builds in a row open with the same first word
Exit 1 if anything other than "opener" is found.
"""
import argparse, json, re, sys
from pathlib import Path

BANNED = {
    "ko": [r"—", r"–", r"(?<!\d):(?!\d)", r";", r"!", r"…", r"\.\.\.", r'"', "다양한", "핵심적", "중요한 역할", "보여줍니다", "것입니다", "라는 점에서"],
    "en": [r"—", r";", r"!"],
}
NUM = re.compile(r"\d+(?:[.,]\d+)*")


def norm(n):
    return n.replace(",", "")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("build")
    ap.add_argument("--sources")
    ap.add_argument("--lang", default="ko")
    a = ap.parse_args()
    build = Path(a.build)
    man = json.loads((build / "out" / "manifest.json").read_text())
    src = Path(a.sources) if a.sources else build.parent / "sources"
    corpus = " ".join(p.read_text() for p in src.glob("*.md")) if src.exists() else ""
    deck = " ".join(" ".join(b["onSlide"] + [b.get("notes") or ""]) for b in man)
    known_all = {norm(n) for n in NUM.findall(corpus + " " + deck)}
    bad, warn, prev = [], [], []
    for b in man:
        t = b.get("script") or ""
        tag = f"{b['n']:>3} {b['key']}"
        if not t:
            bad.append(f"{tag}  missing")
            continue
        here = {norm(n) for n in NUM.findall(" ".join(b["onSlide"] + [b.get("notes") or "", b.get("title") or ""]))}
        stray = [n for n in NUM.findall(t) if norm(n) not in here | known_all and len(norm(n).replace(".", "")) > 1]
        if stray:
            bad.append(f"{tag}  numbers not on slide/notes/sources: {', '.join(stray)}")
        hits = [p for p in BANNED.get(a.lang, []) if re.search(p, t)]
        if hits:
            bad.append(f"{tag}  banned: {' '.join(hits)}")
        first = t.split()[0] if t.split() else ""
        prev = (prev + [first])[-3:]
        if len(prev) == 3 and len(set(prev)) == 1:
            warn.append(f"{tag}  three builds open with '{first}'")
    for line in bad + warn:
        print(line)
    print(f"{len(man)} builds, {len(bad)} problems, {len(warn)} warnings")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
