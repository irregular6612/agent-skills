# Common Issues & Fixes — latex-publication 통합

3개 구 스킬에 분산돼있던 트러블슈팅 표를 카테고리별로 통합. 각 서브커맨드의 SKILL.md에도 핵심 항목 일부 중복 노출.

## 카테고리

1. [한글 폰트 / 인코딩](#1-한글-폰트--인코딩)
2. [컴파일 에러](#2-컴파일-에러)
3. [Table / Overflow](#3-table--overflow)
4. [Figure / TikZ](#4-figure--tikz)
5. [Citation / BibTeX](#5-citation--bibtex)
6. [MD → TeX 변환](#6-md--tex-변환)
7. [Overleaf / Git push](#7-overleaf--git-push)
8. [IDE / 환경](#8-ide--환경)

---

## 1. 한글 폰트 / 인코딩

| 증상 | 원인 | 처방 |
|------|------|------|
| 한글이 PDF에 안 나옴 + PDF 안 갱신 | pdfLaTeX silent fail | engine을 xelatex로 (`% !TEX program = xelatex`) |
| 한글이 빈 박스(□)로 표시 | 폰트 누락 (xeCJK/ucharclasses 모드) | `brew install --cask font-noto-sans-cjk-kr` |
| `Package kotex Error: ...` | TeX Live 구버전 | `tlmgr update --self --all` |
| Overleaf에서만 한글 깨짐 | 시스템 폰트에 의존 | xeCJK → kotex로 전환 (`/latex:setup`) |
| Korean text 누락 (silent) | Noto Sans CJK KR 미설치 | `fc-list \| grep Noto` 확인 |
| `Missing character: There is no 가` | 폰트 mapping 누락 | kotex 또는 xeCJK 패키지 로드 확인 |

## 2. 컴파일 에러

| 증상 | 원인 | 처방 |
|------|------|------|
| Overfull hbox | 라인 너비 초과 | `\tolerance=1000`, `\emergencystretch=3em` 추가, 또는 reword |
| `Undefined control sequence` | 미로드 패키지 | preamble에 `\usepackage{...}` 추가 |
| `! Package ... Error: ... requires xelatex` | 잘못된 engine | magic comment를 xelatex로 |
| `! LaTeX Error: File 'foo.sty' not found` | 패키지 미설치 | `tlmgr install foo` |
| `\\` 라인 분리 실패 | math mode 또는 LR mode | context별 escape 확인 |
| `compile.sh` 완료 후에도 `??` reference | `\label` 누락 | `\label{...}` 정의 후 재컴파일 |

## 3. Table / Overflow

| 증상 | 원인 | 처방 |
|------|------|------|
| Table이 margin 밖으로 overflow | `lcccc` 같은 자동 폭 열이 너무 넓음 | `p{2cm}` 또는 `tabularx` + `X` 열로 변경 |
| Overfull hbox (table) | 같음 | 헤더 축약 또는 폰트 축소 |
| Table 캡션이 잘못된 위치 | `\caption` 위치 | `\begin{table}` 직후 또는 `\end{table}` 직전 |
| Long table이 페이지 break 안 됨 | `tabular`은 break 불가 | `longtable` 또는 `xtab` 패키지 사용 |
| pipe-table이 LaTeX에서 깨짐 | ASCII pseudo-table | pandoc로 정식 변환 또는 `\fbox` 플레이스홀더 |

## 4. Figure / TikZ

| 증상 | 원인 | 처방 |
|------|------|------|
| Figure 누락 또는 빈 칸 | TikZ 코드 에러 | standalone class로 isolate 테스트 |
| TikZ figure 사이즈 부적절 | `\resizebox` 누락 | `\resizebox{\textwidth}{!}{...}` 래핑 |
| Figure 배치가 페이지 끝에 | float 기본 동작 | `[H]` float specifier (`float` 패키지 필요) |
| pgfplots xticklabel `\\` 에러 | LR mode에서 `\\` 사용 불가 | `{Label Text}` + `align=center` |
| `\legend`에서 `$\to$` 에러 | pgfplots legend의 math mode 제한 | `\textrightarrow{}` 사용 |
| Mermaid가 LaTeX에 그대로 잔존 | 빌드 스크립트 regex 누락 | preprocess의 `mermaid_extract` 확인 |
| TikZ 컴파일 시간 매우 김 | externalization 미사용 | `\usetikzlibrary{external}` + `\tikzexternalize` |

## 5. Citation / BibTeX

| 증상 | 원인 | 처방 |
|------|------|------|
| `Citation undefined` | refs.bib에 key 없음 | 엔트리 추가, bibtex 재실행 |
| `[?]` 형태로 표시 | ref/citation 미해소 | `compile.sh` 재실행 (latexmk가 수렴까지 반복) |
| BibTeX 엔트리 누락 | `.bib`에 key 없음 | `refs.bib`에 엔트리 추가 |
| `(Author, Year)` plain text 잔존 | 자동 변환 실패 | 수동으로 `\citep{key}` 변환 |
| bare `\cite{}`이 `\citep{}`로 바뀜 | natbib 정규화 (의도된 동작) | 의도된 동작, biblatex 필요 시 manifest 설정 |
| Author(Year) 거짓 매칭 | "4×2 (2026)" 같은 수식 | `--no-auto-cite` 또는 수동 교정 |
| 같은 key가 중복 entry | bibtex 임의 선택 | 중복 제거 또는 key rename |

상세는 `bibtex-rules.md`.

## 6. MD → TeX 변환

| 증상 | 원인 | 처방 |
|------|------|------|
| `pandoc not on PATH` | pandoc 미설치 | `brew install pandoc` |
| `[[wikilink]]` 잔존 | preprocess에서 strip 실패 | preprocess regex 확인 |
| `no MD file found for marker 'foo'` | ID가 `--md-root` 기준 경로와 불일치 | marker ID 정정 또는 manifest override |
| `main.tex changed since plan was built` | plan 이후 수동 편집 | `inject.py --plan` 재실행 또는 `--force` |
| fragment에 mermaid placeholder | default 동작 | `\fbox{}`을 `\includegraphics{}`로 수동 교체 |
| Overfull hbox (한글 줄바꿈) | kotex tolerance 기본값 | preamble additions에 `\tolerance=1000` (자동 삽입) |
| frontmatter YAML 잔존 | preprocess 누락 | frontmatter regex 확인 |
| `\hypertarget` 잔존 | postprocess 누락 | postprocess의 hypertarget strip 확인 |

## 7. Overleaf / Git push

| 증상 | 원인 | 처방 |
|------|------|------|
| Overleaf git 403 | 무료 플랜 | Premium plan 필요, 또는 GitHub 사용 |
| `RPC failed; HTTP 401` | 토큰 만료/잘못됨 | 새 토큰 생성, env var 재설정 |
| `pack exceeds maximum allowed size` | 빌드 artifact 또는 PDF가 커밋됨 | `.gitignore` 확인, `git rm --cached` |
| 한글 파일명 한자가 깨짐 | `core.quotepath` 기본값 | `git config core.quotepath false` |
| Overleaf에 push 후 빌드 실패 | 시스템 폰트 의존 | kotex로 전환 (`/latex:setup`) |
| `.aux` 등 빌드 캐시 committed | `.gitignore` 누락 | `../templates/gitignore` 적용 |

## 8. IDE / 환경

| 증상 | 원인 | 처방 |
|------|------|------|
| Cursor/VSCode에서 한글 빌드 안 됨 | LaTeX Workshop이 프로젝트와 다른 engine 사용 | `scripts/gen_vscode_settings.sh <프로젝트>` 재실행 |
| `latexmk` 미설치 | TeX Live 일부 누락 | `tlmgr install latexmk` |
| 빌드 폴더가 git에 들어감 | `.vscode/`, `build/` ungitignored | `.gitignore`에 추가 (`templates/gitignore`) |
| VSCode가 미리보기 PDF 못 엽 | viewer 설정 미스 | settings.json `latex-workshop.view.pdf.viewer` 확인 |

---

## 빠른 진단

문제 type 모를 때:

1. `scripts/diagnose.py <project_dir>` 실행 — 환경 진단
2. `main.log`의 마지막 50줄 확인 — 마지막 에러부터 역추적
3. `main.blg` 확인 — citation 문제
4. `pdflatex -interaction=nonstopmode main.tex 2>&1 | grep -E '^!|Error'` — 모든 에러 추출
