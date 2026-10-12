# Korean LaTeX Package Comparison

LaTeX에서 한글을 렌더링하는 4가지 주요 방식의 비교. **default는 `kotex`** (Overleaf 호환성 최우선).

## 한 줄 요약

| 패키지 | 한 줄 정의 | 추천 시나리오 |
|---|---|---|
| **`kotex`** | TeX Live 표준 한국어 패키지, 폰트 자동 번들 | 기본값. Overleaf 호환성 우선. |
| `xeCJK` | XeLaTeX용 일반 CJK 패키지, 시스템 폰트 자유 선택 | 시각적 통일 (Noto/Pretendard 등) 원할 때 |
| `ucharclasses` | Unicode block 단위로 폰트 전환 트리거 | xeCJK 대안 (ctexhook 충돌 회피용) |
| `CJK` (legacy) | pdfLaTeX에서도 작동하는 구식 CJK | 호환성 외 권장 안 함 |

## 상세 비교

### 1. `kotex`

**장점**:
- TeX Live에 기본 포함 → 어떤 환경에서든 동일하게 작동 (Overleaf, MacTeX, Linux TeX Live, MiKTeX)
- Nanum Myeongjo/Gothic 폰트가 자동 번들 → 시스템에 한글 폰트 없어도 OK
- 엔진 자동 fallback: XeLaTeX → `xetexko`, LuaLaTeX → `luatexko`, pdfLaTeX → `klatex` (제한적)
- 한국 출판/논문 표준
- 한 줄로 끝: `\usepackage[hangul]{kotex}`

**단점**:
- 기본 폰트(Nanum Myeongjo)가 일부 사용자에게 너무 평범하게 느껴짐
- 폰트 변경하려면 `\setmainhangulfont{...}` 같은 추가 명령 필요

**언제?**
- Overleaf로 다시 올릴 가능성이 있을 때
- 협업자의 환경을 통제할 수 없을 때
- 빠르게 한글만 되게 하면 충분할 때

**Preamble 예시**:
```latex
\documentclass{article}
\usepackage[hangul]{kotex}        % 한 줄로 끝
% 또는 폰트 커스터마이즈:
% \usepackage[hangul]{kotex}
% \setmainhangulfont{Noto Serif CJK KR}
% \setsanshangulfont{Noto Sans CJK KR}
```

### 2. `xeCJK`

**장점**:
- 시스템에 설치된 어떤 폰트든 직접 지정 가능
- CJK (Chinese/Japanese/Korean) 혼용 텍스트에 가장 유연
- 한·중·일 폰트를 각각 다르게 줄 수 있음
- 디자인 customization 자유도 최고

**단점**:
- 시스템 폰트 의존 → portable하지 않음 (Overleaf로 옮길 때 폰트 누락 위험)
- 일부 폰트(예: Apple-only)는 macOS 외에서 빌드 실패
- `fontspec` 의존 → XeLaTeX/LuaLaTeX 전용 (pdfLaTeX 불가)

**언제?**
- 시각적으로 특정 폰트(Noto, Pretendard, Apple SD Gothic Neo 등)를 꼭 써야 할 때
- 본문 한자/일본어 혼용
- 로컬에서만 빌드하고 Overleaf 배포 안 함

**Preamble 예시**:
```latex
\documentclass{article}
\usepackage{fontspec}
\usepackage{xeCJK}
\setCJKmainfont{Noto Sans CJK KR}     % macOS+Overleaf 둘 다 안전
\setCJKsansfont{Noto Sans CJK KR}
\setCJKmonofont{Noto Sans Mono CJK KR}
\xeCJKsetup{CJKecglue={}}             % CJK-Latin 사이 자동 공백 끄기
```

**Overleaf에서 사용 가능한 한글 폰트**:
- `Noto Sans CJK KR` ✅ (default 권장)
- `Noto Serif CJK KR` ✅
- `Source Han Sans KR` ✅
- `Nanum Myeongjo`, `Nanum Gothic` ✅
- `Apple SD Gothic Neo` ❌ (macOS 전용)
- `Pretendard` ❌ (별도 폰트 업로드 필요)

### 3. `ucharclasses`

**장점**:
- `xeCJK`보다 가벼움 (의존성 적음)
- `xeCJK`가 요구하는 `ctexhook.sty`가 일부 TeX Live 배포판에 누락된 상황 회피
- Unicode block별로 다른 폰트 전환 가능

**단점**:
- xeCJK보다 설정 복잡 (`\setTransitionsForCJK` 같은 추가 명령)
- 한글 organization-specific 기능(예: 한자 보조 등) 부족

**언제?**
- `xeCJK`가 ctexhook 누락으로 빌드 실패할 때
- 다국어 (예: 한국어 + 베트남어 + 그리스어) 혼용 시

**Preamble 예시**:
```latex
\documentclass{article}
\usepackage{fontspec}
\usepackage{ucharclasses}
\setmainfont{Noto Sans CJK KR}
\newfontfamily\hangulfont{Noto Sans CJK KR}
\setTransitionsForCJK{\hangulfont}{}{}
```

> 연혁: 통합 전 `academic-latex-pipeline` 스킬이 이 방식을 썼다. MD→PDF 빌드 환경에서 ctexhook 충돌 회피가 중요했기 때문. 해당 스킬은 이 스킬로 흡수돼 더 이상 존재하지 않는다 — 현재 구현은 `scripts/md2tex/modes/build_legacy.py`.

### 4. `CJK` (legacy)

**장점**:
- pdfLaTeX에서도 작동 (구식 환경 호환)

**단점**:
- 입력 인코딩이 까다로움 (UTF-8 fallback 별도 처리)
- 폰트 매핑 수동 설정
- 신규 프로젝트에서는 비권장
- 한국에서는 거의 안 씀

**언제?**
- 절대 pdfLaTeX만 써야 하는 legacy 환경

**Preamble 예시 (참고용, 권장 안 함)**:
```latex
\documentclass{article}
\usepackage{CJKutf8}
\AtBeginDocument{\begin{CJK}{UTF8}{mj}}
\AtEndDocument{\clearpage\end{CJK}}
```

## 의사결정 트리

```
한글이 필요한가?
├─ Overleaf로 라운드트립할 가능성 있나?
│  └─ YES → kotex (이 skill의 default)
│  └─ NO  → 다음 질문
├─ 특정 폰트(Noto, Pretendard 등)를 꼭 써야 하나?
│  └─ YES → xeCJK + 해당 폰트
│  └─ NO  → kotex
├─ xeCJK가 ctexhook 누락으로 깨지나?
│  └─ YES → ucharclasses
│  └─ NO  → xeCJK 또는 kotex
└─ pdfLaTeX만 써야 하는 환경인가?
   └─ YES → CJK (마지막 수단)
```

## 패키지 충돌 주의

- **`kotex` + `xeCJK` 동시 사용 금지**: 한글 폰트 처리가 두 군데서 일어나 충돌
- **`kotex` + `inputenc[utf8]`**: 작동하나 불필요. kotex이 자체 처리
- **`xeCJK` 로드 순서**: `fontspec` 다음, 본문 폰트 설정 전에 로드
- **`hyperref` + 한글**: 한글 북마크가 깨질 수 있음 → `\usepackage[unicode]{hyperref}` 사용

## 이 skill의 default 결정

이 skill이 `kotex`을 default로 채택한 이유 (Plan Decision 1):

1. **Overleaf 라운드트립이 사용자의 명시적 요구사항**
2. `kotex`은 시스템 폰트 의존이 0 → 어떤 환경에서도 동일
3. TeX Live에 번들되어 추가 설치 불필요
4. 한 줄로 끝나서 `korean-patch.sty` 파일이 단순해짐 → 유지보수 비용 최소

`xeCJK`가 필요한 경우 `templates/korean-patch-xecjk.sty`를 대신 사용.
