# Multi-Project Layout — `\professor` 스위치 패턴

여러 LaTeX 프로젝트를 하나의 repo에서 공통 preamble로 관리하는 패턴. 구 `latex-project-manager`의 핵심 가치 보존.

## 사용 시점

- 여러 교수님의 연구 노트, 여러 논문, 여러 강의 자료를 같은 스타일로 관리
- 패키지 설정(preamble)이 공통이고 컨텐츠만 다를 때
- main.tex 한 줄만 바꿔서 프로젝트 스위치하고 싶을 때

## 디렉토리 구조

```
RepoRoot/
├── main.tex                          # 공통 preamble + \professor 스위치
├── goodman/
│   ├── content.tex                   # 이 프로젝트의 \input 오케스트레이터
│   ├── refs.bib
│   ├── figures/
│   └── sections/
│       ├── 00_frontmatter.tex
│       ├── 01_intro.tex
│       └── ...
├── andreas/
│   ├── content.tex
│   ├── refs.bib
│   ├── figures/
│   └── sections/
│       └── ...
├── lake/
│   ├── content.tex
│   ├── refs.bib
│   ├── figures/
│   └── sections/
│       └── ...
├── .gitignore
└── build_and_compile.sh              # Optional
```

## main.tex 패턴

```latex
\documentclass[11pt]{article}

% ============================================================
% 프로젝트 스위치 — 이 줄 하나만 바꾸면 됨
% ============================================================
\newcommand{\professor}{goodman}  % goodman | andreas | lake
% ============================================================

% 공통 preamble (모든 프로젝트가 공유)
\usepackage{kotex}
\usepackage{natbib}
\usepackage{tcolorbox}
\tcbuselibrary{most}
\usepackage{tikz}
\usepackage{tabularx}
% ... 기타 패키지 ...

% 프로젝트별 figure 경로
\graphicspath{{\professor/figures/}}

% Overfull hbox 방지
\tolerance=1000
\emergencystretch=3em
\hfuzz=2pt

\begin{document}
\input{\professor/content}
\end{document}
```

## `<project>/content.tex` 패턴

```latex
% 이 프로젝트의 모든 섹션을 순서대로 \input
\input{\professor/sections/00_frontmatter}
\input{\professor/sections/01_intro}
\input{\professor/sections/02_method}
\input{\professor/sections/03_results}
\input{\professor/sections/04_discussion}
\input{\professor/sections/NN_bibliography}
```

## 프로젝트 스위치 워크플로

1. `main.tex`의 `\newcommand{\professor}{...}` 한 줄 수정
2. `bash compile.sh main.tex` 실행 (산출물은 `output.pdf`)
3. PDF는 동일 위치(`output.pdf`)에 생성 — 필요 시 `main_<professor>.pdf`로 rename
   (`output`은 Overleaf의 `-jobname` 고정값. `references/overleaf-parity.md` 참조)

## 패키지 합집합 규칙

여러 프로젝트의 패키지를 합칠 때:
- **모든 프로젝트에 필요한 패키지의 합집합** 사용
- 한 프로젝트만 쓰는 패키지도 preamble에 포함 (사용 안 하면 무시되지만 로드는 됨)
- 충돌하는 패키지(예: natbib vs biblatex)는 한쪽만 선택

## Figure 경로 관리

`\graphicspath{{\professor/figures/}}`로 자동 경로 설정.

각 프로젝트 안에서는:
```latex
\includegraphics{plot1.png}  % 자동으로 \professor/figures/plot1.png 참조
```

## refs.bib 관리

**옵션 A — 프로젝트별 분리** (권장):
```
goodman/refs.bib
andreas/refs.bib
lake/refs.bib
```
`\bibliography{\professor/refs}` 사용.

**옵션 B — 공통 refs.bib**:
```
shared/refs.bib
```
`\bibliography{shared/refs}` 사용. 중복은 BibTeX이 자동 처리.

## 검증 체크리스트

`/latex:structure`가 자동 검증:
- [ ] `main.tex` 컴파일 시 `\professor` 값으로 올바른 프로젝트 로드
- [ ] 각 프로젝트의 `content.tex`가 모든 섹션을 빠짐없이 `\input`
- [ ] `\graphicspath`가 `\professor/figures/`로 올바르게 설정
- [ ] `\bibliography{\professor/refs}` 또는 `shared/refs`가 올바름
- [ ] 프로젝트 스위치 후 cross-reference 깨지지 않음 (`compile.sh` 재실행)

## 빌드 스크립트 (optional)

`build_and_compile.sh`:
```bash
#!/bin/bash
# 사용: bash build_and_compile.sh goodman
PROJECT=${1:-goodman}

# main.tex의 \professor 줄을 sed로 교체
sed -i.bak "s/\\\\newcommand{\\\\professor}{[^}]*}/\\\\newcommand{\\\\professor}{$PROJECT}/" main.tex

bash ~/.claude/skills/latex-publication/scripts/compile.sh main.tex

# PDF rename — compile.sh는 Overleaf와 같은 -jobname=output 을 쓴다
mv output.pdf "main_${PROJECT}.pdf"

# 원복
mv main.tex.bak main.tex
```

## 한계점

- 프로젝트마다 documentclass가 다르면 이 패턴 사용 불가 (단일 main.tex 가정)
- TikZ externalization 사용 시 프로젝트 간 충돌 가능 — 프로젝트별 `\tikzsetexternalprefix` 설정
- `\professor` 명령이 다른 패키지와 충돌 가능 — 다른 이름(`\projectid` 등) 사용 가능
