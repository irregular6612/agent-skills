#!/usr/bin/env python3
"""docx 를 LibreOffice 로 PDF 렌더하고 쪽수를 원본과 비교한다.

사용:
  python3 render_check.py <out_dir> <원본.docx> <최종.docx> [<다른.docx> ...]

- 모든 docx 를 <out_dir> 에 같은 이름의 .pdf 로 만든다 (같은 렌더러끼리 비교).
- 첫 번째 docx(원본) 대비 쪽수가 다르면 종료 코드 1.
- Word 에서의 쪽 넘김을 보장하지는 않는다. 같은 렌더러 기준 비교일 뿐이다.
"""
import os, re, subprocess, sys

SOFFICE = '/Applications/LibreOffice.app/Contents/MacOS/soffice'


def pages(pdf):
    for mod in ('pypdf', 'PyPDF2'):
        try:
            return len(__import__(mod).PdfReader(pdf).pages)
        except ImportError:
            continue
    data = open(pdf, 'rb').read()  # 최후 수단: 페이지 객체 수
    return len(re.findall(rb'/Type\s*/Page(?!s)', data))


def main():
    if len(sys.argv) < 4:
        sys.exit(__doc__)
    out, docs = sys.argv[1], sys.argv[2:]
    os.makedirs(out, exist_ok=True)
    soffice = SOFFICE if os.path.exists(SOFFICE) else 'soffice'
    r = subprocess.run([soffice, '--headless', '--convert-to', 'pdf', '--outdir', out, *docs],
                       capture_output=True, text=True, timeout=600)
    if r.returncode:
        sys.exit(f'soffice 실패: {r.stderr.strip()[:500]}')
    counts = []
    for d in docs:
        pdf = os.path.join(out, os.path.splitext(os.path.basename(d))[0] + '.pdf')
        if not os.path.exists(pdf):
            sys.exit(f'PDF 가 안 생겼다: {pdf}')
        counts.append(pages(pdf))
        print(f'{pages(pdf):>3}쪽  {pdf}')
    bad = [d for d, c in zip(docs[1:], counts[1:]) if c != counts[0]]
    if bad:
        print(f'쪽수 다름 (원본 {counts[0]}쪽): {bad}')
        sys.exit(1)
    print(f'쪽수 같음: {counts[0]}쪽 (LibreOffice 기준)')


if __name__ == '__main__':
    main()
