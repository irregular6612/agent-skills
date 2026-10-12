# /latex:setup — 한글 LaTeX 환경 셋업

Cursor(혹은 VSCode)에서 LaTeX 프로젝트를 편집하면서 한글이 깨지지 않게 하고, 그 결과물을 그대로 Overleaf로 다시 올려도 빌드되도록 환경을 셋업한다.

## When to use

- "한글을 추가했는데 PDF에 안 나옴" — silent build fail
- Overleaf에서 받은 영문 템플릿에 한글 섹션을 추가
- Cursor에 LaTeX Workshop을 막 깔았는데 한글 빌드가 안 됨
- 협업자/Overleaf로 다시 올렸을 때도 깨지지 않는 portable setup 필요

## When NOT to use

- 순수 영문 프로젝트에 한글 패키지 추가 (over-engineering)
- Markdown → 독립 PDF 파이프라인 → `/latex:build`
- MD를 기존 LaTeX 템플릿의 마커 영역에 주입 → `/latex:inject`
- LyX/TeXShop 같은 다른 IDE

## 핵심 설계 원칙

| 원칙 | 적용 방법 |
|---|---|
| **Overleaf 라운드트립 호환** | 소스는 portable한 패키지만 (default `kotex`), 시스템 폰트 의존 회피 |
| **비파괴 패치** | 기존 `.sty` 수정 금지. wrapper 패키지 / sentinel 주석으로 분리 |
| **로컬/git 분리** | IDE 설정(`.vscode/`), 빌드 캐시(`build/`, `.build/`)는 `.gitignore` |
| **롤백 가능** | 두 줄 제거로 원복 |

## Engine — 고정 (메인 SKILL.md 공통 원칙)

engine은 **xelatex + TeX Live 2025** 하나뿐이다. fallback 없다.
기준값은 `../scripts/texlive_env.sh`.

아래 `kotex` → `xeCJK` → `ucharclasses` 우선순위는 **한글 조판 패키지** 선택이며
engine과 무관하다. 셋 다 xelatex 위에서 돈다.
상세는 `../SKILL.md`의 "한글 패키지 우선순위" 표.

---

## Phase 1 — Diagnose (read-only)

```bash
python ~/.claude/skills/latex-publication/scripts/diagnose.py [project_dir]
```

진단 항목:
1. **엔진/패키지**: `which xelatex`, `kpsewhich kotex.sty`/`xeCJK.sty`
2. **메인 `.tex` 식별**: `% !TEX root` 우선, 없으면 `\documentclass` 스캔
3. **Preamble**: magic comment, 한글 패키지, pdfLaTeX-only marker(`inputenc`, `fontenc[T1]`, `tgpagella`, `mathpazo`)
4. **`.bib` 한글 포함** 여부 (biber 권장)
5. **빌드 `.log`** `Missing character` 경고 카운트
6. **시스템 폰트** `fc-list :lang=ko`

## Phase 2 — Plan patch

| 진단 결과 | 패치 방식 |
|---|---|
| Preamble 깨끗 | main.tex에 `\usepackage{korean-patch}` + magic comment |
| Custom .sty가 pdfLaTeX 전용 | `korean-patch.sty` 주입, **기존 .sty는 보존** |
| 이미 `kotex` 있음 | magic comment만 → Phase 5로 직행 |
| 이미 `xeCJK` | 폰트 확인, 없으면 `brew install --cask font-noto-sans-cjk-kr` |
| 구 워크플로가 `ucharclasses` 사용 | preamble 유지, Noto Sans CJK KR 설치 확인 (`templates/`에 전용 .sty 없음) |

## Phase 3 — Apply patches (Overleaf-tracked)

(a) main.tex 첫 줄: `% !TEX program = xelatex`
(b) `\documentclass` 다음: `\usepackage{korean-patch}`
(c) `templates/korean-patch.sty` 복사 → 프로젝트 루트
(d) `templates/latexmkrc` 복사 → 프로젝트 루트
(e) `.vscode/settings.json`은 복사하지 말고 생성한다:
    `bash ../scripts/gen_vscode_settings.sh <프로젝트>`
    프로젝트가 정한 엔진·TeX Live로 recipe를 찍어내므로 에디터와 `compile.sh`가 갈리지 않는다.

xeCJK 모드가 필요하면 `templates/korean-patch-xecjk.sty`를 `korean-patch.sty`로 복사.
ucharclasses 모드는 `templates/korean-patch-ucharclasses.sty`를 사용.

## Phase 4 — IDE config (Local-only, gitignored)

(a) `.vscode/settings.json` ← `scripts/gen_vscode_settings.sh <프로젝트>` 로 생성 (복사 아님)
(b) `.gitignore`에 `templates/gitignore`의 IDE/빌드 캐시 섹션 append

## Phase 5 — Verify

```bash
bash ~/.claude/skills/latex-publication/scripts/verify_build.sh [project_dir]
```

검증:
- `examples/korean-test.tex` xelatex 빌드 성공
- PDF에서 `pdftotext`로 `한글` 문자열 추출 확인
- 시스템 절대경로 0건
- `.vscode/` 제외한 Overleaf 시뮬 빌드 성공

---

## Common Issues & Fixes

| 증상 | 원인 | 처방 |
|---|---|---|
| 한글 안 나옴 + PDF 안 갱신 | pdfLaTeX silent fail | engine을 xelatex로 (Phase 3 적용) |
| 한글이 빈 박스(□) | 폰트 누락 (xeCJK 모드) | `brew install --cask font-noto-sans-cjk-kr` |
| `Package kotex Error` | TeX Live 구버전 | `tlmgr update --self --all` |
| Overleaf에서만 깨짐 | 시스템 폰트 의존 | xeCJK → kotex 전환 |

더 많은 이슈는 `../references/common-issues.md` 참조.

## Overleaf Round-trip 체크리스트

세부는 `../references/overleaf-compat-checklist.md`. 핵심:

- [ ] 패치 후 `git status`에서 `.vscode/`, `build/`, `.build/`, `*.aux` 등이 untracked
- [ ] `% !TEX program = xelatex` magic comment in main.tex (로컬 에디터용 — Overleaf는 무시)
- [ ] `latexmkrc`가 프로젝트 루트에 있고 git에 포함됨
- [ ] Overleaf Settings의 Compiler/TeX Live 값이 `scripts/compile.sh` 상단 상수와 일치
- [ ] `korean-patch.sty`가 git에 포함됨
- [ ] 시스템 절대경로 0건

## Trigger phrases

- "한글 LaTeX 셋업해줘" / "tex 파일에 한글이 안 나와"
- "Cursor에서 한글 LaTeX 빌드" / "Overleaf 한글 호환되게 셋업"
- "/latex:setup [project_dir]"

## 다음 단계

Setup 완료 후:
- MD 컨텐츠를 LaTeX로 옮기려면 → `/latex:inject` (기존 템플릿 주입) 또는 `/latex:build` (독립 PDF)
- 단일 .tex를 섹션별로 정리하려면 → `/latex:structure`
- Overleaf/GitHub push → `/latex:push`
