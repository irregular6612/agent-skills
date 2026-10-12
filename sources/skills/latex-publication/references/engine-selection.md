# 엔진 선택

이 스킬은 엔진을 추측하지 않는다. **프로젝트가 정한 값을 따르고, 없으면 묻는다.**

## 왜 고정값을 두지 않는가

한동안 이 스킬은 `xelatex + TeX Live 2025`에 하드코딩돼 있었다. 실제 원고를
대조해보니 그 전제가 틀렸다 — Overleaf 프로젝트가 `pdfLaTeX`로 빌드되고 있었고,
같은 소스가 XeLaTeX에서 9페이지, pdfLaTeX에서 8페이지로 갈렸다.

프로젝트마다 다르고, 같은 프로젝트도 시간에 따라 바뀐다. 그래서 값을 코드가
아니라 프로젝트가 들고 있게 했다.

## 해석 순서

| 순서 | 출처 | 범위 |
|---|---|---|
| 1 | `--engine=` / `--texlive=` | 이번 실행만 |
| 2 | `<프로젝트>/CLAUDE.md`, 없으면 `AGENTS.md` | 그 프로젝트 |
| 3 | 없음 → exit 4 | 사용자에게 묻는다 |

`main.tex` 디렉토리에서 시작해 위로 올라가며 설정 파일을 찾는다. `$HOME` 또는
`/`에서 멈춘다. 저장소 루트에 두면 하위 디렉토리의 `.tex`도 같은 설정을 쓴다.

## 프로젝트에 적는 법

프로젝트 `CLAUDE.md`에 두 줄:

```markdown
latex-engine: xelatex
latex-texlive: 2025
```

목록 마커(`- `)나 대문자, 뒤에 붙은 `# 주석`도 허용한다.
**둘 다 있어야 한다.** 하나만 있으면 exit 3으로 거부한다 — 나머지를 임의로
채우면 어느 조합으로 만든 PDF인지 알 수 없어진다.

붙여넣을 스니펫: `templates/claude-md-snippet.md`

## 쓸 수 있는 조합 확인

```bash
bash scripts/texlive_env.sh --list
# 또는
bash scripts/compile.sh --list-engines
```

설치된 TeX Live를 전부 훑어 연도 × 엔진 조합을 낸다. 훑는 곳:
`$TEXLIVE_BIN_DIR` → `~/texlive/*/bin/*/` → `/usr/local/texlive/*/bin/*/` →
`/Library/TeX/texbin/`. 심볼릭 링크로 같은 배포판이 두 번 잡히는 것은 걸러낸다.

연도는 디렉토리 이름이 아니라 **엔진이 스스로 보고하는 값**(`--version`)으로
판정한다. 경로 이름과 실제 배포판이 다른 경우를 잡기 위해서다.

## Overleaf 값 읽어오기

Overleaf 프로젝트 메뉴 → Settings → Compiler 에서 두 값을 읽어 그대로 적는다.
**Overleaf 기본값은 pdfLaTeX다.** XeLaTeX로 바꾼 적이 없으면 pdfLaTeX다.

이미 빌드된 PDF가 있으면 거기서도 읽을 수 있다:

```bash
pdfinfo dist/main.pdf | grep -i producer
#   pdfTeX, Version ... (TeX Live 2025)   → pdflatex
#   XeTeX version 0.999998                → xelatex
#   LuaTeX ...                            → lualatex
```

`Creator` 줄의 `hyperref` 날짜로 TeX Live 스냅샷 시점까지 가늠할 수 있다.

## exit code

| exit | 뜻 | 대응 |
|---|---|---|
| 2 | 요청한 엔진·연도가 이 머신에 없음 | 해당 TeX Live 설치 (`overleaf-parity.md`) |
| 3 | 설정이 반쪽 | 빠진 줄을 채운다 |
| 4 | 설정 없음 | **사용자에게 묻는다.** 기본값을 고르지 말 것 |

exit 4는 실패가 아니라 질문 요청이다. `--list`로 조합을 뽑아 `AskUserQuestion`으로
제시하고, 답을 프로젝트 `CLAUDE.md`에 적어 다음부터 다시 묻지 않게 한다.

## magic comment와의 관계

`.tex` 첫 줄의 `% !TEX program = ...`은 **엔진을 고르지 않는다.** 해석된 엔진과
다르면 `compile.sh`가 exit 2로 거부한다. Overleaf는 magic comment를 무시하지만
로컬 에디터는 이걸 보고 다른 엔진을 띄우므로, 둘이 어긋나면 로컬과 Overleaf가
갈라진다. 그래서 조용히 넘기지 않고 멈춘다.
