---
name: latex-publication
description: >-
  LaTeX 학술 문서 출판 워크플로 — 5개 서브커맨드 자동 라우팅. TRIGGERS: 한글 LaTeX 셋업/한글 렌더링 안됨/kotex 설정/Overleaf 한글/tex 한국어 → :setup · MD를 LaTeX에 주입/마크다운 논문 변환/md 템플릿 주입/md-to-tex → :inject · LaTeX survey/academic PDF/서베이 PDF/논문 PDF 빌드/xelatex → :build · latex structure/section split/tex 구조화/섹션 분리 → :structure · latex git push/overleaf push → :push. 모호하면 AskUserQuestion 1회로 build vs inject 확인.
license: MIT
metadata:
  category: academic
  locale: multi
  phase: v1
allowed-tools: [Read, Write, Edit, Bash, Glob, Grep, AskUserQuestion]
---

# LaTeX Publication — 통합 출판 워크플로

학술 LaTeX 문서 출판의 5개 워크플로를 한 스킬에서 라우팅합니다. 기존 3개 스킬(`academic-latex-pipeline`, `latex-korean-setup`, `latex-project-manager`)을 통합한 결과물.

## 사용자 의도 → 서브커맨드 라우팅 표

| 사용자가 말한 것 / 트리거 | 라우팅 결과 |
|---|---|
| "한글 LaTeX 환경 셋업해줘", "한글이 PDF에 안 나옴", "Cursor에서 한글 빌드 안 됨" | `commands/setup.md` |
| "MD를 우리 LaTeX 템플릿에 합쳐줘", "docs의 한글 MD를 main.tex에 넣어줘" | `commands/inject.md` |
| "MD로 논문 PDF 빌드", "Obsidian 서베이를 PDF로", "xelatex으로 빌드" | `commands/build.md` |
| "이 tex 파일을 섹션별로 분리", "monolithic LaTeX 정리" | `commands/structure.md` |
| "Overleaf에 push", "GitHub에 LaTeX 프로젝트 올려" | `commands/push.md` |
| "한글 마크다운으로 논문 PDF 빌드" (복합) | `setup.md` 진단 → 필요 시 `setup` 실행 후 `build` |
| "MD를 LaTeX로" (모호) | AskUserQuestion: 독립 PDF인가요(`build`), 기존 템플릿 주입인가요(`inject`)? |

서브커맨드 진입 시 해당 `commands/<name>.md`를 Read로 읽고 그 안의 워크플로를 따른다.

## 공통 원칙

### 한글 폰트 우선순위
| Engine | 사용 시점 | 산출물 portability |
|--------|---------|------------------|
| `kotex` (기본) | `kpsewhich kotex.sty` 성공 시 자동 선택 | Overleaf 라운드트립 OK (TeX Live 표준 패키지) |
| `xeCJK` (fallback 1) | 시스템 Noto Sans CJK KR 폰트 있을 때 | Overleaf에서 폰트 설치 필요 |
| `ucharclasses` (fallback 2, legacy) | `--engine=ucharclasses` 명시 시 (구 academic-latex-pipeline 워크플로 호환) | 시스템 폰트 의존 |

`scripts/diagnose.py`가 환경을 진단해 권장 engine을 출력. 사용자 override는 `--engine=...` 플래그.

### BibTeX 규칙 (모든 서브커맨드 공통)
- 금지: inline `\begin{thebibliography}`
- 필수: `refs.bib` + `\bibliographystyle{plainnat}` + `\bibliography{<project>/refs}`
- 필수: 모든 텍스트 참조를 `\citep{}` 또는 `\citet{}`로 변환
- 컴파일: 3-pass (`pdflatex → bibtex → pdflatex → pdflatex`) — `scripts/compile.sh`로 통일

상세는 `references/bibtex-rules.md`.

### .gitignore 패턴
`templates/gitignore` 사용. 3개 구 스킬의 합집합.

## 서브커맨드 cross-link

- `commands/setup.md` — 한글 LaTeX 환경 셋업
- `commands/inject.md` — MD → 기존 TeX 템플릿 주입
- `commands/build.md` — MD → 독립 PDF 빌드
- `commands/structure.md` — Monolithic TeX → 섹션 분리
- `commands/push.md` — Git/Overleaf push

## 다른 스킬과의 관계

| 다른 스킬 | 관계 |
|---------|------|
| `iterative-academic-writer` | `:build` Phase 1에서 호출 (content quality gate) |
| `academic-slides-iterative` | 별개 — Beamer 슬라이드 critic loop, LaTeX는 도구일 뿐. 슬라이드 작업은 그 스킬로. |
| `update-study` | 별개 — 실험 분석. LaTeX export는 부수 기능. |
| `paper-driller` / `paper-section-rewrite` | 컨텐츠 작성용. PDF 빌드는 `:build`로 체이닝. |

## 통합 이력

이 스킬은 다음 3개를 통합한 결과 (2026-05-20):
- `academic-latex-pipeline` → `commands/build.md` + `scripts/md2tex/modes/build.py`
- `latex-korean-setup` → `commands/setup.md` + `commands/inject.md` + `scripts/md2tex/modes/inject.py`
- `latex-project-manager` → `commands/structure.md` + `commands/push.md`

설계 명세서: `.work/latex-merge/01_design.md` (저장소 외부)
