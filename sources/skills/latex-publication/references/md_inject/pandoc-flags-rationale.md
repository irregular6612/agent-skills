# Pandoc Flags Rationale

`md_inject_convert.py` Phase 7에서 각 MD를 변환할 때 pandoc에 전달하는 플래그들의 근거.

## 기본 명령

```bash
pandoc \
  --from gfm+tex_math_dollars+raw_tex+fenced_code_attributes+pipe_tables \
  --to latex \
  --no-highlight \
  --wrap=none \
  --listings \
  --output <stem>.raw.tex \
  <stem>.preprocessed.md
```

추가로 per-injection 플래그가 manifest나 planner에 의해 붙는다.

## 플래그별 근거

### `--from gfm+tex_math_dollars+raw_tex+fenced_code_attributes+pipe_tables`

**가장 중요한 플래그.** 입력 형식과 활성화할 extension을 함께 명시.

| Extension | 왜 필요한가 |
|---|---|
| `gfm` | GitHub-Flavored Markdown 베이스. Obsidian/GitHub MD는 모두 GFM 호환. |
| `tex_math_dollars` | `$x$`, `$$X$$`을 LaTeX math로 인식. 이게 없으면 `$`는 일반 문자 처리되어 수식이 깨짐. |
| `raw_tex` | `` `\citep{...}`{=latex} `` 같은 raw-tex span을 verbatim 보존. citation_resolver가 만든 `\citep{}`을 pandoc이 escape하지 않게 함. |
| `fenced_code_attributes` | ` ```python {.numberLines} ` 같은 attribute syntax 인식. 일부 MD에서 사용. |
| `pipe_tables` | `\| col1 \| col2 \|` 형식 테이블 인식. Squid-Game 설계 문서가 사용하는 형식. |

이 extension들은 GFM에서 일부만 default로 켜지므로 명시 필요.

### `--to latex`

LaTeX 출력. `--to beamer`나 `--to context`가 아님 — 일반 article-class용.

### `--no-highlight`

pandoc의 기본 syntax highlighter는 `\KeywordTok{...}`, `\StringTok{...}` 같은 매크로를 emit한다. 이는 `gist-preprint.sty`나 일반 `article` 클래스에서 정의되지 않아 컴파일 에러.

대안:
- 코드 블록 자체는 `--listings`로 `lstlisting` 환경에 넣고 (별도 플래그)
- highlight는 비활성화

### `--wrap=none`

pandoc의 기본은 `--wrap=auto` (~72자에서 줄바꿈). 우리의 후처리 단계는 정규식이 한 줄에 맞는 패턴(특히 `\textcolor{gistred}{...}`)을 가정하므로, wrap이 들어가면 패턴이 깨진다. 또한 `--dry-run` diff가 가독성 떨어짐.

### `--listings`

코드 블록을 `\begin{verbatim}` 대신 `\begin{lstlisting}` 환경으로 emit. `lstlisting`은:
- 줄 번호 가능
- 키워드 색상 가능 (`gist-preprint.sty:23`이 `inconsolata` + lstlisting 설정 보유)
- pdfLaTeX/XeLaTeX 호환

### `--top-level-division=section` 또는 `subsection`

**상황 의존** — planner가 결정.

- 마커가 `\section{...}` 직후 = 주입 영역이 section 내부 → fragment top은 `\subsection` → `--top-level-division=subsection` + `--shift-heading-level-by=1`
- 마커가 `\subsection{...}` 직후 = subsection 내부 → fragment top은 `\subsubsection` → `--top-level-division=subsection` + `--shift-heading-level-by=2`
- 마커가 top-level (\section 사이) = fragment top은 `\section` → `--top-level-division=section` (default)

**왜 중요한가**: pandoc의 default는 H1 → `chapter`인데 `article` 클래스에는 `\chapter`가 없어 silent 빈 출력. `--top-level-division=section`이면 H1 → `\section`.

`h1_strip: true`(default)일 때는 추가로 MD의 `# title` 줄 자체를 pre-process에서 제거한다. 이렇게 하면 fragment에 중복된 heading이 안 들어간다.

### `--output <stem>.raw.tex`

stdout이 아닌 파일로 출력. ProcessPoolExecutor 환경에서 stdout 캡처는 race condition 위험.

### (의도적으로 끄는) `--standalone`

기본 `--standalone=false` (= 명시 안 함). `--standalone`을 켜면 pandoc이 `\documentclass` + `\begin{document}` ... `\end{document}` 전체 wrapper를 생성한다. 우리는 fragment만 필요하므로 끔.

후처리 단계에서 정규식 `\\(?:begin|end)\{document\}`로 혹시 emit된 wrapper를 제거하는 안전장치도 있음.

### (의도적으로 끄는) `--citeproc`

pandoc-citeproc는 `[@key]` 형식을 BibTeX entry 기반으로 inline 텍스트로 렌더링한다 (예: "Smith and Jones (2024)"). 그러나:

- gist-preprint는 `natbib authoryear,round` 사용 — `\citep{key}`가 자체 포맷 처리
- citation_resolver가 이미 Author(Year) → `\citep{key}` 치환을 마쳤음
- citeproc가 다시 돌면 `\citep{...}`이 verbatim text로 처리되어 깨짐

따라서 `--citeproc`를 절대 켜지 않는다. (pandoc default도 off지만 명시적으로 안 줌으로써 보장.)

### (의도적으로 끄는) `--toc`, `--number-sections`

fragment는 main.tex 안에 inline되므로 자체 TOC 불필요. main.tex가 `\tableofcontents`를 호출.

## per-injection 추가 플래그 사용 예

manifest에서:

```yaml
injections:
  design/v3/06_measurement_framework:
    pandoc_extra_flags:
      - "--top-level-division=subsection"
      - "--shift-heading-level-by=2"
      - "-V"
      - "tables=tabularx"   # 매우 넓은 통계 테이블에만
```

CLI에서 (전역 적용은 비권장):

```bash
md_inject_convert.py --plan plan.json -- --no-highlight  # already default
```

## 디버깅 — pandoc 단독 실행

skill 외부에서 직접 검증하려면:

```bash
pandoc --from gfm+tex_math_dollars+raw_tex+fenced_code_attributes+pipe_tables \
       --to latex --no-highlight --wrap=none --listings \
       --top-level-division=subsection --shift-heading-level-by=1 \
       sample-section.md > out.tex
xelatex out.tex
```

이 결과의 raw 출력을 보면 후처리 전 형태를 확인할 수 있다 (`\hypertarget`, `\passthrough` 등이 그대로 보임).
