# /latex:inject — MD → 기존 TeX 템플릿 주입

이미 작성된 한글 Markdown 문서를 준비된 LaTeX 템플릿(예: gist-preprint)의 sentinel 마커 영역에 포맷을 깨뜨리지 않고 주입한다. Idempotent하며 `main.tex.bak.<timestamp>` 자동 백업.

**전제조건**: `/latex:setup` 완료 (kotex이 preamble에 로드되어 있고, xelatex 엔진 설정됨).

## When to use

- docs/에 이미 작성된 MD 문서를 논문 LaTeX 템플릿에 옮겨야 함
- 여러 MD 섹션을 한 번에 변환하고 싶음 (예: docs/design/v3/의 18개 파일)
- gist-preprint 같은 커스텀 스타일의 `\textcolor{gistred}`, `\citep{}`, tcolorbox 일관성 유지
- MD를 계속 수정하면서 LaTeX 본문을 자동 싱크

## When NOT to use

- MD를 독립 PDF로 빌드 → `/latex:build`
- LaTeX 환경 셋업 자체 → `/latex:setup`

---

## 사용자가 한 번만 해야 할 일 — main.tex에 마커 추가

`main.tex`의 각 주입 영역에 paired sentinel을 배치:

```latex
\subsection{Theoretical Foundations}
\label{sec:theory}

% MD-INJECT: design/v3/02_theoretical_foundations
[placeholder content]
% MD-INJECT-END
```

- `<id>` = `--md-root` 기준 상대경로(확장자 제외)
- 두 마커 사이의 모든 줄이 fragment로 교체됨
- 마커 라인 자체는 보존 → 재실행 가능

컨벤션 상세는 `../references/md_inject/md-injection-conventions.md`.

## 실행 — 두 가지 경로

### 경로 A: 헤드리스 Python 전용 (fastest, Phase 8 LLM 감사 skip)

```bash
python3 ~/.codex/skills/latex-publication/scripts/md2tex/modes/inject.py <project> \
    [--target main.tex] \
    [--md-root docs] \
    [--manifest md-inject.yaml] \
    [--workers 8] \
    [--no-auto-cite] \
    [--dry-run] \
    [--no-verify]
```

Phase 통합 entry point로도 호출 가능:
```bash
python3 ~/.codex/skills/latex-publication/scripts/md2tex/convert.py --mode=inject <project> [옵션]
```

Phases 6 → 7 → 9 → 10을 순차 실행. 소요 약 15–30초 (18개 MD 기준).

### 경로 B: Skill 기반 (Phase 8 LLM 감사 포함, 포맷 품질 ↑)

이 서브커맨드가 호출되면 다음 워크플로우가 실행된다:

**Phase 6 — Plan Injection** (1 × LLM subagent)

`md-tex-injection-planner` 서브에이전트가:
1. `md2tex/modes/inject_legacy/md_inject_plan.py`로 결정론적 plan 생성 (`.build/md_inject/plan.json`)
2. fuzzy 매칭 모호성을 semantic 추론으로 보정
3. 최종 `InjectionPlan` JSON 반환

서브에이전트 정의: `../agents/md-tex-injection-planner.md`

**Phase 7 — Convert (parallel)** (1 × LLM coordinator, Python pool 내부)

`md-fragment-converter-coordinator`가 `md2tex/modes/inject_legacy/md_inject_convert.py --workers N`을 호출.
Python ProcessPoolExecutor가 N개의 pandoc 변환을 동시 실행:

- Pre-process: frontmatter/wikilink strip, `<font color>` → `\textcolor`, mermaid → placeholder, `Author(Year)` → `\citep{}`
- Pandoc: `--from gfm+tex_math_dollars+... --to latex --no-highlight --wrap=none --listings`
- Post-process: `\hypertarget` 제거, `\passthrough` 정규화, longtable 컬럼 재작성, sentinel 주석 삽입

Coordinator는 실패를 cluster화 (예: "pandoc missing → 전체 N건 영향")해 단일 메시지로 요약.

**Phase 8 — Audit Fragments (parallel)** (N × LLM subagents, 단일 메시지 내 병렬 dispatch)

각 성공 fragment마다 `tex-fragment-format-auditor` 하나씩 병렬 호출. 체크 항목:

1. `color_palette_consistency` — `\textcolor[HTML]{}`이 palette에 매핑 가능한지
2. `section_depth_consistency` — fragment top-level이 marker 깊이와 일치
3. `tcolorbox_safety` — 중첩 tcolorbox 없음
4. `citation_style_consistency` — natbib 환경에서 bare `\cite{}` 잔존 없음
5. `custom_command_usage` — `\val{x}{y}` 권장 사례
6. `unresolved_citations` — 미매칭 citation surfacing

출력: `AuditReport` JSON per fragment + optional auto-fix sed patterns.

**Phase 9 — Apply (serial atomic)**

`md2tex/modes/inject_legacy/md_inject_apply.py`가:
1. main.tex SHA1 staleness 확인 (plan 이후 변경되었으면 abort)
2. `main.tex.bak.<timestamp>` 백업 (5개 rotate)
3. 각 marker 영역을 fragment로 교체
4. preamble additions idempotent 삽입
5. tmp → atomic rename

**Phase 10 — Verify**

`../scripts/verify_build.sh <project>` 재호출 (Overleaf simulation 포함). 실패 시 `main.tex.bak.<latest>`에서 자동 롤백 안내.

## 한 눈에 — 실행 모드 비교

| 모드 | 명령 | Phase 8 (LLM 감사) | 시간 | 언제? |
|---|---|---|---|---|
| Headless fast | `inject.py <project>` 직접 (orchestrator) | skip | ~15–30s | 반복 재변환, CI |
| Skill full | 서브커맨드 호출 | 포함 (N parallel) | ~1–3min | 첫 실행, 포맷 품질 검증 |
| Dry-run | `inject.py <project> --dry-run` | n/a | ~5s | main.tex diff 확인만 |
| Plan only | `inject_legacy/md_inject_plan.py <project>` | n/a | ~1s | suggest 모드, 매핑 확인 |

---

## Common Issues & Fixes

| 증상 | 원인 | 처방 |
|---|---|---|
| `pandoc not on PATH` | pandoc 미설치 | `brew install pandoc` |
| `no MD file found for marker 'foo'` | ID가 `--md-root` 기준 경로와 불일치 | marker ID 정정 or manifest override |
| `main.tex changed since plan was built` | plan 이후 main.tex 수동 편집 | `inject_legacy/md_inject_plan.py` 재실행 or `--force` |
| fragment에 mermaid placeholder | default 동작 | `\fbox{}`을 수동으로 `\includegraphics{}`로 교체 |
| bare `\cite{}`이 `\citep{}`로 바뀜 | natbib 정규화 (의도된 동작) | `cite_style: biblatex`가 필요하면 manifest (v1 미지원) |
| Author(Year) 거짓 매칭 | "4×2 (2026)" 같은 패턴을 citation으로 인식 | `--no-auto-cite` 또는 audit 경고를 보고 수동 교정 |
| Overfull hbox (한글 줄바꿈) | kotex tolerance 기본값 | preamble additions에 `\tolerance=1000` (자동 삽입됨) |

---

## Template presets

If the target project uses a custom template (e.g. `gist-preprint.sty` with its `researchquestion` / `highlightbox` / `algorithm` environments), the skill can emit those instead of stock LaTeX:

```bash
python3 inject.py <project> --target main.tex --md-root docs \
    --template-preset gist-preprint   # explicit
```

Or auto-detect: if `main.tex` contains `\usepackage{gist-preprint}`, the preset activates without any flag.

Currently supported preset: `gist-preprint`. Mapped items:

- ` ```algorithm ` fenced block → `\begin{algorithm}[t]\begin{algorithmic}[1]...` with `Require/Ensure/For/If/Return` pseudocode keywords parsed. Inside the fence, `caption: X` → `\caption{X}`, `label: Y` → `\label{Y}`.

(More mappings — `highlightbox`, `researchquestion`, `\val{}`, `\tokenred{}` — documented in `../references/template-items.md`.)

Projects without the preset follow the default rules documented above.

## Default postprocessing rules

Beyond the raw pandoc output, the skill applies these Korean-MD-aware cleanups unless explicitly disabled via `PostprocessConfig`:

| Rule | Flag (default) | What it does |
|---|---|---|
| Unwrap `\begin{quote}` | `unwrap_blockquotes=True` | Markdown `> ...` callouts become plain paragraphs (no indented frame) |
| Strip prose `\textbf{}` | `strip_prose_bold=True` | Bold wrapping > 12 chars OR containing sentence punctuation gets unwrapped; short labels (`IV`, `α 보존`) preserved |
| Attach trailing captions | `attach_trailing_captions=True` | `\emph{Table N: ...}` / `\emph{Figure N: ...}` / `\emph{표 N: ...}` / `\emph{그림 N: ...}` right after a `table*`/`figure*` float is moved inside as `\caption{...}` |
| lstlisting defensive styling | auto when `lstlisting` emitted | Injects `\lstset{basicstyle=\footnotesize\ttfamily, breaklines=true, columns=fullflexible}` into the preamble so code blocks fit in a 2-col column |
| Pipe-table → placeholder | always | Bare ``` fenced blocks where ≥3 lines each contain ≥3 `|` are detected as ASCII pseudo-tables and rendered as `\fbox` placeholder (they'd otherwise overflow as `lstlisting`) |

---

## Re-use & References

- `../references/md_inject/md-injection-conventions.md` — 마커 + manifest 스키마
- `../references/md_inject/pandoc-flags-rationale.md` — 모든 pandoc 플래그 설명
- `../references/md_inject/format-preservation-checklist.md` — 포맷 보존 12개 항목
- `../references/template-items.md` — 지원 가능한 template (gist-preprint) item 카탈로그 + 매핑 가이드
- `../templates/md_inject/manifest-example.yaml` — override YAML 예시
- `../templates/md_inject/color-palette-map.yaml` — hex → gist palette 매핑
- `../templates/md_inject/marker-snippet.tex` — main.tex에 붙여넣을 마커 블록
- `../agents/md-tex-injection-planner.md`, `../agents/md-fragment-converter-coordinator.md`, `../agents/tex-fragment-format-auditor.md` — 서브에이전트 정의
- `../examples/md_inject/sample-*.{md,tex}` — smoke regression baseline

## Trigger phrases

- "MD를 LaTeX에 주입" / "마크다운 논문 변환"
- "MD를 템플릿에 합쳐줘" / "docs의 한글 MD를 main.tex에 넣어줘"
- "/latex:inject [project_dir]" / "/md-to-tex"

## Auto-chain

- "한글 마크다운으로 논문 빌드" → `/latex:setup` 필요 시 먼저 실행 후 `/latex:inject`
