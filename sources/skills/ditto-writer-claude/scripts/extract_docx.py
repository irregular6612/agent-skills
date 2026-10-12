#!/usr/bin/env python3
"""docx 본문 문단을 v0.json + v0_context.md + v0_meta.json 으로 뽑는다. 원본은 읽기만 한다.

사용:
  python3 extract_docx.py <src.docx> <out_dir> [--sample 2] [--fixed 0,22] [--target 4,7,8]
  python3 extract_docx.py <final.docx> --text-out <document.txt>   # 블라인드용 평문 (표지 없음)

인덱스는 python-docx 의 document.paragraphs 순서(0부터, 빈 문단 포함)다.
처음에는 옵션 없이 한 번 돌려 v0_context.md 의 번호를 보고, 사용자와 고정/샘플 범위를
확정한 뒤 옵션을 붙여 다시 돌리면 된다.

자동 분류:
  - 빈 문단                        -> 건너뜀 (맥락에도 안 나옴)
  - 텍스트 없이 수식만 있는 문단     -> EQUATION (고정)
  - 스타일 Title/Subtitle/Heading* -> HEADING (고정)
  - --sample 에 든 문단            -> USER SAMPLE (고정, 문체 기준)
  - --fixed 에 든 문단             -> FIXED
  - --target 을 주면 그 문단만 TARGET, 나머지 텍스트 문단은 FIXED
  - --target 을 안 주면 위에 안 걸린 텍스트 문단은 모두 TARGET
TARGET 문단 안의 인라인 수식은 $...$ (apply_docx.py 가 읽는 문법)로 바꿔 v0.json 에 넣는다.
바로 다음 비어 있지 않은 문단이 EQUATION 인 TARGET 은 '수식 도입부'로 표시한다.
한계: 표·텍스트 상자·각주 안의 문단은 다루지 않는다.
"""
import argparse, json, os, re, sys
import docx

M = 'http://schemas.openxmlformats.org/officeDocument/2006/math'
W = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
ACC = {'̂': r'\hat', '̃': r'\tilde', '̄': r'\bar', '̅': r'\bar', '̇': r'\dot'}


def local(tag):
    return tag.split('}', 1)[-1]


def child(el, name):
    return el.find(f'{{{M}}}{name}')


def tex(el):
    """OMML 요소 -> apply_docx.py 가 다시 읽을 수 있는 LaTeX 비슷한 한 줄."""
    if el is None:
        return ''
    tag = local(el.tag)
    if tag == 't':
        return el.text or ''
    if tag.endswith('Pr'):
        return ''
    if tag == 'acc':
        pr = child(el, 'accPr')
        c = '̂'
        if pr is not None and child(pr, 'chr') is not None:
            c = child(pr, 'chr').get(f'{{{M}}}val', c)
        return ACC.get(c, ACC['\u0302']) + '{' + tex(child(el, 'e')) + '}'
    if tag in ('sSub', 'sSup', 'sSubSup'):
        base = tex(child(el, 'e'))
        base = base if len(base) == 1 else '{' + base + '}'
        out = base
        if child(el, 'sub') is not None:
            out += '_{' + tex(child(el, 'sub')) + '}'
        if child(el, 'sup') is not None:
            out += '^{' + tex(child(el, 'sup')) + '}'
        return out
    if tag == 'f':
        return r'\frac{' + tex(child(el, 'num')) + '}{' + tex(child(el, 'den')) + '}'
    if tag == 'd':
        pr = child(el, 'dPr')
        beg, end, sep = '(', ')', ','
        if pr is not None:
            for name, cur in (('begChr', beg), ('endChr', end), ('sepChr', sep)):
                c = child(pr, name)
                if c is not None:
                    v = c.get(f'{{{M}}}val', cur)
                    if name == 'begChr': beg = v
                    elif name == 'endChr': end = v
                    else: sep = v
        parts = [tex(e) for e in el.findall(f'{{{M}}}e')]
        return beg + sep.join(parts) + end
    return ''.join(tex(k) for k in el)


def para_parts(p):
    """문단 -> (텍스트, 인라인수식 개수). 수식은 $...$ 로 감싼다."""
    out, n_math = [], 0
    for el in p._p.iter():
        tag, ns = local(el.tag), el.tag.split('}')[0][1:]
        if ns == W and tag == 't' and not any(a.tag == f'{{{M}}}oMath' for a in el.iterancestors()):
            out.append((el.text or '').replace('$', '\\$'))
        elif ns == W and tag == 'tab' and not any(a.tag == f'{{{M}}}oMath' for a in el.iterancestors()):
            out.append('\t')
        elif ns == M and tag == 'oMath':
            out.append('$' + tex(el) + '$')
            n_math += 1
    return ''.join(out), n_math


def ints(s):
    return {int(x) for x in s.split(',') if x.strip()} if s else set()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('src')
    ap.add_argument('out_dir', nargs='?')
    ap.add_argument('--sample', default='', help='사용자가 직접 쓴 문단 인덱스 (쉼표 구분)')
    ap.add_argument('--fixed', default='', help='고정 문단 인덱스 (쉼표 구분)')
    ap.add_argument('--target', default='', help='고쳐 쓸 문단 인덱스. 주면 이것만 TARGET')
    ap.add_argument('--text-out', default=None, help='표지 없는 평문만 이 파일로 쓰고 끝낸다 (블라인드 판독용)')
    a = ap.parse_args()

    if a.text_out:
        paras = [para_parts(p)[0].replace('\\$', '$').strip() for p in docx.Document(a.src).paragraphs]
        with open(a.text_out, 'w', encoding='utf-8') as f:
            f.write('\n\n'.join(t for t in paras if t) + '\n')
        print('wrote', a.text_out)
        return
    if not a.out_dir:
        sys.exit('out_dir 가 필요하다 (또는 --text-out)')

    sample, fixed, target = ints(a.sample), ints(a.fixed), ints(a.target)
    overlap = (sample & fixed) | (sample & target) | (fixed & target)
    if overlap:
        sys.exit(f'겹치는 인덱스: {sorted(overlap)}')

    d = docx.Document(a.src)
    P = d.paragraphs
    for i in sample | fixed | target:
        if i >= len(P):
            sys.exit(f'인덱스 {i} 가 문단 수 {len(P)} 를 넘는다')

    units = []
    for i, p in enumerate(P):
        text, n_math = para_parts(p)
        has_text = bool(text.replace('$', '').strip()) if n_math else bool(text.strip())
        only_math = n_math > 0 and not re.sub(r'\$[^$]*\$', '', text).strip()
        if not text.strip():
            continue
        style = (p.style.name or '') if p.style is not None else ''
        if only_math:
            kind = 'EQUATION'
        elif i in sample:
            kind = 'USER SAMPLE'
        elif i in fixed:
            kind = 'FIXED'
        elif i in target:
            kind = 'TARGET'
        elif re.match(r'(Title|Subtitle|Heading)', style, re.I):
            kind = 'HEADING'
        elif target:
            kind = 'FIXED'
        else:
            kind = 'TARGET' if has_text else 'FIXED'
        units.append({'idx': i, 'kind': kind, 'style': style, 'text': text,
                      'inline_math': n_math if kind != 'EQUATION' else 0,
                      'words': len(re.sub(r'\$[^$]*\$', 'X', text).split())})

    for j, u in enumerate(units):
        u['leadin'] = (u['kind'] == 'TARGET' and j + 1 < len(units)
                       and units[j + 1]['kind'] == 'EQUATION')

    os.makedirs(a.out_dir, exist_ok=True)
    v0 = {str(u['idx']): u['text'].strip() for u in units if u['kind'] == 'TARGET'}
    with open(os.path.join(a.out_dir, 'v0.json'), 'w', encoding='utf-8') as f:
        json.dump(v0, f, ensure_ascii=False, indent=2)

    meta = {
        'src': os.path.abspath(a.src),
        'paragraph_count': len(P),
        'targets': [u['idx'] for u in units if u['kind'] == 'TARGET'],
        'sample': [u['idx'] for u in units if u['kind'] == 'USER SAMPLE'],
        'leadins': [u['idx'] for u in units if u['leadin']],
        'target_words': sum(u['words'] for u in units if u['kind'] == 'TARGET'),
        'sample_words': sum(u['words'] for u in units if u['kind'] == 'USER SAMPLE'),
        'units': [{k: u[k] for k in ('idx', 'kind', 'style', 'words', 'inline_math', 'leadin')} for u in units],
    }
    with open(os.path.join(a.out_dir, 'v0_meta.json'), 'w', encoding='utf-8') as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    lines = [f'<!-- 원본: {os.path.basename(a.src)} / TARGET {len(v0)}개, '
             f'{meta["target_words"]}단어 / USER SAMPLE {meta["sample_words"]}단어 -->', '']
    for u in units:
        tag = u['kind']
        if tag == 'TARGET':
            tag += ' - 고쳐 쓸 대상'
            if u['leadin']:
                tag += ', 수식 도입부: 다음 수식을 이끄는 끝맺음 유지'
        elif tag == 'USER SAMPLE':
            tag += ' - 문체 기준, 수정 금지'
        else:
            tag += ' - 고정'
        body = u['text'].strip()
        if u['kind'] == 'HEADING':
            body = '## ' + body
        lines += [f'[{u["idx"]}] ({tag})', body, '']
    with open(os.path.join(a.out_dir, 'v0_context.md'), 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))

    counts = {}
    for u in units:
        counts[u['kind']] = counts.get(u['kind'], 0) + 1
    print('wrote', a.out_dir, '| ' + ', '.join(f'{k} {v}' for k, v in counts.items()),
          f'| target words {meta["target_words"]} | lead-ins {meta["leadins"]}')
    if not meta['sample']:
        print('주의: USER SAMPLE 문단이 없다. 샘플을 문서 밖에서 받았다면 SAMPLE.md 로 따로 저장할 것.')


if __name__ == '__main__':
    main()
