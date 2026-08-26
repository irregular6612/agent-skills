# Overleaf Round-trip Compatibility Checklist

Cursor에서 로컬 작업한 LaTeX 프로젝트를 Overleaf로 다시 올렸을 때 깨지지 않도록 검증할 항목들.

## 핵심 원칙

> **Overleaf는 Linux + TeX Live 풀 설치 + 제한된 폰트셋을 가진 격리된 빌드 환경이다.**
> 로컬 머신에만 있는 것에 의존하면 무조건 깨진다.

## 업로드 전 체크리스트

### 1. Source 파일

- [ ] **Magic comment**: 메인 `.tex` 첫 줄에 `% !TEX program = xelatex` 있음
- [ ] **`korean-patch.sty`** 가 git에 staged (다른 사람이 받아도 같이 따라감)
- [ ] **`latexmkrc`** 가 git에 staged (Overleaf가 자동 인식해서 xelatex 사용)
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

### Step 1: Compiler 설정 확인

Overleaf 프로젝트 메뉴 → **Settings** → **Compiler**:
- ☑️ XeLaTeX (Magic comment가 있어도 명시적으로 선택해두면 안전)
- ☑️ Main document: 정확히 메인 `.tex` 파일

### Step 2: 첫 빌드

- 기대: 한글 페이지 정상 렌더링, log에 한글 관련 경고 없음
- 실패 시 흔한 에러:
  - `! LaTeX Error: File 'kotex.sty' not found` → Compiler가 pdfLaTeX임. XeLaTeX로 변경.
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
python ~/.claude/skills/latex-korean-setup/scripts/diagnose.py .
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
| `% !TEX program` 누락 | Overleaf가 pdflatex로 빌드 → 한글 깨짐 | magic comment 추가 또는 Overleaf UI에서 XeLaTeX 선택 |
| `latexmkrc` 누락 | Compiler 변경 시마다 수동 설정 | `templates/latexmkrc` 복사 |
| 절대경로 `\input{/Users/.../foo.tex}` | Overleaf에서 file not found | 상대경로로 |
| 빌드 산출물(`*.pdf`)을 git에 commit | Overleaf 빌드와 충돌 | `.gitignore`에 `*.pdf` (단 원본 figure PDF는 제외) |
