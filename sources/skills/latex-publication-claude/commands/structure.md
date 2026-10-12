# /latex:structure — Monolithic TeX → 섹션 분리

단일 `.tex` 파일을 섹션별 폴더 구조로 분리한다. 컨텐츠는 한 글자도 변경하지 않고 구조만 변경.

## When to Use

- 단일 `.tex` 파일을 섹션별로 분리하고 싶을 때
- 여러 LaTeX 프로젝트를 하나의 repo에서 스위치 방식으로 관리할 때
- 기존 inline `\begin{thebibliography}`를 BibTeX `.bib`으로 전환할 때

## Usage

```
/latex:structure <tex_file> <output_dir> [project_name]
```

내부적으로 `scripts/structure_split.py` 호출.

## What It Does

단일 `.tex` 파일을 분석하여 아래 구조로 분리:

```
output_dir/
├── main.tex                       # 공통 preamble + 프로젝트 선택 스위치
├── <project_name>/
│   ├── content.tex                # \input 오케스트레이터
│   ├── refs.bib                   # BibTeX 참고문헌
│   ├── figures/                   # 이미지 저장 폴더
│   │   └── .gitkeep
│   └── sections/
│       ├── 00_frontmatter.tex     # \title, \author, \maketitle, \abstract
│       ├── 01_<section_name>.tex  # 각 \section별 파일
│       ├── ...
│       └── NN_bibliography.tex    # \bibliography{project/refs}
└── .gitignore
```

## Workflow

```
Phase 1: 분석
├── .tex 파일 읽기
├── preamble 추출 (documentclass ~ \begin{document})
├── \section 경계 식별
├── bibliography 방식 확인 (inline vs bibtex)
└── 패키지 목록 수집

Phase 2: 분리
├── main.tex 생성 (preamble + \professor 스위치)
├── content.tex 생성 (\input 목록)
├── 섹션별 .tex 파일 생성
├── refs.bib 생성 (inline bib → BibTeX 변환)
└── figures/ 디렉토리 생성

Phase 3: 검증
├── 컴파일 (에러 0 확인) — `../scripts/compile.sh` (xelatex + TeX Live 2025 고정)
├── bibtex 실행 + 재컴파일 (`../scripts/compile.sh` — latexmk가 수렴까지 반복)
├── 원본 대비 페이지 수 일치 확인
├── citation 경고 0건 확인
└── 컨텐츠 유실 없음 확인 (diff)

Phase 4: Critique Loop
├── Round 1: 에러/경고 확인 → 수정
├── Round 2: 재검증 → 이슈 없으면 통과
└── 2회 연속 이슈 없을 때까지 반복
```

## Rules

### Preamble Handling
- `\documentclass` ~ `\begin{document}` 사이의 모든 내용을 `main.tex`로 추출
- 여러 프로젝트가 있을 경우 패키지의 **합집합**을 사용
- `\graphicspath{{\professor/figures/}}`로 프로젝트별 이미지 경로 설정

### Section Splitting
- `\section{...}` 단위로 분리 (subsection은 해당 section 파일에 포함)
- 파일명: `NN_<section_name>.tex` (번호 + 스네이크케이스)
- `\title`, `\author`, `\date`, `\maketitle`, `\begin{abstract}`~`\end{abstract}` → `00_frontmatter.tex`
- `\section*{Acknowledgments}` + bibliography → 마지막 번호 `_bibliography.tex`

#### Section Name Mapping 예시

| 원본 `\section` | 출력 파일명 |
|----------------|------------|
| `\section{Background \& Motivation}` | `01_background.tex` |
| `\section{Research Questions}` | `02_research_questions.tex` |
| `\section{Proposed Method}` | `03_proposed_method.tex` |
| `\section{Experimental Setup}` | `04_experimental_setup.tex` |
| `\section{Expected Results \& Analysis}` | `05_expected_results.tex` |
| `\section*{Acknowledgments}` | (merged into `NN_bibliography.tex`) |

규칙:
- 특수문자(`&`, `:`, etc.) 제거
- 공백 → 언더스코어
- 소문자로
- Zero-padded 번호 prefix
- `\section*` (unnumbered) 섹션은 가장 가까운 번호 섹션 파일에 merge

#### Frontmatter Extraction 정확한 범위

`\begin{document}`과 첫 `\section` 사이의 모든 내용:

```latex
% 00_frontmatter.tex
\title{...}
\author{...}
\date{...}

\maketitle

\begin{abstract}
...
\end{abstract}
```

#### content.tex 작성 규칙

```latex
\input{PROJECT_NAME/sections/00_frontmatter}
\input{PROJECT_NAME/sections/01_SECTION_NAME}
...
\input{PROJECT_NAME/sections/NN_bibliography}
```

**중요**: `\input` 경로에는 hardcoded 프로젝트 이름 사용 (`\professor` 변수 X). `\input`은 main.tex의 `\professor`로 동작하지만, content.tex 내부 경로는 명시적이어야 Overleaf 호환성/명확성 유지.

### Bibliography (CRITICAL)
- **반드시 BibTeX `.bib` 파일로 관리** — inline `\begin{thebibliography}` 금지
- `refs.bib`를 프로젝트 폴더 루트에 생성
- `\bibliographystyle{plainnat}` + `\bibliography{<project>/refs}` 사용
- inline `\bibitem`이 있으면 자동으로 `@article`/`@inproceedings` 엔트리로 변환
- **모든 텍스트 참조를 `\citep{}` 또는 `\citet{}`로 변환** — "(Author et al., Year)" 같은 plain text 참조를 찾아 `\citep{key}`로 교체
- 컴파일: `../scripts/compile.sh` — Overleaf와 동일한 latexmk 호출. 엔진 고정, 패스 횟수는 latexmk가 판정

상세는 `../references/bibtex-rules.md`.

### Multi-Project Switch
```latex
% main.tex
\newcommand{\professor}{goodman}  % Change to: goodman | andreas | lake

% ... shared preamble ...

\begin{document}
\input{\professor/content}
\end{document}
```

상세는 `../references/multi-project-layout.md`.

### Content Preservation
- 원본 내용을 **한 글자도 변경하지 않음** (구조 변경만)
- 단, LaTeX 에러가 있는 경우 수정 (예: pgfplots xticklabel `\\` 문제)

---

## Common Issues & Fixes

| 문제 | 원인 | 해결 |
|------|------|------|
| pgfplots xticklabel `\\` 에러 | LR mode에서 `\\` 사용 불가 | `{Label Text}` 형태로 변경, `align=center` 추가 |
| Overfull hbox (table) | `lcccc` 열이 너무 넓음 | `Xcccc` (tabularx) 또는 헤더 축약 |
| Citation undefined | `\cite` 없이 텍스트로 참조 | `\citep{key}` 또는 `\citet{key}`로 변환 |
| BibTeX 엔트리 누락 | `.bib`에 key 없음 | `refs.bib`에 엔트리 추가 |
| `\legend`에서 `$\to$` 에러 | pgfplots legend의 math mode 제한 | `\textrightarrow{}` 사용 |

더 많은 이슈: `../references/common-issues.md`.

## Related Subcommands

- `/latex:build` — MD→LaTeX 변환, Korean font, Format review
- `/latex:push` — 분리 후 GitHub/Overleaf로 push
- `iterative-academic-writer` — 학술 문서 품질 개선 루프 (별개 스킬)
