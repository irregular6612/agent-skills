#!/usr/bin/env python3
"""vN.json 의 문단 텍스트를 원본 docx 의 복제본에 넣어 새 docx 를 만든다. 원본은 읽기만 한다.

사용:
  python3 apply_docx.py <src.docx> <vN.json> <out.docx> [--v0 v0.json]

- vN.json: {"문단 인덱스": "새 텍스트", ...}  (인덱스는 extract_docx.py 와 같은 document.paragraphs 순서)
- --v0 를 안 주면 vN.json 옆의 v0.json 을 자동으로 찾는다. v0 에 없는 키(=고정 문단)를
  건드리려 하면 멈춘다.
- 대상 문단은 문단 서식(pPr)과 첫 글자 서식(rPr)만 남기고 내용을 새로 채운다.
- 본문 안의 $...$ 는 Word 인라인 수식(OMML)으로 바꾼다. 리터럴 달러는 \\$ 로 쓴다.
  지원 문법: x_j, x_{ab}, x^{2}, x_{i}^{2}, {ab}_{c}, \\hat{p}, \\bar{x}, \\tilde{x}, \\dot{x},
  \\frac{a}{b}, \\text{..}, 그리스 문자(\\Delta, \\alpha, ...), \\ge \\le \\ne \\approx \\times \\cdot
  \\to \\in \\infty \\sum \\pm. 모르는 명령은 이름을 글자로 남긴다.
  예: "$\\hat{p}(r,m,t,l)$", "$l_{j}$", "$l_{j-1}$", "$\\Delta S$", "$A = 1$"
- 저장 뒤 검증: 대상 외 문단의 XML 이 원본과 같은지, 인라인 수식 개수, 남은 '$' 를 출력한다.
"""
import argparse, copy, json, os, re, sys
import docx
from docx.oxml.ns import qn
from lxml import etree

M = 'http://schemas.openxmlformats.org/officeDocument/2006/math'
XML_SPACE = '{http://www.w3.org/XML/1998/namespace}space'

SYM = {
    'Delta': 'Δ', 'delta': 'δ', 'alpha': 'α', 'beta': 'β', 'gamma': 'γ', 'Gamma': 'Γ',
    'epsilon': 'ε', 'varepsilon': 'ε', 'theta': 'θ', 'lambda': 'λ', 'mu': 'μ', 'pi': 'π',
    'sigma': 'σ', 'Sigma': 'Σ', 'tau': 'τ', 'phi': 'φ', 'varphi': 'φ', 'psi': 'ψ',
    'omega': 'ω', 'Omega': 'Ω', 'rho': 'ρ', 'eta': 'η', 'kappa': 'κ', 'nabla': '∇',
    'ge': '≥', 'geq': '≥', 'le': '≤', 'leq': '≤', 'ne': '≠', 'neq': '≠', 'approx': '≈',
    'times': '×', 'cdot': '·', 'to': '→', 'rightarrow': '→', 'in': '∈', 'infty': '∞',
    'sum': '∑', 'prod': '∏', 'pm': '±', 'equiv': '≡', 'sim': '∼', 'propto': '∝',
    'mid': '|', 'ldots': '…', 'dots': '…', 'partial': '∂', 'sqrt': '√',
}
ACCENT = {'hat': '̂', 'widehat': '̂', 'bar': '̅', 'overline': '̅',
          'tilde': '̃', 'dot': '̇'}


def m(tag, *kids, **attrs):
    el = etree.Element(f'{{{M}}}{tag}')
    for k, v in attrs.items():
        el.set(f'{{{M}}}{k}', v)
    for k in kids:
        el.append(k)
    return el


def mrun(text):
    t = m('t')
    t.text = text
    t.set(XML_SPACE, 'preserve')
    return m('r', t)


def group(s, i):
    """s[i] 에서 한 덩어리: {..} (중첩 허용), \\명령, 또는 한 글자. (본문, 다음 위치)"""
    while i < len(s) and s[i] == ' ':
        i += 1
    if i >= len(s):
        return '', i
    if s[i] == '{':
        depth, j = 0, i
        while j < len(s):
            if s[j] == '{': depth += 1
            elif s[j] == '}':
                depth -= 1
                if depth == 0:
                    return s[i + 1:j], j + 1
            j += 1
        return s[i + 1:], len(s)
    if s[i] == '\\':
        j = i + 1
        while j < len(s) and s[j].isalpha():
            j += 1
        return s[i:max(j, i + 2)], max(j, i + 2)
    return s[i], i + 1


def parse(s):
    """수식 문자열 -> OMML 요소 리스트."""
    atoms = []  # ('txt', str) | ('els', [element, ...])
    i = 0
    while i < len(s):
        c = s[i]
        if c == '\\':
            j = i + 1
            while j < len(s) and s[j].isalpha():
                j += 1
            name = s[i + 1:j]
            if not name:  # \, \{ \} \$ 같은 한 글자 이스케이프
                ch = s[j] if j < len(s) else ''
                atoms.append(('txt', ' ' if ch in ',;: ' else ch))
                i = j + 1
                continue
            i = j
            if name in ACCENT:
                body, i = group(s, i)
                atoms.append(('els', [m('acc', m('accPr', m('chr', val=ACCENT[name])), m('e', *parse(body)))]))
            elif name == 'frac':
                a, i = group(s, i)
                b, i = group(s, i)
                atoms.append(('els', [m('f', m('num', *parse(a)), m('den', *parse(b)))]))
            elif name in ('text', 'mathrm', 'mathit', 'operatorname', 'mathbf'):
                body, i = group(s, i)
                atoms.append(('txt', body))
            elif name in ('left', 'right', 'big', 'Big'):
                continue
            elif name in SYM:
                atoms.append(('txt', SYM[name]))
            else:
                atoms.append(('txt', name))
        elif c in '_^':
            body, i = group(s, i + 1)
            base = atoms.pop() if atoms else ('txt', '')
            base_els = merge([base])
            sub = sup = None
            if c == '_': sub = body
            else: sup = body
            if i < len(s) and s[i] in '_^' and s[i] != c:
                body2, i = group(s, i + 1)
                if c == '_': sup = body2
                else: sub = body2
            if sub is not None and sup is not None:
                el = m('sSubSup', m('e', *base_els), m('sub', *parse(sub)), m('sup', *parse(sup)))
            elif sub is not None:
                el = m('sSub', m('e', *base_els), m('sub', *parse(sub)))
            else:
                el = m('sSup', m('e', *base_els), m('sup', *parse(sup)))
            atoms.append(('els', [el]))
        elif c == '{':
            body, i = group(s, i)
            atoms.append(('els', parse(body)))
        else:
            atoms.append(('txt', c))
            i += 1
    return merge(atoms)


def merge(atoms):
    out, buf = [], ''
    for kind, v in atoms:
        if kind == 'txt':
            buf += v
        else:
            if buf:
                out.append(mrun(buf)); buf = ''
            out.extend(v)
    if buf:
        out.append(mrun(buf))
    return out


SPLIT = re.compile(r'(?<!\\)\$(.+?)(?<!\\)\$')
KEEP = {'pPr'}
QUIET_DROP = {'r', 'oMath', 'proofErr', 'bookmarkStart', 'bookmarkEnd', 'lastRenderedPageBreak'}


def fill(p, text):
    """문단 p 의 내용을 text 로 갈아 끼운다. 지워진 비일상 요소 이름을 돌려준다."""
    proto_rpr = None
    for r in p._p.findall(qn('w:r')):
        if r.find(qn('w:t')) is not None:
            proto_rpr = r.find(qn('w:rPr'))
            break
    dropped = []
    for el in list(p._p):
        name = el.tag.split('}', 1)[-1]
        if name in KEEP:
            continue
        if name not in QUIET_DROP:
            dropped.append(name)
        p._p.remove(el)
    if '\n' in text:
        text = re.sub(r'\s*\n\s*', ' ', text)
    for idx, part in enumerate(SPLIT.split(text.strip())):
        if not part:
            continue
        if idx % 2:
            p._p.append(m('oMath', *parse(part)))
        else:
            r = etree.SubElement(p._p, qn('w:r'))
            if proto_rpr is not None:
                r.append(copy.deepcopy(proto_rpr))
            t = etree.SubElement(r, qn('w:t'))
            t.text = part.replace('\\$', '$')
            t.set(XML_SPACE, 'preserve')
    return dropped


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('src')
    ap.add_argument('version_json')
    ap.add_argument('out')
    ap.add_argument('--v0', default=None, help='허용 키 목록으로 쓸 v0.json (기본: vN.json 옆)')
    a = ap.parse_args()

    if os.path.abspath(a.src) == os.path.abspath(a.out):
        sys.exit('출력 경로가 원본과 같다. 원본은 덮어쓰지 않는다.')
    data = json.load(open(a.version_json, encoding='utf-8'))
    v0_path = a.v0 or os.path.join(os.path.dirname(os.path.abspath(a.version_json)), 'v0.json')
    if os.path.abspath(v0_path) == os.path.abspath(a.version_json):
        print('참고: v0.json 자체를 적용한다 (키 검사 불필요).')
    elif os.path.exists(v0_path):
        allowed = set(json.load(open(v0_path, encoding='utf-8')))
        extra = set(data) - allowed
        if extra:
            sys.exit(f'v0.json 에 없는 키(고정 문단) 수정 시도: {sorted(extra, key=int)}')
        missing = allowed - set(data)
        if missing:
            print(f'참고: 빠진 키 {sorted(missing, key=int)} 는 원문 그대로 둔다.')
    else:
        print('경고: v0.json 을 못 찾아 키 검사를 건너뛴다.')

    d = docx.Document(a.src)
    P = d.paragraphs
    for k, text in data.items():
        i = int(k)
        if i >= len(P):
            sys.exit(f'인덱스 {i} 가 문단 수 {len(P)} 를 넘는다')
        if len(re.findall(r'(?<!\\)\$', text)) % 2:
            sys.exit(f'[{k}] $ 짝이 안 맞는다: {text[:80]}...')
        dropped = fill(P[i], text)
        if dropped:
            print(f'경고: [{k}] 에서 서식 외 요소가 지워졌다: {sorted(set(dropped))} (각주·링크·변경추적이면 수동 확인)')
    d.save(a.out)

    # 검증
    src, out = docx.Document(a.src).paragraphs, docx.Document(a.out).paragraphs
    keys = {int(k) for k in data}
    same = sum(etree.tostring(src[i]._p) == etree.tostring(out[i]._p)
               for i in range(len(src)) if i not in keys)
    n_other = len(src) - len(keys & set(range(len(src))))
    n_inline = sum(len(out[i]._p.findall(f'.//{{{M}}}oMath')) for i in keys)
    left = [k for k in data if out[int(k)].text.count('$') != data[k].count('\\$')]
    print(f'saved {a.out} | 문단 수 {len(src)}->{len(out)} | 대상 외 문단 XML 동일 {same}/{n_other}'
          f' | 대상 문단 인라인 수식 {n_inline}개 | 남은 $ 표기 문단 {left or "없음"}')
    if len(src) != len(out) or same != n_other:
        sys.exit('검증 실패: 대상 외 문단이 바뀌었다.')


if __name__ == '__main__':
    main()
