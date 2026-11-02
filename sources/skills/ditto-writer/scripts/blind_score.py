#!/usr/bin/env python3
"""블라인드 리뷰 보고서들의 BLIND_JSON 을 읽어 '대상 부분' 점수와 멈춤 여부를 계산한다.

사용:
  python3 blind_score.py --targets vN.json  blind_rN_anthropic.md blind_rN_openai.md [--threshold 30]
  python3 blind_score.py --md vN.md --fixed 0,3  blind_rN_*.md                       # md/txt 대상

블라인드 리뷰어는 어느 문단이 고쳐 쓴 대상인지 모른다. 그래서 보고서의 문단(첫 단어들)과 high 인용을
대상 텍스트에 맞춰 본다:
  - 대상 부분 점수 = 대상 문단 점수의 단어 수 가중 평균 (못 맞춘 대상 문단은 경고)
  - 대상 최고점 = 대상 문단 점수의 최댓값
  - high_in_target = high 인용 중 대상 문단 안에 있는 것 (고정 부분 high 는 따로 보고만)
  - one_person = 보고서의 one_person 값
리뷰어별 PASS: 대상 부분 점수 <= threshold AND high_in_target == 0 AND one_person == true.
모든 리뷰어가 PASS 면 종료 코드 0, 아니면 1. 결과 한 줄 JSON 도 출력한다 (CHANGELOG 점수표용).
"""
import argparse, json, re, sys


def norm(s):
    # 인라인 수식은 렌더된 모양에 가깝게 (\hat{p} -> p, l_{j-1} -> l j 1)
    s = re.sub(r'\$([^$]*)\$', lambda m: ' ' + re.sub(r'\\[A-Za-z]+', ' ', m.group(1)) + ' ', s)
    s = s.replace('’', "'").replace('“', '"').replace('”', '"').replace('\\$', '$')
    return re.sub(r'[^0-9a-z가-힣]+', ' ', s.lower()).strip()


def words(s):
    return len(re.sub(r'\$[^$]*\$', 'X', s).split())


def load_targets(a):
    if a.targets:
        d = json.load(open(a.targets, encoding='utf-8'))
        return {k: v for k, v in d.items()}
    text = open(a.md, encoding='utf-8').read()
    blocks = [b.strip() for b in re.split(r'\n\s*\n', text) if b.strip()]
    fixed = {int(x) for x in a.fixed.split(',') if x.strip()} if a.fixed else set()
    return {str(i): b for i, b in enumerate(blocks)
            if i not in fixed and not b.startswith('$$') and not b.startswith('#')}


def parse_report(path):
    text = open(path, encoding='utf-8').read()
    m = re.findall(r'BLIND_JSON:\s*(\{.*\})', text)
    if not m:
        sys.exit(f'{path}: BLIND_JSON 줄이 없다 → 그 리뷰어에게 그 줄만 다시 요청')
    try:
        return json.loads(m[-1])
    except json.JSONDecodeError as e:
        sys.exit(f'{path}: BLIND_JSON 파싱 실패 ({e})')


def locate(snippet, targets):
    n = norm(snippet)
    if not n:
        return None
    for k, t in targets.items():
        nt = norm(t)
        if n in nt or nt.startswith(n[:40]) or (len(n) > 15 and n[:25] in nt):
            return k
    # 느슨한 맞춤: 앞 6토큰 중 80% 이상이 대상 앞 12토큰에 있으면
    head = n.split()[:6]
    best, best_k = 0, None
    for k, t in targets.items():
        pool = norm(t).split()[:12]
        hit = sum(w in pool for w in head) / len(head)
        if hit > best:
            best, best_k = hit, k
    return best_k if best >= 0.8 and len(head) >= 3 else None


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument('--targets', help='vN.json (대상 문단 텍스트)')
    g.add_argument('--md', help='vN.md (블록 단위)')
    ap.add_argument('--fixed', default='', help='--md 일 때 고정 블록 번호 (쉼표 구분)')
    ap.add_argument('--threshold', type=float, default=30)
    ap.add_argument('reports', nargs='+')
    a = ap.parse_args()

    targets = load_targets(a)
    results, all_pass = [], True
    for path in a.reports:
        r = parse_report(path)
        scores = {}
        for item in r.get('paragraphs', []):
            if not isinstance(item, (list, tuple)) or len(item) < 2:
                continue
            k = locate(str(item[0]), targets)
            if k is not None:
                scores.setdefault(k, float(item[1]))
        missing = [k for k in targets if k not in scores]
        tw = sum(words(targets[k]) for k in scores)
        target_score = round(sum(scores[k] * words(targets[k]) for k in scores) / tw, 1) if tw else None
        target_max = max(scores.values()) if scores else None
        highs = r.get('high_spans', [])
        high_in = [h for h in highs if locate(str(h), targets) is not None]
        high_out = [h for h in highs if locate(str(h), targets) is None]
        one = bool(r.get('one_person'))
        ok = target_score is not None and target_score <= a.threshold and not high_in and one
        all_pass &= ok
        res = {'report': path.rsplit('/', 1)[-1], 'overall': r.get('overall'), 'target': target_score,
               'target_max': target_max, 'high_in_target': len(high_in), 'high_elsewhere': len(high_out),
               'one_person': one, 'pass': ok, 'unmatched_targets': missing}
        results.append(res)
        print(f"{res['report']}: 전체 {res['overall']}% | 대상 {target_score}% (최고 {target_max}) | "
              f"대상 high {len(high_in)} (그 밖 {len(high_out)}) | 한 사람 {'예' if one else '아니오'} | "
              f"{'PASS' if ok else 'REVISE'}" + (f" | 못 맞춘 대상 {missing}" if missing else ''))
    print('SCORE_JSON:', json.dumps(results, ensure_ascii=False))
    print('멈춤: 예' if all_pass else '멈춤: 아니오')
    sys.exit(0 if all_pass else 1)


if __name__ == '__main__':
    main()
