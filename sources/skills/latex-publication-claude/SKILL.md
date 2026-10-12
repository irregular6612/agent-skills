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

### LaTeX engine — 프로젝트가 정한다

엔진을 추측하지 않는다. 아래 순서로 해석하고, 어디에도 없으면 **빌드하지 않고 묻는다.**

| 순서 | 출처 | 범위 |
|---|---|---|
| 1 | `compile.sh --engine= --texlive=` | 이번 실행만 |
| 2 | `<프로젝트>/CLAUDE.md` (없으면 `AGENTS.md`)의 `latex-engine:` / `latex-texlive:` | 그 프로젝트 |
| 3 | 없음 → **exit 4** | — |

`main.tex` 디렉토리부터 위로 올라가며 설정 파일을 찾는다.

```markdown
latex-engine: xelatex
latex-texlive: 2025
```

두 줄 다 있어야 한다. 하나만 있으면 exit 3으로 거부한다 — 나머지를 임의로
채우면 어느 조합으로 만든 PDF인지 알 수 없어진다. 붙여넣을 스니펫은
`templates/claude-md-snippet.md`.

**exit 4를 받으면 반드시 사용자에게 물어라.** 기본값을 고르지 말 것.
`bash scripts/texlive_env.sh --list`로 이 머신에서 쓸 수 있는 조합을 뽑아
`AskUserQuestion`으로 제시하고, 답을 받으면 그 프로젝트 `CLAUDE.md`에
두 줄로 적는다. 그래야 다음 실행부터 다시 묻지 않는다.

| exit | 뜻 |
|---|---|
| 2 | 요청한 엔진·연도가 이 머신에 없음 |
| 3 | 설정이 반쪽 (`latex-engine`만, 또는 `latex-texlive`만) |
| 4 | 설정 없음 — **사용자에게 물어야 함** |

엔진 → latexmk 플래그 매핑은 Overleaf CLSI와 같다:
`pdflatex`→`-pdf`, `latex`→`-pdfdvi`, `xelatex`→`-xelatex`, `lualatex`→`-lualatex`.

상세와 재현 잔차는 `references/overleaf-parity.md`, 엔진 선택은
`references/engine-selection.md`.

### 한글 패키지 우선순위 (engine이 아니라 preamble 패키지)
| 패키지 | 사용 시점 | 산출물 portability |
|--------|---------|------------------|
| `kotex` (기본) | `kpsewhich kotex.sty` 성공 시 자동 선택 | Overleaf 라운드트립 OK (TeX Live 표준 패키지) |
| `xeCJK` (fallback 1) | 시스템 Noto Sans CJK KR 폰트 있을 때 | Overleaf에서 폰트 설치 필요 |
| `ucharclasses` (fallback 2, legacy) | preamble에 직접 작성한 구 워크플로 호환용 | 시스템 폰트 의존 |

셋 다 preamble에서 고르는 한글 조판 패키지다. engine 선택과는 별개 축이다.
(`kotex`은 pdfLaTeX·XeLaTeX 양쪽에서 돌지만 폰트 임베딩 방식이 달라 PDF 크기와 줄바꿈이 달라진다.)
`scripts/diagnose.py`가 어느 패키지가 쓰이고 있는지 진단해 출력한다.

### BibTeX 규칙 (모든 서브커맨드 공통)
- 금지: inline `\begin{thebibliography}`
- 필수: `refs.bib` + `\bibliographystyle{plainnat}` + `\bibliography{<project>/refs}`
- 필수: 모든 텍스트 참조를 `\citep{}` 또는 `\citet{}`로 변환
- 컴파일: `scripts/compile.sh`로 통일. Overleaf와 동일한 latexmk 호출을 쓰며 패스 횟수와 bibtex 실행 여부는 latexmk가 정한다 (고정 3-pass 아님). 기준 환경은 `references/overleaf-parity.md`

상세는 `references/bibtex-rules.md`.

### .gitignore 패턴
`templates/gitignore` 사용. 3개 구 스킬의 합집합.

## 배포 사본 동기화

이 스킬은 두 곳에 산다.

| | 경로 | 역할 |
|---|---|---|
| 원본 | `~/.claude/skills/latex-publication` | 작업본. 여기서 고친다 |
| 배포 사본 | `<marketplace>/plugins/academic-writing/skills/latex-publication` | 플러그인 배포용 |

**손으로 rsync 하지 말 것.** 배포 사본에는 원본에 둘 수 없는 치환이 두 개 있고,
단순 복사는 그것을 지워 플러그인을 깨뜨린다.

| | 원본 | 배포 사본 |
|---|---|---|
| 경로 규약 | `~/.claude/skills/latex-publication/...` | `${CLAUDE_PLUGIN_ROOT}/skills/latex-publication/...` |

```bash
bash scripts/sync_plugin.sh --dry-run   # 무엇이 지워지는지 먼저 확인
bash scripts/sync_plugin.sh
```

치환 후 문법 검사와 "홈 경로 잔존" 검사까지 스크립트가 수행한다.

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
