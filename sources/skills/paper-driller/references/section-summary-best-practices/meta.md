# Metadata / BibTeX — Best Practices

## Core Fields
| Field | 규칙 |
|---|---|
| Title | 원문 영문 그대로, 대소문자 보존 |
| Authors | `First Last` 형식, 콤마 구분. 5명 초과 시 `et al.` 허용 |
| Year | 4자리 연도 (출판 연도 우선, 없으면 arXiv submission) |
| Venue | 학회/저널 공식명. 프리프린트면 `arXiv preprint` |
| arXiv ID | `XXXX.XXXXX` 형식, 없으면 `N/A` |
| DOI | 전체 DOI 문자열, 없으면 `N/A` |
| URL | arxiv abs 페이지 또는 DOI 페이지 |
| Category | enum: `Architecture / Training / Benchmark/Evaluation / Application / Reasoning / Survey / Dataset / Optimization / Theory / AGI` |

## BibTeX 규칙
- 키: `{first_author_lastname}{year}` 소문자.
- arXiv: `journal={arXiv preprint arXiv:XXXX.XXXXX}` + `eprint`, `archivePrefix` 필드.
- Venue 출판: `journal=` 또는 `booktitle=` 에 공식 venue 명.
- URL 필드 항상 포함.

## Category 분류 heuristic
- Architecture: 새 아키텍처·모듈 제안 주력.
- Training: 학습 알고리즘·목적함수·RL/RLHF.
- Benchmark/Evaluation: 평가 셋·메트릭 신규.
- Application: 특정 도메인 적용 중심.
- Reasoning: inference-time 추론·CoT·tool use.
- Survey: 종합 리뷰.
- Dataset: 데이터셋 공개/분석.
- Optimization: 효율·양자화·pruning.
- Theory: 수학·이론적 분석.
- AGI: 범용 지능·자율성·alignment 철학.

## Anti-patterns
- 저자 이름을 LaTeX accent 없이 깨뜨림.
- Venue를 약칭으로만 표기 (ex: "NeurIPS" 대신 "Advances in Neural Information Processing Systems" 우선).
- 연도를 추측 (확인 안 되면 `N/A`).

## Output Checklist
- [ ] 8개 필드 전부 채움 (또는 `N/A`)
- [ ] BibTeX compile-safe (`@article{...}` 닫힘, 콤마 올바름)
- [ ] Category가 enum 중 하나

## Sources
- [Wikipedia — BibTeX](https://en.wikipedia.org/wiki/BibTeX)
- [CERMINE — Metadata extraction](https://link.springer.com/article/10.1007/s10032-015-0249-8)
- [Yale — Zotero and LaTeX](https://guides.library.yale.edu/bibtex/zotero-and-latex)
