# /latex:build — MD → 독립 PDF 빌드

Obsidian/일반 학술 서베이 Markdown을 publication-ready LaTeX PDF로 변환. 5-Phase 파이프라인, 각 Phase 사이에 decision gate.

## When to Use

- 사용자가 `.md` 서베이/논문을 PDF로 변환하고 싶을 때
- 기존 LaTeX 컴파일 PDF의 포맷 이슈를 수정하고 싶을 때
- 한글 폰트 지원이 필요한 LaTeX 빌드 (XeLaTeX + kotex 또는 Noto Sans CJK KR)
- Mermaid 다이어그램을 TikZ figure로 교체하고 싶을 때
- `build_template.py`로 서베이 컴파일을 원할 때
- LaTeX 프로젝트를 섹션별 폴더로 재구조화하고 싶을 때

## When NOT to Use

- 기존 LaTeX 템플릿의 sentinel 마커 영역에 MD를 주입 → `/latex:inject`
- LaTeX 환경 셋업 자체 → `/latex:setup`
- Beamer 슬라이드 → `academic-slides-iterative` (별개 스킬)

## Phase Overview

```
Phase 1: Content Quality    → iterative-academic-writer 스킬 호출, Critical=0 to pass
Phase 2: LaTeX Build        → MD→TEX→PDF 파이프라인 (`scripts/md2tex/modes/build.py`)
Phase 3: Format Review      → Page-by-page 시각 검수, overflow 수정
Phase 4: Figure Validation  → TikZ 렌더링, 캡션, 사이즈
Phase 5: Git Management     → `/latex:push`로 위임
```

---

## Phase 1: Content Writing Loop

`iterative-academic-writer` 스킬을 source `.md` 파일에 invoke. 14개 학술 글쓰기 원칙, FactBase 검증, hallucination 탐지 적용.

**Gate**: Critical issues = 0 → Phase 2 진행.

이 Phase는 비싼 LaTeX 처리 전에 컨텐츠 품질을 확보. 스킵하지 말 것 — PDF 생성 후 컨텐츠 에러 수정은 시간 낭비.

---

## Phase 2: LaTeX Build Pipeline

### 2.1 Project Structure

섹션별 폴더 organization (유지보수성 ↑):

```
ProjectName/
├── main.tex                   # 공통 preamble + 프로젝트 선택 스위치
├── <project>/
│   ├── content.tex            # 모든 섹션의 \input 오케스트레이터
│   ├── refs.bib               # BibTeX 참고문헌 (NOT inline thebibliography)
│   ├── figures/               # 이미지 + 생성된 figure
│   │   └── .gitkeep
│   └── sections/
│       ├── 00_frontmatter.tex # \title, \author, \maketitle, \abstract
│       ├── 01_background.tex  # 각 \section은 자체 파일
│       ├── ...
│       └── NN_bibliography.tex # \bibliographystyle + \bibliography
├── .gitignore
└── build_and_compile.sh       # Optional: 컴파일 shell wrapper
```

MD→TEX 프로젝트(Obsidian 소스)는 추가로:
```
├── SourceDocument.md          # Obsidian 소스 (git 제외)
└── build_latex.py             # Python 빌드 스크립트 (MD → TEX → PDF) — 신 경로: scripts/md2tex/modes/build.py
```

**Multi-project layout**: `\newcommand{\professor}{project_name}` in `main.tex`로 공유 preamble 사용. 상세는 `../references/multi-project-layout.md` 또는 `/latex:structure`.

### 2.2 Bibliography Management (CRITICAL)

상세는 `../references/bibtex-rules.md`. 핵심:

- BibTeX `.bib` 파일만 사용. inline `\begin{thebibliography}` 금지
- `refs.bib`를 프로젝트 폴더 루트에 생성
- `\bibliographystyle{plainnat}` + `\bibliography{<project>/refs}` 사용
- 모든 참조는 `\citep{}` 또는 `\citet{}` — plain text "(Author, Year)" 금지
- 컴파일: `../scripts/compile.sh` (Overleaf와 동일한 latexmk 호출. 패스 횟수·bibtex은 latexmk가 판정)

### 2.3 Build Script (`scripts/md2tex/modes/build.py`)

`build.py`는 `build_legacy.py`(구 academic-latex-pipeline `build_template.py`)의 wrapper.
Entry point는 `scripts/md2tex/convert.py --mode=build`를 통해서도 호출 가능.

MD→TEX 전체 변환 흐름:

1. **Pre-process MD** (별도 수동): `pandoc input.md -f markdown -t latex -o raw.tex` 먼저 실행
2. **build.py 실행**: `raw.tex` → `final.tex` 변환 (wikilinks strip, frontmatter 제거, citation 매칭 등)
build.py의 처리 단계 (legacy 코드, 변경 금지):

3. **Preamble 주입** (한글 폰트 지원):

   **기본 (`kotex`)** — Overleaf 호환 권장:
   ```latex
   \usepackage{kotex}
   ```

   **`ucharclasses` (legacy academic-latex-pipeline 방식 — preamble에 직접 작성)**:
   ```latex
   \usepackage{fontspec}
   \usepackage{ucharclasses}
   \setmainfont{Noto Sans CJK KR}
   \newfontfamily\hangulfont{Noto Sans CJK KR}
   \setTransitionsForCJK{\hangulfont}{}{}
   ```
   Why `ucharclasses` instead of `xeCJK`? The `xeCJK` package requires `ctexhook.sty` which is missing from many LaTeX distributions. `ucharclasses` is more portable in some environments.

4. **Mermaid 블록을 TikZ figure로 교체**
5. **Examples를 `tcolorbox` environment로 래핑**
6. **Citation 주입**: `PaperName (Year)` → `\cite{key_year}` 매칭
7. **Table 수정**: `p{Xcm}` 열을 `l`/`c`/`r` 대신 사용해 overflow 방지

### 2.4 Font Installation
```bash
mkdir -p ~/.local/share/fonts
# Noto Sans CJK KR 다운로드: github.com/googlei18n/noto-cjk/releases
fc-cache -fv ~/.local/share/fonts/
```

### 2.5 Compilation (Overleaf parity)
```bash
bash ~/.claude/skills/latex-publication/scripts/compile.sh main.tex
```

내부 동작 — Overleaf CLSI가 실행하는 명령 그대로:
```bash
latexmk -cd -jobname=output -auxdir=. -outdir=. \
        -synctex=1 -interaction=batchmode -time -xelatex main.tex
```
산출물은 `output.pdf` (Overleaf와 같은 이름). 패스 횟수는 latexmk가
수렴할 때까지 반복하고, bibtex 실행 여부도 latexmk가 판정한다.
상세·잔차는 `../references/overleaf-parity.md`.

### 2.6 Overfull Hbox Prevention (Preamble)
```latex
\tolerance=1000
\emergencystretch=3em
\hfuzz=2pt
```

**Gate**: 컴파일이 에러 없이 성공 → Phase 3 진행.

---

## Phase 3: Format Review Loop

PDF를 page by page 검수. 확인 항목:

**Critical** (반드시 수정, loop back):
- Table이 margin을 넘어 overflow
- Figure 누락 또는 빈 칸
- 읽을 수 없거나 잘린 text
- `[[wikilink]]` 잔존
- Undefined citations

**Minor** (deferable):
- Spacing 조정, 캡션 대소문자, 색상 preference

각 critical 이슈:
- Table overflow → 열 폭 조정, `tabularx` + `X` 열 사용
- Figure 누락 → TikZ standalone 모드 테스트, 단순화
- Wikilinks → 빌드 스크립트의 pre-processing regex 수정
- Undefined citations → `refs.bib`에 엔트리 추가

수정 후 재컴파일. **Gate**: Critical 이슈 0 → Phase 4.

---

## Phase 4: Figure/Image Review

각 TikZ figure:
1. 올바르게 렌더링되는가?
2. 캡션이 있고 descriptive한가?
3. 사이징이 적절한가 (`\resizebox{\textwidth}{!}{...}`)?
4. 배치가 올바른가 (`[H]` float specifier)?

문제 있는 TikZ는 isolation 테스트:
```latex
\documentclass[tikz]{standalone}
\usepackage{tikz}
\begin{document}
% TikZ code here
\end{document}
```

**Gate**: 모든 figure 정상 → Phase 5.

---

## Phase 5: Git Management

`/latex:push`로 위임 (구조화된 git 작업).

### Files to include in repo:
- `main.tex`, `<project>/content.tex`, `<project>/sections/*.tex`
- `<project>/refs.bib`
- `<project>/figures/*`
- `.gitignore`
- `build_latex.py`, `build_and_compile.sh` (해당 시)

### Files to exclude:
- 원본 `.md` Obsidian 소스 (Obsidian vault에만)
- `.obsidian/` 디렉토리
- LaTeX 빌드 artifact (`.aux`, `.log`, `.out`, `.toc`, `.bbl`, `.blg`)
- PDF 파일 (on-demand 컴파일)

`.gitignore` template: `../templates/gitignore` 또는 `../references/common-issues.md` 참조.

### Git authentication:
- GitHub: `$GITHUB_TOKEN` env var or user-provided token
- Overleaf: `$OVERLEAF_TOKEN` env var (Premium plan 필요)

---

## Common Issues & Fixes

| Issue | Fix |
|-------|-----|
| Korean text 누락 | Noto Sans CJK KR 설치 확인, `fc-list \| grep Noto` |
| Overfull hbox | `\tolerance`, `\emergencystretch` 증가, 긴 줄 reword |
| Table overflow | `p{2cm}` 또는 `X` 열 사용, 내용 축소 |
| tcolorbox 깨짐 | `\tcbuselibrary{most}` 로드 확인 |
| Undefined citations | 누락 키를 `refs.bib`에 추가, bibtex 재실행 |
| Mermaid 미교체 | 빌드 스크립트의 regex 패턴 확인 |
| pgfplots `\\` in labels | `{Label Text}` + `align=center` 사용 |
| `$\to$` in `\legend` | `\textrightarrow{}` 사용 |
| Inline thebibliography | `refs.bib` + `\bibliography{}`로 전환 |

더 많은 이슈: `../references/common-issues.md`.

## English Version Generation

Bilingual 프로젝트는 별도 English build:
- MD 컨텐츠 번역 (구조 동일)
- English-specific preamble (CJK 폰트 불필요, 표준 `\usepackage[T1]{fontenc}` 사용)
- `survey_main_EN.tex` → `survey_main_EN.pdf` 생성
- 양 버전이 `refs.bib` 공유

## Related Subcommands

- `/latex:setup` — Phase 2의 한글 폰트 환경 셋업 (선행)
- `/latex:structure` — Phase 5의 프로젝트 구조화
- `/latex:push` — Phase 5의 git push
- `iterative-academic-writer` — Phase 1 컨텐츠 평가 (별개 스킬)
