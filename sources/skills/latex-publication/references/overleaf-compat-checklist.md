# Overleaf Round-trip Compatibility Checklist

Cursor에서 로컬 작업한 LaTeX 프로젝트를 Overleaf로 다시 올렸을 때 깨지지 않도록 검증할 항목들.

## 핵심 원칙

> **Overleaf는 Linux + TeX Live 풀 설치 + 제한된 폰트셋을 가진 격리된 빌드 환경이다.**
> 로컬 머신에만 있는 것에 의존하면 무조건 깨진다.

> **Overleaf 프로젝트 설정이 진실의 원천이다. 로컬이 그것을 따라간다.**
> Compiler·TeX Live는 프로젝트에서 읽은 값이다. XeLaTeX/2025는 예시이지 공통 고정값이 아니다.
> 컴파일 명령과 재현 잔차는 `overleaf-parity.md`. 이 문서는 파일·폰트 이식성만 다룬다.

## 업로드 전 체크리스트

### 1. Source 파일

- [ ] **Magic comment**: 메인 `.tex`의 `% !TEX program`이 선택한 프로젝트 engine과 일치
- [ ] **`korean-patch.sty`** 가 git에 staged (다른 사람이 받아도 같이 따라감)
- [ ] **`latexmkrc`** 는 엔진을 정하지 않는다. 엔진은 Overleaf Settings와
      프로젝트 `CLAUDE.md`가 정한다 (`engine-selection.md`).
      latexmk는 rc 파일보다 커맨드라인을 우선하므로 `$pdf_mode`를 써도 무시된다.
      이 파일에는 biber 전환 같은 엔진 무관 설정만 둔다.
- [ ] **시스템 절대경로 0건**: `grep -r "/Users/\|/home/" *.tex *.sty *.bib`
- [ ] **상대경로만**: `\graphicspath{{./figures/}}` 같은 상대경로만 사용
- [ ] **파일명에 공백 없음**: Overleaf는 공백 파일명을 안전하게 처리하지만 일부 패키지가 깨짐

### 2. 한글 패키지 선택

| 사용 중인 패키지 | Overleaf 호환성 | 추가 조치 |
|---|---|---|
| `kotex` | ✅ 100% portable | 없음 |
| `xeCJK` + `Noto Sans CJK KR` | ⚠️ Noto는 있지만 명시 필요 | 폰트명 정확히 (`Noto Sans CJK KR`) |
| `xeCJK` + `Apple SD Gothic Neo` | ❌ macOS 전용 폰트 | 다른 폰트로 교체 필수 |
| `ucharclasses` + system font | ⚠️ 폰트 없으면 깨짐 | Noto 같은 cross-platform 폰트로 |
| `CJK` (legacy) | ⚠️ 작동하나 비권장 | `kotex`으로 마이그레이션 |

### 3. .gitignore 확인

git push 전에 다음 파일들이 untracked인지:

- [ ] `.vscode/settings.json` (LaTeX Workshop 로컬 설정)
- [ ] `.cursor/settings.json`
- [ ] `build/` 디렉토리 (xelatex 출력)
- [ ] `*.aux`, `*.log`, `*.fls`, `*.fdb_latexmk`, `*.synctex.gz`
- [ ] `.DS_Store` (macOS noise)

> **왜?** Overleaf는 `.vscode/settings.json`을 무시하지만, 협업자에게는 노이즈. `*.aux` 같은 build artifact는 Overleaf가 자체 생성하므로 충돌 가능.

### 4. BibTeX vs Biber

`.bib` 파일에 한글이 있다면:

- [ ] `\usepackage[backend=biber]{biblatex}` 사용
- [ ] Overleaf 프로젝트 Settings → Compiler에서 Biber 선택 (또는 latexmkrc에 `$bibtex = 'biber'`)
- [ ] 일반 `\usepackage{natbib}` + `bibtex`는 한글 저자명에서 깨짐

## Overleaf 업로드 후 검증 단계

### Step 1: Compiler 설정 확인 (읽기만, 바꾸지 않는다)

Overleaf 프로젝트 메뉴 → **Settings** → **Compiler**에서 값을 읽고,
그 값을 프로젝트 `CLAUDE.md`에 적는다:

| Overleaf에서 읽을 값 | `CLAUDE.md`에 적을 것 |
|---|---|
| Compiler (예: XeLaTeX) | `latex-engine: xelatex` |
| TeX Live (예: 2025) | `latex-texlive: 2025` |
| Main document | `compile.sh <그 파일>` |

> Overleaf 기본값은 **pdfLaTeX**다. XeLaTeX로 바꾼 적이 없으면 pdfLaTeX다.
> 이미 빌드된 PDF가 있으면 `pdfinfo <pdf> | grep -i producer` 로도 확인된다.
> 상세는 `engine-selection.md`.

> Magic comment(`% !TEX program`)는 Overleaf에서 **무시된다.** Overleaf는
> 프로젝트 Compiler 설정만 본다. magic comment는 로컬 에디터용이다.

### Step 2: 첫 빌드

- 기대: 한글 페이지 정상 렌더링, log에 한글 관련 경고 없음
- 실패 시 흔한 에러:
  - `! LaTeX Error: File 'kotex.sty' not found` → 선택된 배포판의 kotex 설치를 확인. 엔진을 임의 변경하지 않는다.
  - `! Package fontspec Error: The font 'Noto Sans CJK KR' cannot be found` → 폰트명 오타 또는 Noto 패키지 누락. `Noto Sans KR`로 시도.
  - `! Missing character: There is no [한] in font ...` → 패키지 로드 순서 문제. `\usepackage{korean-patch}`를 다른 폰트 패키지보다 **뒤에** 두기.

### Step 3: 협업자 view 검증

- 동료/리뷰어가 같은 프로젝트를 열어도 똑같이 빌드되는지
- "내 컴퓨터에서만 됨" 방지 — Overleaf에서 빌드되면 portable 보증

## 로컬 ↔ Overleaf 동기화 워크플로우

### Overleaf → 로컬

```bash
# Overleaf 프로젝트 메뉴 → Menu → Source → Download
unzip overleaf-project.zip -d project/
cd project/

# Skill 적용
python ${SKILL_ROOT}/scripts/diagnose.py .
# 진단 결과 보고 Phase 3-4 적용
```

### 로컬 → Overleaf

#### 옵션 A: zip 업로드 (간단, 협업 어려움)
```bash
# .gitignore 패턴을 활용해 build 산출물 제외
zip -r project.zip . -x '@.gitignore'
# Overleaf → New Project → Upload Project
```

#### 옵션 B: Git Bridge (Overleaf 유료) — 권장
- Overleaf 프로젝트 Menu → Sync → Git
- `git remote add overleaf https://git.overleaf.com/<id>`
- `git push overleaf master`
- `.gitignore`가 자동으로 적용되므로 build 산출물 안 올라감

#### 옵션 C: GitHub 연동 (Overleaf Premium)
- Overleaf가 GitHub repo에서 양방향 sync
- 가장 협업 친화적

## 흔한 실수

| 실수 | 결과 | 해결 |
|---|---|---|
| `.vscode/`를 commit | Overleaf에서는 무시되나 협업자가 혼란 | `.gitignore`에 추가 |
| 시스템 폰트 (`Apple SD Gothic Neo`) 사용 | Overleaf 빌드 실패 | `Noto Sans CJK KR`로 교체 |
| 선택 engine과 패키지 불일치 | 한글 깨짐 | 프로젝트 engine에 호환되는 패키지를 준비 (engine 변경은 사용자 결정) |
| `latexmkrc`로 엔진을 바꾸려 함 | 커맨드라인이 이겨서 무시됨 | 엔진은 Overleaf Settings가 결정. `overleaf-parity.md` |
| 로컬 TeX Live 연도 ≠ Overleaf | 줄바꿈·페이지 번호 어긋남 | 프로젝트에서 읽은 TeX Live 연도를 일치시킨다 |
| 절대경로 `\input{/Users/.../foo.tex}` | Overleaf에서 file not found | 상대경로로 |
| 빌드 산출물(`*.pdf`)을 git에 commit | Overleaf 빌드와 충돌 | `.gitignore`에 `*.pdf` (단 원본 figure PDF는 제외) |
