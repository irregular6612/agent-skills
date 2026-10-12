<!--
  latex-publication 스킬이 읽는 두 줄.
  프로젝트 CLAUDE.md (없으면 AGENTS.md) 아무 데나 넣으면 된다.
  main.tex 디렉토리부터 위로 올라가며 찾으므로, 저장소 루트에 두면 하위
  디렉토리의 .tex 도 같은 설정을 쓴다.

  값은 Overleaf 프로젝트 Settings → Compiler 에서 읽은 것과 일치시킨다.
  쓸 수 있는 조합:  bash scripts/texlive_env.sh --list
-->

## LaTeX 빌드 설정

latex-engine: xelatex
latex-texlive: 2025

<!--
  latex-engine   pdflatex | latex | xelatex | lualatex
                 Overleaf Compiler 설정과 같은 값. Overleaf 기본값은 pdfLaTeX.
  latex-texlive  Overleaf Settings → Compiler 의 TeX Live 연도.

  둘 다 있어야 한다. 하나만 있으면 compile.sh 가 exit 3 으로 거부한다 —
  나머지 하나를 임의로 채우면 어느 조합으로 만든 PDF인지 알 수 없어진다.
-->
