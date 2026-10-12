# /latex:setup — 한글 LaTeX 환경 셋업

기존 LaTeX 프로젝트의 한글 렌더링과 로컬/Overleaf 설정을 맞춘다. 기존 `.sty`는 직접 고치지 않고 wrapper와 sentinel로 패치한다. MD 독립 PDF는 `:build`, 기존 템플릿 주입은 `:inject`로 분리한다.

## 1. 프로젝트 엔진 확인 (read-only)

`SKILL.md`와 `references/engine-selection.md`가 단일 계약이다. `compile.sh --engine= --texlive=` override 또는 프로젝트 `CLAUDE.md`/`AGENTS.md`의 `latex-engine:`·`latex-texlive:` 두 값을 사용한다. 값이 없으면 exit 4이며 빌드하지 않고 사용자에게 확인한다. 한 값만 있으면 exit 3이다.

Overleaf가 원본이면 Settings의 Compiler·TeX Live·Main document를 읽는다. 기존 engine을 임의로 XeLaTeX로 바꾸지 않는다. `% !TEX program`은 로컬 에디터용이고 Overleaf 설정을 대체하지 않는다.

```bash
python3 "${SKILL_ROOT}/scripts/diagnose.py" <project_dir>
```

진단은 preamble·한글 패키지·폰트·bibliography·Missing character 로그·절대경로를 검사한다. 설치나 프로젝트 수정 전에 실제 선택된 engine/TeX Live와 결과를 확인한다.

## 2. 비파괴 패치 계획

- `kotex`가 설치되어 있으면 해당 프로젝트 엔진과 호환되는 `korean-patch.sty`를 사용한다.
- `xeCJK` 패치는 XeLaTeX 전용이다. 다른 엔진에 넣지 않는다.
- legacy `ucharclasses` preamble은 기존 프로젝트 호환용이다. 새 다중 엔진 지원이라고 주장하지 않는다.
- 시스템 전용 폰트 대신 협업 환경에 실제 있는 폰트를 선택한다. 임의 설치나 유료 작업은 별도 승인 없이 하지 않는다.
- `templates/latexmkrc`는 엔진을 강제하지 않는다. 사용자 설정을 덮어쓰지 않고 필요한 엔진 무관 항목만 병합한다.

## 3. 승인한 패치 적용

1. 로컬 magic comment를 선택된 engine과 맞춘다.
2. `\documentclass` 뒤에 호환되는 `\usepackage{korean-patch}`를 추가한다.
3. wrapper 파일을 프로젝트에 복사한다. 기존 사용자 파일은 백업한다.
4. IDE 설정은 프로젝트 설정으로 생성한다:

```bash
bash "${SKILL_ROOT}/scripts/gen_vscode_settings.sh" <project_dir>
```

`.vscode/`, `build/`, `.build/`와 임시 빌드 파일은 `templates/gitignore`를 참고해 제외한다.

## 4. 검증

```bash
bash "${SKILL_ROOT}/scripts/compile.sh" <project_dir/main.tex>
```

성공 뒤 PDF의 한글 렌더링·텍스트 추출·citation·Missing character·시스템 절대경로를 확인한다. Overleaf의 실제 설정과 같은 환경에서 재현했는지 보고한다. 미실행이면 미검증으로 남긴다.

`verify_build.sh`는 스킬 자체의 XeLaTeX/2025 회귀 fixture다. 프로젝트의 engine 선택을 대신하지 않는다. `korean-patch-ucharclasses.sty` 배포 template은 없으며 legacy preamble을 자동 복사하지 않는다.

## 5. 전달

프로젝트 engine/TeX Live, 변경한 파일과 백업, 실제 명령·exit code, 남은 폰트/Overleaf 한계를 기록한다. `:push`는 별도 승인과 작업 범위가 있을 때만 실행한다.
