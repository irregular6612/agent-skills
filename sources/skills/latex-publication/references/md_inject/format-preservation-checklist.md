# Format Preservation Checklist

준비된 LaTeX 템플릿(예: `gist-preprint.sty`)에 MD 변환 fragment를 주입할 때 **포맷이 깨지지 않게 하는** 12개 체크 항목.

## 자동 처리 (skill이 보장)

### 1. 색상 일관성
- **위험**: MD `<font color="#0000ff">` → `\textcolor[HTML]{0000FF}{...}`로 fallback되면 gist-preprint의 `\definecolor{gistblue}` 활용 못함
- **자동 처리**: `templates/md_inject/color-palette-map.yaml`로 hex → 이름 매핑
- **수동 보강**: 새 hex 발견 시 palette YAML에 추가 (audit이 알려줌)

### 2. Section 깊이
- **위험**: MD H1이 `\section` 또는 `\subsection`으로 emit되면, marker가 위치한 깊이와 충돌
- **자동 처리**: `h1_strip: true`(default) + `--top-level-division=subsection` + `--shift-heading-level-by`
- **수동 보강**: 매니페스트로 per-injection override

### 3. Citation 스타일
- **위험**: MD raw `\cite{key}`가 그대로 들어가면 natbib authoryear 환경에서 numeric `[1]`로 렌더
- **자동 처리**: `citation_resolver.py`가 bare `\cite{}` → `\citep{}` 정규화
- **수동 보강**: `defaults.cite_style: biblatex` 시 정규화 비활성화 (현재 v1 미지원, TODO)

### 4. Long table 컬럼
- **위험**: pandoc emit `{@{}llll@{}}`은 모든 컬럼이 좌측 정렬 minipage. 한글이 길면 overflow.
- **자동 처리**: `pandoc_postprocess.py`가 `p{0.25\textwidth}` 등으로 rewrite
- **수동 보강**: 매우 넓은 표 (>4 컬럼)는 `tabularx`로 수동 변경 권장

### 5. `\tightlist` 누락 매크로
- **위험**: pandoc 출력은 `\tightlist`를 사용하지만 정의 없음 → 빌드 에러
- **자동 처리**: planner가 `preamble_additions`에 `\providecommand{\tightlist}{...}` 추가, apply가 idempotent 삽입

### 6. `\hypertarget` 노이즈
- **위험**: pandoc이 `\hypertarget{id}{%\section{X}\label{id}}`로 emit, hyperref 미로딩 시 에러
- **자동 처리**: `pandoc_postprocess.py`가 `\section{X}\label{id}`로 단순화

### 7. `\passthrough{\lstinline!...!}` 한글 깨짐
- **위험**: 인라인 코드 안에 한글이 있으면 `\lstinline!`이 한글 처리 못함
- **자동 처리**: `\texttt{\detokenize{...}}`로 치환

### 8. `\begin{Shaded}\begin{Highlighting}[]` 미정의
- **위험**: `--no-highlight` 플래그를 무시하고 emit되는 경우가 가끔
- **자동 처리**: `lstlisting`으로 강제 치환 + Highlight tok macro 제거

## 수동 처리 (사용자 책임, audit이 surfacing)

### 9. Mermaid placeholder
- **위험**: Phase 7은 `\fbox{...}` 자리표시자만 emit
- **수동 처리**: 사용자가 mmdc 등으로 PNG 생성 후 placeholder를 `\includegraphics{...}`로 교체
- **보조**: meta.json의 `mermaid_blocks[]`가 위치/내용을 알려줌

### 10. 커스텀 명령 활용 (`\val{x}{y}` 등)
- **위험**: gist-preprint의 `\val{56.3}{1.2}` 같은 stat 포맷이 단순 텍스트 "56.3 ± 1.2"로 들어감
- **수동 처리**: 변환 후 audit 경고를 보고 표 안의 해당 셀을 수동 교체
- **자동화 제외 이유**: false positive 위험 (모든 "X ± Y" 패턴이 stat 표시는 아님)

### 11. Korean sans-serif heading fallback
- **위험**: `gist-preprint.sty`의 subsection 헤딩은 Helvetica (`\sffamily`). Helvetica에는 한글 글리프 없음 → kotex이 dotum 등으로 fallback
- **수동 처리**: 시각적 통일을 원하면 .sty에 `\setsanshangulfont{Noto Sans CJK KR}` 추가 (단, Overleaf에서는 폰트 누락 위험)
- **권장**: kotex 기본 fallback 수용 (Overleaf 호환)

### 12. 중복 `\newcommand`
- **위험**: MD에 raw `\newcommand{\foo}{...}`가 있으면 pandoc이 그대로 emit, main.tex에 이미 같은 이름이 있으면 conflict
- **자동 처리**: `pandoc_postprocess.py`가 fragment에서 `\newcommand`/`\renewcommand` 제거 + 경고
- **수동 보강**: 경고에 나온 명령을 `math_commands.tex` 등 preamble로 이동

## 빠른 진단 — 빌드 실패 시

```
! Undefined control sequence \tightlist
  → preamble_additions가 적용 안 됨. apply step 다시 실행.

! Missing $ inserted at \textcolor[HTML]{0000ff}
  → palette map 누락 + 한글 본문에 $ 미스매치 동시 발생. fragment 직접 검사.

! LaTeX Error: Environment lstlisting undefined.
  → main.tex preamble에 \usepackage{listings} 추가 필요.

! File ended while scanning use of \textcolor.
  → <font color> 안에 다중 줄 본문이 들어갔고 escape이 깨짐. fragment 검사.

! Package natbib Warning: Citation 'foo' on page X undefined.
  → references.bib에 entry 누락. citation_resolver 경고를 무시한 결과.
```

## Overleaf 라운드트립 검증

`bash verify_build.sh <project>` 가:
1. 시스템 절대경로 0건 확인
2. `.vscode/`, `.cursor/`, `build/`, `.build/` 제외 후 rsync 시뮬
3. xelatex 빌드 성공 확인

검증을 통과하면 그대로 Overleaf에 push해도 동일 결과 보장.
