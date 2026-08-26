# BibTeX 규칙 — latex-publication 공통

3개 구 스킬(`academic-latex-pipeline`, `latex-korean-setup`, `latex-project-manager`)에 분산돼있던 BibTeX 규칙을 통합한 단일 진실 원천(SSOT).

## 핵심 원칙

| 원칙 | 이유 |
|------|------|
| **inline `\begin{thebibliography}` 금지** | 유지보수 어려움, 자동화 불가, 중복 entry 위험 |
| **BibTeX `.bib` 파일만 사용** | 표준 도구체인 활용 (bibtex, biber, JabRef, Mendeley 등) |
| **모든 텍스트 참조는 `\citep{}` / `\citet{}`** | natbib 스타일 일관성, citation/reference 자동 매칭 |
| **plain text "(Author, Year)" 금지** | undefined citation 위험, 자동 변환 불가 |
| **3-pass 컴파일 표준화** | reference resolution 보장 |

## 파일 구조

```
<project>/
├── refs.bib                    # BibTeX 엔트리만 (per-project)
└── sections/
    └── NN_bibliography.tex     # \bibliographystyle + \bibliography
```

`NN_bibliography.tex` 내용:
```latex
\bibliographystyle{plainnat}
\bibliography{<project>/refs}
```

## Multi-project 공유 가능성

여러 프로젝트가 같은 `refs.bib`을 공유하려면:
- 루트에 `shared/refs.bib` 두고 각 프로젝트가 `\bibliography{shared/refs}` 참조
- 또는 프로젝트별 `refs.bib`을 그대로 두고 중복 entry는 BibTeX이 자동 dedup

## Citation 명령

| 명령 | 출력 | 언제 사용? |
|------|------|----------|
| `\citep{key}` | (Author, Year) | 문장 끝, parenthetical reference |
| `\citet{key}` | Author (Year) | 문장 주체, "Smith (2020) showed..." |
| `\citeauthor{key}` | Author | 저자만 |
| `\citeyear{key}` | Year | 연도만 |
| `\cite{key}` (bare) | 스타일 의존 | **금지** — natbib 환경에서 모호함, `\citep` 또는 `\citet` 명시 |

## 3-pass 컴파일 표준

```bash
# scripts/compile.sh가 자동 처리
pdflatex -interaction=nonstopmode main.tex    # Pass 1: aux 생성
bibtex main                                    # Citation key 해소
pdflatex -interaction=nonstopmode main.tex    # Pass 2: \cite 마크업 적용
pdflatex -interaction=nonstopmode main.tex    # Pass 3: 최종 cross-ref 정착
```

XeLaTeX 사용 시 `pdflatex` 대신 `xelatex`. Engine 선택은 `% !TEX program = xelatex` magic comment 우선.

## Plain text → `\citep` 자동 변환 패턴

`/latex:build`와 `/latex:structure`가 다음 패턴 자동 변환:

| 입력 패턴 | 변환 결과 |
|----------|---------|
| `(Smith, 2020)` | `\citep{smith2020}` (refs.bib에 key 있을 시) |
| `(Smith et al., 2020)` | `\citep{smith2020}` |
| `Smith (2020) showed` | `\citet{smith2020} showed` |
| `Smith & Jones (2020)` | `\citet{smithjones2020}` |
| `[1]`, `[1, 2]` (numeric) | `\citep{key1}`, `\citep{key1,key2}` (manifest 매핑 필요) |

**거짓 매칭 주의**: "4×2 (2026)" 같은 수식 표현이 citation으로 잘못 매칭될 수 있음. `--no-auto-cite` 플래그 또는 수동 검토 필요.

## BibTeX 엔트리 표준 예시

```bibtex
@article{smith2020,
  author = {Smith, John and Jones, Mary},
  title = {Title of Paper},
  journal = {Journal Name},
  year = {2020},
  volume = {15},
  number = {3},
  pages = {123--145},
  doi = {10.xxxx/yyyy}
}

@inproceedings{lee2021,
  author = {Lee, Hyun},
  title = {Conference Paper Title},
  booktitle = {Proceedings of NeurIPS},
  year = {2021},
  pages = {1--10}
}
```

## Inline thebibliography → BibTeX 자동 변환

`/latex:structure`가 다음 변환 수행:

입력 (inline):
```latex
\begin{thebibliography}{99}
\bibitem{smith2020} Smith, J. (2020). Title. Journal, 15(3), 123--145.
\end{thebibliography}
```

출력 (BibTeX):
```bibtex
@article{smith2020,
  author = {Smith, J.},
  title = {Title},
  journal = {Journal},
  year = {2020},
  volume = {15},
  number = {3},
  pages = {123--145}
}
```

#### 상세 변환 규칙 (`\textit` 패턴별 entry type 추론)

| `\textit{...}` 패턴 | Entry type | Field |
|---|---|---|
| `\textit{arXiv preprint ...}` | `@article` | `journal` |
| `\textit{Proceedings of ...}` 또는 `In \textit{...}` | `@inproceedings` | `booktitle` |
| `\textit{Journal Name}` (일반 저널명) | `@article` | `journal` |
| (위 패턴 모두 없음) | `@misc` | 텍스트 전체를 `note` |

#### 보존 규칙

- `\bibitem{key}`의 key는 정확히 그대로 유지
- 저자 abbreviation 가능하면 expand (`E.` → `Eric` if context allows)
- 제목의 대문자는 `{braces}`로 protect (예: `Quiet-{STaR}`)

#### 변환 예시

입력:
```latex
\bibitem[Zelikman et~al.(2024)]{zelikman2024quietstar}
Zelikman, E., Harik, G., ... (2024). Quiet-STaR: ...
\textit{arXiv preprint arXiv:2403.09629}.
```

출력:
```bibtex
@article{zelikman2024quietstar,
  author  = {Zelikman, Eric and Harik, Georges and ...},
  title   = {Quiet-{STaR}: Language Models Can Teach Themselves to Think Before Speaking},
  journal = {arXiv preprint arXiv:2403.09629},
  year    = {2024},
}
```

## 검증 체크리스트

빌드 후 확인:
- [ ] `pdflatex main` 후 `main.log`에서 `Citation undefined` 0건
- [ ] `bibtex main` 후 `main.blg`에서 `couldn't find a database entry` 0건
- [ ] PDF에 `[?]` 형태의 미해결 reference 0건
- [ ] inline `\begin{thebibliography}` 잔존 0건 (`grep -n thebibliography main.tex`)
- [ ] plain text "(Author, Year)" 잔존 0건 (`grep -nE '\([A-Z][a-z]+, [0-9]{4}\)' *.tex`)

### Structure split 후 추가 검증 (8개)

`/latex:structure` 사용 후:

1. `pdflatex -interaction=nonstopmode main.tex` → no `!` errors
2. `bibtex main` → no errors, correct `.bib` file found
3. `pdflatex` × 2 more passes → cross-reference 해소
4. `grep "! " main.log` → 0 results
5. `grep "Overfull" main.log` → 0 results (또는 acceptable)
6. `grep "Citation.*undefined" main.log` → 0 results
7. 페이지 수가 원본과 일치
8. `grep -c "bibitem" main.bbl` matches number of `\cite` calls

## 관련 트러블슈팅

| 증상 | 원인 | 해결 |
|------|------|------|
| `Citation undefined` | refs.bib에 key 없음 | refs.bib에 엔트리 추가, bibtex 재실행 |
| `Empty bibliography` | `\bibliography` 명령 누락 | 마지막 섹션에 추가 |
| `Package natbib Warning: Citation 'foo' on page N undefined` | 첫 컴파일 후 정상 (3-pass 필요) | 3-pass 완료 후에도 남으면 key 확인 |
| 같은 key가 두 entry에 | BibTeX warning + 임의 entry 선택 | 중복 제거 또는 key rename |
| natbib vs biblatex 충돌 | `\usepackage{natbib}`와 `\usepackage{biblatex}` 동시 사용 | 하나만 선택 (natbib + plainnat 권장) |

## 외부 표준

- BibTeX 표준 entry types: https://www.bibtex.com/e/entry-types/
- natbib 매뉴얼: https://ctan.org/pkg/natbib
- biblatex 매뉴얼: https://ctan.org/pkg/biblatex (대안)
