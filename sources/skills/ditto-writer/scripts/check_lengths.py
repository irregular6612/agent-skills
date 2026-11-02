#!/usr/bin/env python3
"""스킬이 저장·누적하는 파일의 길이 상한 검사 (상한표: references/formats.md "길이 상한").

사용:
  python3 check_lengths.py --profile <profiles/이름>     # 프로필 폴더 (+ 인용 원문 대조)
  python3 check_lengths.py --work <작업폴더>              # 작업 폴더
  python3 check_lengths.py <파일> [<파일> ...]            # 파일 이름으로 규칙을 골라 검사

단어 = 공백으로 나눈 토큰 (영어 단어, 한국어 어절). 상한을 넘으면 종료 코드 1.
--profile 은 추가로:
  - 실행별 중간 파일(_work/, analysis/, stage*_run*.md)이 남아 있으면 FAIL
  - profile.md · evidence.md 의 `백틱` 인용과 Anchors 절의 '> ' 인용이 sample.md 에 글자 그대로 있는지 확인
    (백틱은 샘플 인용 전용. ID·파일 이름·옵션은 백틱에 넣지 않는다. 예외로 L1-.., H-.., x=.., *.json/*.md 는 건너뛴다)
"""
import argparse, fnmatch, os, re, sys

# (파일 이름 패턴, 종류, 상한, 설명)  종류: words | lines | rowchars | none
RULES = [
    ('profile.md', 'words', 700, '프로필 (writer 가 매 라운드 읽음)'),
    ('evidence.md', 'words', 1200, '근거 (Stage 1/2 병합 인용·계량)'),
    ('meta.yaml', 'lines', 25, '프로필 메타'),
    ('sample.md', 'none', 0, '샘플 원문 (상한 없음)'),
    ('sample_raw.md', 'none', 0, '샘플 원문 (상한 없음)'),
    ('counts.json', 'none', 0, '기계 출력'),
    ('stage1_run*.md', 'words', 1500, 'Stage 1 run (임시, 병합 뒤 삭제)'),
    ('stage2_run*.md', 'words', 1500, 'Stage 2 run (임시, 조립 뒤 삭제)'),
    ('stage1.md', 'words', 1200, 'Stage 1 병합 (임시, 조립 뒤 삭제)'),
    ('BRIEF.md', 'words', 900, '작업 규칙 (덮어쓰기로 갱신)'),
    ('BRIEF_v*.md', 'words', 900, '이전 BRIEF (필요할 때만)'),
    ('CHANGELOG.md', 'rowchars', 200, '버전·리뷰당 한 행'),
    ('writer_r*.md', 'words', 600, 'writer 라운드 노트'),
    ('blind_r*_*.md', 'words', 600, '블라인드 보고서'),
    ('external_reports.md', 'none', 0, '사용자가 붙여 넣은 외부 판독 원문'),
    ('*.txt', 'words', 300, 'logs/ 의 codex 마지막 메시지'),
    ('*.md', 'words', 1000, 'prompts/ 의 프롬프트 사본'),
]
SKIP_DIRS = {'final', 'render'}
SKIP_FILES = {'v0_context.md'}  # 원문에서 뽑은 맥락 (원문 길이를 따른다)


def rule_for(path):
    name = os.path.basename(path)
    parent = os.path.basename(os.path.dirname(os.path.abspath(path)))
    if name in SKIP_FILES or re.match(r'v\d+\.(json|md|docx)$', name):
        return None
    if parent in ('logs', 'prompts'):  # 사본·로그는 이름과 상관없이 폴더 규칙
        pats = ('*.txt',) if parent == 'logs' else ('*.md',)
        for pat, kind, cap, desc in RULES:
            if pat in pats and fnmatch.fnmatch(name, pat):
                return kind, cap, desc
        return None
    for pat, kind, cap, desc in RULES:
        if pat in ('*.txt', '*.md'):
            continue
        if fnmatch.fnmatch(name, pat):
            return kind, cap, desc
    return None


def measure(path, kind, cap):
    text = open(path, encoding='utf-8', errors='replace').read()
    if kind == 'words':
        n = len(text.split())
        return n, n <= cap, f'{n}단어 / {cap}'
    if kind == 'lines':
        n = len(text.rstrip('\n').splitlines())
        return n, n <= cap, f'{n}줄 / {cap}'
    if kind == 'rowchars':
        rows = [l for l in text.splitlines() if l.startswith('|') and not re.match(r'^\|[\s:|-]+\|?$', l)]
        long = [(i, len(l)) for i, l in enumerate(rows) if len(l) > cap]
        worst = max((len(l) for l in rows), default=0)
        return worst, not long, f'행 {len(rows)}개, 최장 {worst}자 / {cap}' + (f', 초과 {len(long)}행' if long else '')
    return 0, True, '상한 없음'


QUOTE_SKIP = re.compile(r'^(L1-|H-\d|N-?\d|A\d$|S\d|\w+=|--|[\w./-]+\.(json|md|py|yaml)$)')


def norm_ws(s):
    return re.sub(r'\s+', ' ', s).strip()


def verify_quotes(folder):
    sample_path = os.path.join(folder, 'sample.md')
    if not os.path.exists(sample_path):
        return ['sample.md 없음']
    sample = norm_ws(open(sample_path, encoding='utf-8').read())
    bad = []
    for fname in ('profile.md', 'evidence.md'):
        p = os.path.join(folder, fname)
        if not os.path.exists(p):
            continue
        text = open(p, encoding='utf-8').read()
        quotes = [q for q in re.findall(r'`([^`\n]+)`', text) if not QUOTE_SKIP.match(q)]
        anchors = []
        m = re.search(r'^## [^\n]*Anchors[^\n]*\n(.*?)(?=^## |\Z)', text, re.M | re.S)
        if m:
            anchors = [norm_ws(l[1:]) for l in m.group(1).splitlines() if l.startswith('>')]
        for q in quotes + anchors:
            if norm_ws(q) not in sample:
                bad.append(f'{fname}: "{q[:70]}"')
        print(f'  인용 대조 {fname}: 백틱 {len(quotes)}개 + anchor {len(anchors)}개, 원문에 없음 '
              f'{sum(1 for b in bad if b.startswith(fname))}개')
    return bad


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--profile')
    ap.add_argument('--work')
    ap.add_argument('files', nargs='*')
    a = ap.parse_args()

    targets, fails = list(a.files), []
    for root in (a.profile, a.work):
        if not root:
            continue
        for dp, dns, fns in os.walk(root):
            dns[:] = [d for d in dns if d not in SKIP_DIRS]
            targets += [os.path.join(dp, f) for f in sorted(fns)]

    for p in targets:
        r = rule_for(p)
        if r is None:
            continue
        kind, cap, desc = r
        n, ok, msg = measure(p, kind, cap)
        if kind != 'none':
            print(f'{"OK  " if ok else "OVER"} {os.path.relpath(p)}  {msg}  ({desc})')
        if not ok:
            fails.append(f'{os.path.relpath(p)}: {msg}')

    if a.profile:
        leftovers = [os.path.relpath(os.path.join(dp, f)) for dp, _, fns in os.walk(a.profile) for f in fns
                     if re.match(r'stage[12](_run\d+)?\.md$', f) or '/_work' in dp or '/analysis' in dp]
        if leftovers:
            fails.append(f'병합 뒤 남은 중간 파일: {leftovers}')
        fails += [f'인용 불일치 {b}' for b in verify_quotes(a.profile)]

    if fails:
        print('\nFAIL:')
        for f in fails:
            print(' -', f)
        sys.exit(1)
    print('\n길이 상한 통과')


if __name__ == '__main__':
    main()
