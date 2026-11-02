#!/usr/bin/env python3
"""버전 하나를 v0 와 기계적으로 대조한다 (내용 대조는 사람/모델 몫, 여기선 숫자만).

사용:
  python3 check_version.py <v0.json|v0.md> <vN.json|vN.md> [--meta v0_meta.json] [--sample SAMPLE.md] [--tol 0.15]

출력:
  - 단위별 단어(영문)·어절(한글) 수 v0 -> vN (인라인 수식 하나 = 1단어), 전체 증감률 (±tol 넘으면 FAIL)
  - 키 불일치 (json, FAIL), 수식 도입부 끝맺음 (meta 의 leadins 또는 md 의 다음 블록이 $$, WARN)
  - 본문에 남은 날 유니코드 수식 문자 (p̂, lⱼ, ₋₁ 등) / $ 짝
  - 대시(— –) 개수, 문장 길이 평균·표준편차·변동계수(CV): 대상 전체 vs 사용자 샘플
    (샘플보다 CV 가 눈에 띄게 낮으면 '문장 길이 고름' 신호)
종료 코드: 기계 검사 FAIL 이 하나라도 있으면 1.
"""
import argparse, json, os, re, statistics, sys

RAW_MATH = re.compile('[̂̃̄̅̇ⱼᵢⱼ₊-₎₀-₉⁰¹²³⁴-⁹≤≥≠≈∈∞∑∏]')


def load(path):
    if path.endswith('.json'):
        return json.load(open(path, encoding='utf-8')), 'json'
    text = open(path, encoding='utf-8').read()
    blocks = [b.strip() for b in re.split(r'\n\s*\n', text) if b.strip()]
    return {str(i): b for i, b in enumerate(blocks)}, 'md'


def prose(t):
    t = re.sub(r'\$\$.*?\$\$', 'X', t, flags=re.S)
    return re.sub(r'(?<!\\)\$[^$]*(?<!\\)\$', 'X', t)


def words(t):
    return len(prose(t).split())


def sentences(t):
    t = prose(t)
    return [s for s in re.split(r'(?<=[.!?])\s+|(?<=[.!?])(?=[A-Z])', t) if s.strip()]


def spread(texts):
    lens = [len(s.split()) for t in texts for s in sentences(t)]
    if len(lens) < 2:
        return None
    mu, sd = statistics.mean(lens), statistics.pstdev(lens)
    return mu, sd, sd / mu if mu else 0, len(lens)


def is_equation_block(b):
    return b.startswith('$$') or b.startswith('```math') or b.startswith('\\[')


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('v0')
    ap.add_argument('vn')
    ap.add_argument('--meta', default=None)
    ap.add_argument('--sample', default=None, help='사용자 샘플 텍스트 파일 (SAMPLE.md). 주면 문장 길이 분포를 비교')
    ap.add_argument('--tol', type=float, default=0.15)
    a = ap.parse_args()

    v0, kind = load(a.v0)
    vn, _ = load(a.vn)
    fails, warns = [], []

    meta_path = a.meta or os.path.join(os.path.dirname(os.path.abspath(a.v0)), 'v0_meta.json')
    meta = json.load(open(meta_path, encoding='utf-8')) if kind == 'json' and os.path.exists(meta_path) else None

    if kind == 'json':
        if set(v0) != set(vn):
            fails.append(f'키 불일치: 빠짐 {sorted(set(v0) - set(vn), key=int)}, 추가 {sorted(set(vn) - set(v0), key=int)}')
        keys = sorted(set(v0) & set(vn), key=int)
        leadins = {str(i) for i in (meta or {}).get('leadins', [])}
        compare = [(k, v0[k], vn[k]) for k in keys]
    else:
        # md: 블록 수가 다를 수 있으니 전체만 비교, 수식 도입부는 vN 안에서 직접 찾는다
        keys = list(vn)
        leadins = {k for k in keys if int(k) + 1 < len(keys) and is_equation_block(vn[str(int(k) + 1)])}
        compare = [('전체', '\n\n'.join(v0.values()), '\n\n'.join(b for b in vn.values()))]

    print(f'{"단위":>6} {"v0":>5} {"vN":>5}  변화')
    w0 = wn = 0
    for k, a0, an in compare:
        if kind == 'md' or not is_equation_block(an):
            c0, cn = words(a0), words(an)
            w0 += c0; wn += cn
            print(f'{k:>6} {c0:>5} {cn:>5}  {cn - c0:+d}')
    delta = (wn - w0) / w0 if w0 else 0
    status = 'OK' if abs(delta) <= a.tol else 'FAIL'
    print(f'{"합계":>6} {w0:>5} {wn:>5}  {delta:+.1%}  [{status} ±{a.tol:.0%}]')
    if status == 'FAIL':
        fails.append(f'길이 {delta:+.1%}')

    for k in sorted(leadins, key=int):
        if k in vn and not vn[k].rstrip().endswith(':') and (kind == 'md' or v0.get(k, '').rstrip().endswith(':')):
            warns.append(f'[{k}] 수식 도입부가 ":" 로 끝나지 않는다 → 다음 수식을 여전히 이끄는지 눈으로 확인')

    for k in keys:
        t = vn[k]
        if kind == 'md' and is_equation_block(t):
            continue
        raw = RAW_MATH.findall(prose(t))
        if raw:
            fails.append(f'[{k}] 본문에 날 유니코드 수식 문자 {"".join(sorted(set(raw)))} → $...$ 인라인 수식이나 말로 풀기')
        if len(re.findall(r'(?<!\\)\$', t)) % 2:
            fails.append(f'[{k}] $ 짝이 안 맞는다')

    allt = [vn[k] for k in keys if not is_equation_block(vn[k])]
    dashes = sum(t.count('—') + t.count('–') for t in allt)
    print(f'대시(— –): {dashes}개' + ('  ← 샘플에 대시가 없으면 0 으로' if dashes else ''))

    sample_texts = []
    if a.sample:
        sample_texts = [open(a.sample, encoding='utf-8').read()]
    sp_t, sp_s = spread(allt), spread(sample_texts) if sample_texts else None
    if sp_t:
        print(f'문장 길이(대상): 평균 {sp_t[0]:.1f}, 표준편차 {sp_t[1]:.1f}, CV {sp_t[2]:.2f}, 문장 {sp_t[3]}개')
    if sp_s:
        print(f'문장 길이(샘플): 평균 {sp_s[0]:.1f}, 표준편차 {sp_s[1]:.1f}, CV {sp_s[2]:.2f}, 문장 {sp_s[3]}개')
        if sp_t and sp_t[2] < sp_s[2] * 0.7:
            print('  ← 대상 문장 길이가 샘플보다 훨씬 고르다 (AI 신호 가능)')

    if warns:
        print('\nWARN:')
        for w in warns:
            print(' -', w)
    if fails:
        print('\nFAIL:')
        for f in fails:
            print(' -', f)
        sys.exit(1)
    print('\n기계 검사 통과 (의미 보존은 content ledger 로 따로 확인)')


if __name__ == '__main__':
    main()
