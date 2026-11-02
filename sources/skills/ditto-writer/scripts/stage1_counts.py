#!/usr/bin/env python3
"""Stage 1a — 샘플(또는 생성 글)의 결정적 계량. LLM 에게 세게 하지 않는다.

사용:
  python3 stage1_counts.py <text.md|txt> [--json out.json]
  python3 stage1_counts.py <생성글.txt> --ref <profile_counts.json>   # 생성 글을 프로필 계량과 나란히 비교

언어 자동 판별: 한글 비율 > 30% 면 ko (단어 = 어절), 아니면 en.
$...$ 인라인 수식은 단어 1개로 친다. 원 연구 스크립트(research §3.1)를 확장:
  - 마침표 뒤 띄어쓰기 누락("example.There")도 문장 경계로 보고 따로 센다
  - 직선/둥근 따옴표·아포스트로피 구분, 문두 연결어, 1인칭, 의문문, 괄호
  - LLM 기본값 신호(never-list 후보) 적중 수: em-dash, not only/but also, In conclusion, 문장 끝 -ing 해설구 등
"""
import argparse, collections as C, json, re, statistics as st, sys

FW_EN = ("the a an of to in on at for with by from about as and but or so because that which who this these "
         "it its i we you they my our not can could may might should would will just also very really "
         "therefore however then thus instead").split()
CONNECTORS_EN = {'so', 'but', 'and', 'also', 'however', 'therefore', 'then', 'thus', 'instead', 'because',
                 'moreover', 'furthermore', 'firstly', 'secondly', 'finally', 'in', 'for', 'traditionally', 'another'}
AI_LEX_EN = ['delve', 'tapestry', 'testament', 'intricate', 'underscore', 'pivotal', 'crucial', 'vibrant',
             'foster', 'showcase', 'enhance', 'align with', 'landscape', 'leverage', 'utilize', 'facilitate',
             'robust', 'nuanced', 'notably', 'furthermore', 'moreover', 'additionally', 'in conclusion',
             'overall,', 'plays a crucial role', 'it is important to note', 'serves as', 'stands as']
AI_LEX_KO = ['시사하', '에 있어서', '를 통해', '을 통해', '다양한', '핵심적', '중요한 역할', '결론적으로', '살펴보',
             '측면에서', '것으로 보인다', '할 수 있을 것이다']


def split_sents(t):
    t = re.sub(r'\s+', ' ', t.strip())
    parts = re.split(r'(?<=[.!?])\s+|(?<=[a-z][.!?])(?=[A-Z])|(?<=[.!?][”"’)])\s+', t)
    return [s.strip() for s in parts if s.strip()]


def toks(s, lang):
    s = re.sub(r'\$[^$]*\$', ' MATH ', s)
    if lang == 'ko':
        return s.split()
    return re.findall(r"[A-Za-z][A-Za-z'’\-]*|\d+", s)


def count(text):
    lang = 'ko' if len(re.findall('[가-힣]', text)) > 0.3 * max(1, len(re.findall(r'\S', text))) else 'en'
    paras = [p.strip() for p in re.split(r'\n\s*\n', text) if p.strip()]
    sents = split_sents(text)
    words = toks(text, lang)
    n = max(1, len(words))
    L = [len(toks(s, lang)) for s in sents] or [0]
    per100 = lambda k: round(100 * k / n, 2)
    low = [w.lower() for w in words]
    out = {
        'lang': lang, 'n_words': len(words), 'n_sents': len(sents), 'n_paras': len(paras),
        'sent_len': {'list': L, 'mean': round(st.mean(L), 1), 'sd': round(st.pstdev(L), 1),
                     'cv': round(st.pstdev(L) / st.mean(L), 2) if st.mean(L) else 0,
                     'min': min(L), 'max': max(L), 'short<=5': sum(l <= 5 for l in L),
                     'long>=30': sum(l >= 30 for l in L)},
        'sents_per_para': [len(split_sents(p)) for p in paras],
        'punct_per100w': {k: per100(text.count(k)) for k in
                          [',', ';', ':', '(', '—', '–', ' - ', '...', '…', '!', '?', '"', '“', "'", '’']},
        'questions': sum(s.endswith('?') for s in sents),
        'missing_space_after_period': len(re.findall(r'[a-z][.!?][A-Z]', text)),
        'no_space_before_paren': len(re.findall(r'\w\(', text)),
        'sent_initial': C.Counter(re.sub(r'[^\w가-힣’\']', '', s.split()[0]).lower() for s in sents if s.split()).most_common(12),
        'repeated_3grams': [' '.join(g) for g, c in C.Counter(zip(low, low[1:], low[2:])).items() if c >= 2],
    }
    if lang == 'en':
        fw = C.Counter(w for w in low if w in FW_EN)
        out['function_words_per1000'] = {w: round(1000 * c / n, 1) for w, c in fw.most_common(30)}
        # 's 는 소유격과 구분이 안 되므로 it's/that's/there's/what's/let's 만 축약으로 센다
        out['contractions_per100w'] = per100(len(re.findall(
            r"\b(\w+n['’]t|\w+['’](re|ve|ll|d|m)|(it|that|there|what|let|he|she)['’]s)\b", text, re.I)))
        out['first_person'] = {k: low.count(k) for k in ('i', 'my', 'me', 'we', 'our', 'us', 'you')}
        out['sent_initial_connectors'] = {k: v for k, v in C.Counter(
            re.sub(r'[^\w]', '', s.split()[0]).lower() for s in sents if s.split()).items() if k in CONNECTORS_EN}
        lowt = text.lower()
        hits = {w: lowt.count(w) for w in AI_LEX_EN if lowt.count(w)}
        hits['not only/but also'] = len(re.findall(r'not only\b.*?\bbut also', lowt))
        hits['not X, but Y'] = len(re.findall(r'\bnot\b[^.]{1,40}, but\b', lowt))
        hits[', -ing tail'] = len(re.findall(r', (highlighting|underscoring|emphasizing|showing|reflecting|making|ensuring|revealing)\b', lowt))
        hits['em-dash'] = text.count('—')
        hits['bullets/headings'] = len(re.findall(r'^\s*([-*•]|#{1,6})\s', text, re.M))
        out['ai_signal_hits'] = {k: v for k, v in hits.items() if v}
    else:
        out['comma_sentence_ratio'] = round(sum(',' in s for s in sents) / max(1, len(sents)), 2)
        out['endings'] = dict(C.Counter(re.findall(r'(다|요|음|함|죠|까)[.!?]', text)))
        lowt = text
        hits = {w: lowt.count(w) for w in AI_LEX_KO if lowt.count(w)}
        hits['em-dash'] = text.count('—')
        hits['bullets/headings'] = len(re.findall(r'^\s*([-*•]|#{1,6})\s', text, re.M))
        out['ai_signal_hits'] = {k: v for k, v in hits.items() if v}
    return out


def compare(cur, ref):
    rows = [('단어 수', ref['n_words'], cur['n_words']),
            ('문장 길이 평균', ref['sent_len']['mean'], cur['sent_len']['mean']),
            ('문장 길이 CV', ref['sent_len']['cv'], cur['sent_len']['cv']),
            ('짧은 문장(≤5) 비율', round(ref['sent_len']['short<=5'] / max(1, ref['n_sents']), 2),
             round(cur['sent_len']['short<=5'] / max(1, cur['n_sents']), 2)),
            ('쉼표/100w', ref['punct_per100w'][','], cur['punct_per100w'][',']),
            ('em-dash/100w', ref['punct_per100w']['—'], cur['punct_per100w']['—']),
            ('세미콜론/100w', ref['punct_per100w'][';'], cur['punct_per100w'][';']),
            ('콜론/100w', ref['punct_per100w'][':'], cur['punct_per100w'][':']),
            ('의문문 비율', round(ref['questions'] / max(1, ref['n_sents']), 2), round(cur['questions'] / max(1, cur['n_sents']), 2))]
    if cur['lang'] == 'en' and ref.get('lang') == 'en':
        rows.append(('축약/100w', ref['contractions_per100w'], cur['contractions_per100w']))
    print(f'{"지표":<18}{"프로필":>10}{"현재":>10}')
    for name, r, c in rows:
        print(f'{name:<18}{r:>10}{c:>10}')
    print('AI 신호 적중 (현재):', cur['ai_signal_hits'] or '없음')


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('path')
    ap.add_argument('--json', default=None, help='결과 JSON 저장 경로')
    ap.add_argument('--ref', default=None, help='비교 기준 계량 JSON (프로필의 counts.json)')
    a = ap.parse_args()
    out = count(open(a.path, encoding='utf-8').read())
    if a.json:
        json.dump(out, open(a.json, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    if a.ref:
        compare(out, json.load(open(a.ref, encoding='utf-8')))
    elif a.json:
        sl = out['sent_len']
        print(f"wrote {a.json} | {out['lang']} {out['n_words']}단어 {out['n_sents']}문장 | 문장 길이 평균 {sl['mean']} CV {sl['cv']}"
              f" | AI 신호 {out['ai_signal_hits'] or '없음'}")
    else:
        print(json.dumps(out, ensure_ascii=False, indent=1))


if __name__ == '__main__':
    main()
