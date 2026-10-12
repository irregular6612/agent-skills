# Overleaf Parity — 로컬에서 Overleaf와 같은 PDF 얻기

이 스킬의 **컴파일 기준(single source of truth)** 문서.
목표: Overleaf 웹 설정을 바꾸지 않고, 로컬 Mac이 Overleaf를 따라간다.

## 추측하지 않는다

엔진과 TeX Live 연도는 **프로젝트가 정한다.** `<프로젝트>/CLAUDE.md`의
`latex-engine:` / `latex-texlive:` 두 줄이고, 없으면 빌드하지 않고 묻는다.
상세는 `engine-selection.md`.

프로젝트마다 다른 값을 뺀 나머지는 Overleaf CLSI 고정값을 그대로 쓴다.

| 항목 | 값 | 출처 |
|---|---|---|
| Compiler | 프로젝트 설정 | `CLAUDE.md` 또는 `--engine=` |
| TeX Live | 프로젝트 설정 | `CLAUDE.md` 또는 `--texlive=` |
| jobname | `output` | Overleaf CLSI 고정값 |
| interaction | `batchmode` | Overleaf CLSI 고정값 |

조건이 안 맞을 때 다른 조합으로 대신 빌드하는 fallback은 없다.

| 상황 | 결과 |
|---|---|
| 요청한 엔진·연도가 이 머신에 없음 | exit 2 |
| 설정이 반쪽 | exit 3 |
| 설정이 아예 없음 | exit 4 — 사용자에게 묻는다 |
| 찾은 엔진의 `--version`이 요청한 연도가 아님 | exit 2 |
| `.tex`의 magic comment가 해석된 엔진과 다름 | exit 2 |

해석은 `scripts/texlive_env.sh` 한 곳이 담당하고,
`compile.sh`·`verify_build.sh`·`diagnose.py`가 전부 이 파일을 통해 같은 배포판을 본다.

## Overleaf가 실제로 실행하는 명령

`overleaf/overleaf` → `services/clsi/app/js/LatexRunner.js` (main):

```
latexmk -cd -jobname=output -auxdir=$COMPILE_DIR -outdir=$COMPILE_DIR \
        -synctex=1 -interaction=batchmode -time <engineflag> main.tex
```

엔진 플래그 매핑 (CLSI 원본 그대로):

| Overleaf Compiler 설정 | latexmk 플래그 |
|---|---|
| pdfLaTeX (Overleaf 기본값) | `-pdf` |
| LaTeX | `-pdfdvi` |
| **XeLaTeX** | `-xelatex` |
| LuaLaTeX | `-lualatex` |

> `compile.sh`는 프로젝트가 정한 엔진을 이 표대로 latexmk 플래그에 옮긴다.
> Overleaf Compiler 설정과 `latex-engine:` 값을 같게 맞추는 것이 parity의 전제다.

> 구버전 CLSI에는 `-f`(에러 무시하고 계속)가 있었으나 현행 main에는 없다.
> 그래서 `compile.sh`도 기본적으로 `-f`를 넣지 않는다 (`--force`로 켤 수 있음).

`-xelatex`는 `-pdfxe`와 같다. latexmk가 `xelatex`으로 `.xdv`를 만들고
`xdvipdfmx`로 PDF를 만든다 — 2단계. `xelatex main.tex`를 직접 부르는 것과
드라이버는 같지만 의존성 추적과 반복 횟수 판단이 다르다.

## 로컬 명령

```bash
bash ~/.claude/skills/latex-publication/scripts/compile.sh main.tex
```

빌드 경로는 이것 하나다. 컨테이너로 우회하는 경로는 없다.

## TeX Live 2025 설치

시스템 기본은 MacTeX 2026이다. Overleaf는 2025이므로, 이 연도 차이가
잔차의 최대 지분이다. TL2025를 나란히 깔아 `compile.sh`가 그것만 쓰게 한다. (sudo 불필요)

기존 MacTeX 2026을 지우지 않고 홈 디렉토리에 나란히 깐다.
Apple Silicon 네이티브(`universal-darwin` 바이너리)라 빠르다.

```bash
# 1. 설치 프로그램 받기
#    주의: ftp.tug.org 는 인증서가 호스트명과 안 맞아 curl이 거부한다 (SSL error 60).
#    Utah 미러를 쓴다.
M=https://ftp.math.utah.edu/pub/tex/historic/systems/texlive/2025
cd /tmp && curl -sS -O "$M/install-tl-unx.tar.gz" && tar xzf install-tl-unx.tar.gz

# 2. 프로파일 작성 (비대화식 설치)
cat > /tmp/tl2025-profile.txt <<'EOF'
selected_scheme scheme-full
TEXDIR ~/texlive/2025
TEXMFLOCAL ~/texlive/texmf-local
TEXMFSYSCONFIG ~/texlive/2025/texmf-config
TEXMFSYSVAR ~/texlive/2025/texmf-var
TEXMFCONFIG ~/.texlive2025/texmf-config
TEXMFHOME ~/texmf
TEXMFVAR ~/.texlive2025/texmf-var
binary_universal-darwin 1
instopt_adjustpath 0
instopt_adjustrepo 0
tlpdbopt_autobackup 0
tlpdbopt_install_docfiles 0
tlpdbopt_install_srcfiles 0
EOF

# 3. 설치 (30~60분)
cd /tmp/install-tl-* && perl ./install-tl \
  -profile /tmp/tl2025-profile.txt \
  -repository "$M/tlnet-final"
```

프로파일 값의 뜻:

| 키 | 이유 |
|---|---|
| `selected_scheme scheme-full` | Overleaf의 texlive-full과 같은 범위. 패키지 누락으로 로컬만 실패하는 일 방지 |
| `TEXDIR ~/texlive/2025` | `/usr/local` 대신 홈 → **sudo 불필요**, 지우기도 `rm -rf` 한 번 |
| `instopt_adjustpath 0` | PATH를 건드리지 않는다. MacTeX 2026이 계속 기본으로 남는다 |
| `tlpdbopt_install_docfiles 0`<br>`tlpdbopt_install_srcfiles 0` | 문서·소스 제외. 조판 결과에 **영향 없고** 용량이 절반 이하로 준다 |

`compile.sh`가 다음 순서로 **자동 감지**한다 — PATH를 손댈 필요 없다:

1. `$TEXLIVE_BIN_DIR` 환경변수
2. `~/texlive/2025/bin/<arch>/`
3. `/usr/local/texlive/2025/bin/<arch>/`

제거는 `rm -rf ~/texlive/2025 ~/.texlive2025`.

#### 이 머신의 설치 상태 (2026-09-01 기준)

| | |
|---|---|
| 경로 | `~/texlive/2025/bin/universal-darwin` |
| 크기 | 4.4G (doc/src 제외, scheme-full) |
| XeTeX | `3.141592653-2.6-0.999997 (TeX Live 2025)` |
| latexmk | 4.87 (2025-06-15) |
| 시스템 기본 | MacTeX **2026** 그대로 (XeTeX 0.999998, latexmk 4.88) |

`compile.sh`는 TL2025를 자동으로 집어 쓴다. 다른 도구(`/Library/TeX/texbin`)는
여전히 2026을 쓰므로, 두 연도가 한 머신에 공존한다.

> latexmk 버전까지 2025 쪽(4.87)으로 맞춰진다. Overleaf TL2025 이미지가 쓰는 것과
> 같은 계열이라, 반복 횟수 판정 로직 차이까지 사라진다.


산출물은 `output.pdf`. Overleaf와 같은 이름이다.
`main.pdf`가 필요하면 `--jobname=main` — 단 그만큼 parity가 깨진다.

## 맞춰지는 것 / 못 맞추는 것

### 맞춰짐
- latexmk 인자 전부 (`-cd -jobname -auxdir -outdir -synctex=1 -interaction=batchmode -time`)
- 엔진 플래그 (`-xelatex`)
- 패스 횟수 — latexmk가 수렴할 때까지 반복. 고정 3-pass 아님
- bibtex/biber 실행 여부 판정 — latexmk에 위임
- TeX Live 연도 (TL2025 설치 후)

### 못 맞춤 (알고 있어야 하는 잔차)
1. **OS와 폰트 환경.**
   Overleaf는 Linux에서, 여기는 macOS에서 돈다. TeX Live 연도가 같아도
   시스템 폰트 목록이 다르므로, macOS 전용 폰트(`Apple SD Gothic Neo` 등)에
   의존하는 문서는 로컬에서만 빌드된다. `references/overleaf-compat-checklist.md`의
   폰트 항목으로 걸러낼 것.
   (overleaf.com이 쓰는 `quay.io/sharelatex/texlive-full` 이미지는 인증이
   걸려 있어 일반 계정으로는 받을 수 없다. 이 잔차는 없앨 방법이 없다.)
2. **Overleaf 시스템 latexmk 설정 파일** `/usr/local/share/latexmk/LatexMk`의
   내용은 공개돼 있지 않다. 여기서 뭔가를 설정한다면 재현 불가.
3. **로컬 native 모드는 TeX Live 2026**이라 패키지 버전이 다르다.
   줄바꿈·페이지 번호가 어긋날 수 있는 가장 큰 원인.
4. **PDF 바이트 동일성**은 별개 문제. 생성 시각과 PDF ID가 매번 다르다.
   바이트까지 비교하려면:
   ```bash
   SOURCE_DATE_EPOCH=0 FORCE_SOURCE_DATE=1 bash compile.sh main.tex
   ```

## latexmkrc 우선순위 — 흔한 오해

latexmk는 rc 파일을 먼저 읽고 **커맨드라인 옵션을 나중에 적용한다. 커맨드라인이 이긴다.**

즉 `latexmkrc`에 `$pdf_mode = 5`(xelatex)를 써도, Overleaf 프로젝트 Compiler가
pdfLaTeX이면 `-pdf`가 넘어와 그 값을 덮어쓴다.

> 구버전 `templates/latexmkrc`는 `$pdflatex = 'xelatex ...'`로
> "pdflatex 자리에 xelatex 바이너리"를 끼워 넣어 이를 우회했다.
> 한글은 나오지만 mode는 pdflatex인 채라 latexmk의 의존성 추적이 어긋난다.
> 현재 템플릿에서 제거했다. 엔진은 Overleaf 프로젝트 설정을 진실의 원천으로 둔다.

Overleaf 문서가 보장하는 것은 두 가지뿐이다:
`latexmkrc`는 **프로젝트 루트**에 있어야 하고,
Overleaf 시스템 설정 파일 **뒤에** 읽힌다.

## 출처
- https://raw.githubusercontent.com/overleaf/overleaf/main/services/clsi/app/js/LatexRunner.js
- https://docs.overleaf.com/getting-started/recompiling-your-project/selecting-a-tex-live-version-and-latex-compiler
- https://docs.overleaf.com/managing-projects-and-files/the-latexmkrc-file
- https://docs.overleaf.com/on-premises/configuration/overleaf-toolkit/server-pro-only-configuration/sandboxed-compiles
