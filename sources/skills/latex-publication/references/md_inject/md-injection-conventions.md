# MD→TeX Injection Conventions

이 문서는 `latex-korean-setup` skill의 Part 2 (Phase 6–10) MD→TeX 주입 워크플로우에서 사용하는 마커 컨벤션, 매니페스트 스키마, 마커 ↔ MD 매핑 규칙을 정의한다.

## 1. 핵심 컨벤션 — Paired Sentinel Comments

`main.tex`의 각 주입 영역은 **두 개의 LaTeX 주석**으로 둘러싼다:

```latex
% MD-INJECT: <id>
... 본문 (다음 실행에서 교체됨) ...
% MD-INJECT-END
```

### 규칙

- **`<id>`** 는 `--md-root` 기준 상대 경로 (확장자 `.md` 생략).
  - 예: `% MD-INJECT: design/v3/02_theoretical_foundations`
    → 해석: `<md-root>/design/v3/02_theoretical_foundations.md`
- **두 마커 사이의 모든 줄**이 fragment로 교체된다. 마커 라인 자체는 보존되어 재실행 가능.
- **시작 마커는 한 줄**에 정확히 한 ID만. 인라인 주석 추가 금지:
  ```latex
  % MD-INJECT: foo  ← OK
  % MD-INJECT: foo % some note  ← 작동하지만 ID에 ' % some note'가 붙음, 비권장
  ```
- **종료 마커**는 정확히 `% MD-INJECT-END` (대소문자 일치, 추가 텍스트 금지).
- **중첩 금지**. 새 `% MD-INJECT:`가 직전 마커가 닫히기 전에 나오면 plan이 abort.
- **중복 ID 금지**. 같은 `<id>`를 가진 두 마커는 plan이 abort.

### 권장 위치

마커는 보통 `\section{}` 또는 `\subsection{}` **다음에** 배치한다:

```latex
\subsection{Theoretical Foundations}
\label{sec:theory}

% MD-INJECT: design/v3/02_theoretical_foundations
[본문 placeholder]
% MD-INJECT-END
```

이렇게 하면:
- 주입 영역의 깊이가 명확 (subsection 내부 → fragment top = subsubsection)
- gist-preprint의 `\label{}` 같은 sectioning 메타가 fragment 외부에 보존
- audit Phase 8이 `section_depth_consistency` 체크를 정확히 수행

### Overleaf 호환성

LaTeX 주석(`%`)은 모든 엔진(pdfLaTeX/XeLaTeX/LuaLaTeX)에서 무시되므로, Overleaf로 push해도 빌드에 영향 없음. 마커가 보이지만 PDF에는 출력되지 않는다.

## 2. ID → MD 경로 해석 순서

skill은 `<id>`를 다음 순서로 해석한다:

1. `<md-root>/<id>.md`
2. `<md-root>/<id>/index.md`
3. `<md-root>/**/<basename(<id>)>.md` (단일 매칭만 허용)

세 단계 모두 실패하면 `plan.json.warnings`에 항목 추가, 해당 marker는 `injections[]`에서 제외 (apply 시 영역 보존).

## 3. 매니페스트 (선택)

`md-inject.yaml`을 프로젝트 루트에 두면 per-injection override 가능. 매니페스트는 **선택**이며, 마커가 single source of truth.

스키마는 `templates/md_inject/manifest-example.yaml` 참조. 주요 필드:

| 필드 | 기본 | 설명 |
|---|---|---|
| `target` | auto | main.tex 경로 |
| `md_root` | `docs` | MD 검색 root |
| `build_cache` | `.build/md_inject` | fragment/메타 캐시 |
| `defaults.cite_style` | `natbib` | `natbib` 또는 `biblatex` |
| `defaults.h1_strip` | `true` | MD H1을 fragment에서 제거 |
| `defaults.pandoc_extra_flags` | `[]` | pandoc 추가 플래그 |
| `injections.<id>.*` | — | per-injection override |
| `skip_markers[]` | `[]` | 무시할 marker ID 목록 |

## 4. Bootstrap (마커 없는 main.tex)

마커가 0개인 main.tex에 `md_inject_plan.py --suggest-only`를 돌리면, fuzzy 매칭 기반 삽입 제안이 출력된다:

```
suggestions (12):
  main.tex:60   \section{Introduction}        ← 01_overview_and_principles.md  (conf=0.81)
  main.tex:148  \section{Preliminaries}       ← 02_theoretical_foundations.md  (conf=0.74)
  ...
```

- **confidence ≥ 0.65**: 키워드 사전 매칭 (예: `이론` ↔ `theory`/`theoretical`)
- **0.55 ≤ confidence < 0.65**: ASCII fallback 유사도 (Korean 본문에는 거의 안 걸림)

사용자가 이 제안을 보고 수동으로 마커를 main.tex에 삽입한 뒤 재실행. skill은 **자동으로 main.tex를 수정하지 않는다** (suggest-only는 read-only).

## 5. Fragment 구조

각 fragment는 sentinel 주석으로 감싸진다:

```latex
% ─── BEGIN auto-injected from <relpath> (sha1=abc123def456) ───
\subsection{...}\label{...}
... 본문 ...
% ─── END auto-injected from <relpath> ───
```

- **sha1**: 변환 소스 MD의 SHA1 short hash. 다음 실행 시 비교하여 cache hit 판정.
- **relpath**: `--md-root` 기준 상대 경로. 디버깅 시 origin 추적용.

이 sentinel은 `% MD-INJECT:` 마커 **내부**에 위치하므로, 마커 자체와는 별개로 작동.

## 6. 비파괴 보장

- **백업**: 모든 apply는 `main.tex.bak.<timestamp>`을 남김 (마지막 5개 rotate).
- **SHA1 staleness 체크**: plan 시점과 apply 시점의 main.tex SHA1이 다르면 `--force` 없이 abort.
- **atomic write**: tmp 파일 → `os.replace()`로 원자적 교체. 중간 실패 시 main.tex 손상 없음.
- **skip 영역**: marker가 plan에 없으면 (해석 실패, manifest skip 등) 해당 영역은 손대지 않음.

## 7. 자주 묻는 질문

**Q. 마커 안에 또 다른 `\subsection{}`이 있어도 괜찮나요?**
→ 네. apply step은 마커 사이의 모든 줄을 단순 교체합니다. fragment가 자체 `\subsection`을 포함해도 외부 `\subsection`(마커 직전)과 충돌하지 않습니다.

**Q. 같은 MD를 두 marker에 주입할 수 있나요?**
→ 네, 다른 ID로. 예를 들어 `% MD-INJECT: shared-content-A`와 `% MD-INJECT: shared-content-B`가 모두 `<md-root>/shared-content.md`에 매핑되도록 manifest로 override 가능. 단, plan.json에 경고가 남습니다.

**Q. `--md-root`를 여러 개 지정할 수 있나요?**
→ 현재 v1에서는 단일 root만 지원. 여러 source tree가 필요하면 symlink 사용을 권장.

**Q. 마커 ID에 한글을 쓸 수 있나요?**
→ 기술적으로는 가능 (`% MD-INJECT: 설계/이론`). 하지만 cache 파일명이 `_`로 sanitize되어 가독성이 떨어지므로, ASCII 권장.
