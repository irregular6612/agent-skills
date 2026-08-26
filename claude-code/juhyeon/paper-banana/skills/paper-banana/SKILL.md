---
name: paper-banana
description: >-
  논문 텍스트에서 publication-ready 학술 일러스트레이션(methodology diagram, statistical plot, system architecture)을 PaperBanana 멀티 에이전트 파이프라인으로 생성·수정·평가. MANDATORY TRIGGERS: paperbanana, paper banana, 논문 figure, 논문 그림, methodology diagram, architecture diagram, statistical plot, 학술 일러스트레이션, figure 생성, 차트 생성, 시스템 구조도, pipeline diagram, 모델 아키텍처 시각화, figure 평가, diagram 비교
---

# PaperBanana — Academic Illustration Generator

논문 텍스트로부터 publication-ready 학술 일러스트레이션을 자동 생성한다.
5개 에이전트(Retriever, Planner, Stylist, Visualizer, Critic)가 협력하여
방법론 다이어그램, 통계 차트, 시스템 아키텍처 등을 생성하고 반복 개선한다.

## 구조 — 엔진은 이 스킬 폴더 안에 self-contained

이 스킬은 문서만 있는 게 아니라 **실제 엔진을 함께 포함**한다.

```
~/.claude/skills/paper-banana/
├── SKILL.md          ← 이 문서 (사용법)
├── .gitignore        ← engine/.venv · .env · outputs 제외
└── engine/           ← PaperBanana Python 패키지 (실제 엔진)
    ├── paperbanana/      코어 + 에이전트(agents/) + 프로바이더
    ├── mcp_server/       FastMCP 래퍼 (server.py)
    ├── prompts/ data/ configs/   런타임 리소스
    ├── pyproject.toml · uv.lock   의존성 정의(재현 가능)
    ├── .venv/            ← uv sync 로 재생성 (gitignore, 미추적)
    └── .env             ← GOOGLE_API_KEY (gitignore, 미추적)
```

`paperbanana`(CLI)와 `paperbanana-mcp`(MCP 서버)는 **같은 패키지의 두 진입점**이며
같은 `.venv` 안에 동시에 존재한다. 즉 MCP로도, CLI로도 동일 엔진을 호출할 수 있다.

> 참고: 원본 개발 클론은 `~/Documents/WorkSpace/paperbanana`(업스트림 fork, `.git` 보유)에
> 그대로 남아 있다. 업스트림 업데이트가 필요하면 거기서 `git pull` 후, 변경된 소스를
> `engine/`으로 다시 복사하고 `uv sync`를 돌린다.

## 사용법 1 — MCP 도구 (Claude가 직접 호출, 기본 경로)

이 스킬이 활성화되면 Claude는 아래 MCP 도구를 **직접 호출**할 수 있다.
별도 셸 명령 없이 도구 호출만으로 그림이 생성된다.

| MCP 도구 | 용도 |
|---|---|
| `mcp__paperbanana__generate_diagram` | 텍스트 → 방법론/아키텍처 다이어그램 |
| `mcp__paperbanana__generate_plot` | JSON 데이터 → 통계 차트(Matplotlib) |
| `mcp__paperbanana__evaluate_diagram` | 생성물 vs 참조 이미지 품질 평가 |
| `mcp__paperbanana__download_references` | 확장 레퍼런스 세트(~294 예시) 다운로드 |

MCP 등록(`~/.claude.json`)은 새 경로를 가리킨다:

```jsonc
"paperbanana": {
  "type": "stdio",
  "command": "uv",
  "args": ["--directory", "~/.claude/skills/paper-banana/engine", "run", "paperbanana-mcp"],
  "env": { "GOOGLE_API_KEY": "<key>" }
}
```

연결 확인: `claude mcp list | grep banana` → `✓ Connected`

## 사용법 2 — CLI (셸에서 직접, 배치/PDF 등 고급 옵션)

CLI는 engine 디렉터리 venv 안에서 돈다. 호출 패턴(어디서 실행하든 동일):

```bash
ENGINE=~/.claude/skills/paper-banana/engine
uv run --directory "$ENGINE" paperbanana <command> ...
```

### Methodology Diagram 생성

```bash
uv run --directory "$ENGINE" paperbanana generate \
  --input <텍스트_파일.txt> \
  --caption "<Figure 캡션>" \
  --optimize --auto
```

주요 옵션:
- `--input` / `-i`: 방법론 텍스트(.txt) 또는 논문 PDF(.pdf)  ※ PDF는 `pdf` extra 필요(아래)
- `--caption` / `-c`: communicative intent (그림이 전달할 핵심 메시지)
- `--optimize`: 입력 전처리로 품질 향상
- `--auto`: Critic이 만족할 때까지 자동 반복
- `--iterations N` / `-n`: 수동 반복 횟수(기본 3)
- `--format [png|jpeg|webp]`: 출력 포맷

PDF 입력:
```bash
uv run --directory "$ENGINE" paperbanana generate \
  --input paper.pdf --caption "Overview of our framework" \
  --pdf-pages "3-8" --optimize --auto
```

### Statistical Plot 생성

```bash
uv run --directory "$ENGINE" paperbanana plot \
  --data <결과.csv> --intent "<원하는 차트 설명>"
```

### 품질 평가 (Faithfulness · Readability · Conciseness · Aesthetics)

```bash
uv run --directory "$ENGINE" paperbanana evaluate \
  --generated <생성.png> --reference <참조.png> \
  --context <원본.txt> --caption "<캡션>"
```

### 이전 결과 수정 / 배치

```bash
uv run --directory "$ENGINE" paperbanana generate --continue --feedback "화살표를 더 굵게"
uv run --directory "$ENGINE" paperbanana generate --continue-run <run_ID> --iterations 3
uv run --directory "$ENGINE" paperbanana batch --manifest manifest.yaml --optimize
```

config·모델 맵 확인: `uv run --directory "$ENGINE" paperbanana show-config`

## 셋업 / 복구 (venv 재생성)

`.venv`는 미추적(재생성 가능)이다. 새 머신이거나 깨졌을 때:

```bash
cd ~/.claude/skills/paper-banana/engine
uv sync --extra mcp          # 코어 + MCP(fastmcp)
uv sync --extra mcp --extra pdf   # PDF 입력까지 쓰려면 (pymupdf, 네트워크 느릴 수 있음)
```

API 키는 `engine/.env`(`GOOGLE_API_KEY=...`, gitignore)에 둔다.
MCP 등록의 `env`에도 키가 있어 도구 호출 시엔 그쪽이 우선 적용된다.

## 모델 (2026-07-30 기준)

값은 `engine/.env`에 슬롯별 env로 박혀 있고, `core/config.py`의 코드 기본값도 같은 값으로
맞춰 두었다. 즉 `.env`가 사라져도 동작은 동일하다.

| 슬롯 | 모델 | 역할 | 호출/figure |
|---|---|---|---|
| Planner | `gemini-3.6-flash` | 논문 텍스트 + 참조 이미지 10장 → 다이어그램 전체 사양 서술 | 1 |
| Critic | `gemini-3.6-flash` | 생성 이미지 판독 → 수정 지시 | N (기본 3, `--auto` 최대 30) |
| Visualizer | `gemini-3.6-flash` | **plot 경로 전용**(matplotlib 코드 생성). diagram 경로에선 미사용 | 0~N |
| Stylist | `gemini-3.5-flash-lite` | 심미 가이드라인 기반 서술 재작성 | 1 |
| Retriever / Optimizer | `gemini-2.5-flash-lite` | 참조 top-10 선별 / 입력 전처리 | 각 0~1 |
| Image | `gemini-3-pro-image` | 실제 렌더링 (Nano Banana Pro, 4K·텍스트 정확도 ~94%) | N |

교체 근거 (2026-07):
- Planner·Critic이 쓰던 `gemini-3.1-pro-preview` → `gemini-3.6-flash`. AA 지능지수 50 vs 46,
  $1.50/$7.50 vs $2.00/$12.00, 출력 속도 약 2배. 차트·멀티모달 판독에서도 우위라 Critic 용도에 부합.
- `gemini-3-pro-image-preview` 별칭은 **2026-06-25 셧다운** → GA id `gemini-3-pro-image`로 교체(필수).
- Stylist는 `gemini-2.5-flash-lite`(AA 16)로는 3천 자 가이드라인 판단이 버거워 `3.5-flash-lite`(AA 36)로 승급.
- Retriever/Optimizer는 단순 작업이라 최저가 `2.5-flash-lite` 유지.

비용 지배 요인은 텍스트가 아니라 **이미지 모델**이다. Pro는 장당 $0.134~0.24라 3회 반복이면
figure 1장에 $0.4~0.7. 초안을 싸게 돌리려면 `IMAGE_MODEL=gemini-3.1-flash-image`
(Nano Banana 2, 1K 기준 장당 ~$0.067)로 내리고 최종본만 Pro로 다시 뽑는다.

주의: `GOOGLE_VLM_MODEL`은 슬롯 경로에 **적용되지 않는다**(레거시 단일 VLM 경로 전용).
슬롯을 바꾸려면 `VLM_MODEL_<SLOT>` env 또는 아래 CLI 플래그를 쓴다.

에이전트별 오버라이드(CLI):
```bash
uv run --directory "$ENGINE" paperbanana generate -i fig.txt -c "..." \
  --vlm-model gemini-2.5-flash-lite \
  --vlm-model-planner gemini-3.6-flash \
  --vlm-model-critic gemini-3.6-flash
```

## 워크플로우

1. 사용자가 논문 텍스트나 PDF를 제공하면, figure로 만들 부분을 파악한다
2. 적절한 caption(communicative intent)을 작성한다 — 이것이 그림의 핵심 메시지가 된다
3. MCP 도구(`generate_diagram`)로 생성하고 결과 이미지를 사용자에게 보여준다
   (셸 옵션이 필요하면 CLI `paperbanana generate`)
4. 피드백이 있으면 `--continue --feedback`으로 수정한다
5. 최종 결과물을 workspace 폴더에 저장한다

## 출력 구조

```
engine/outputs/run_<timestamp>_<hash>/   (gitignore)
├── final_output.png      # 최종 이미지
├── metadata.json         # 생성 메타데이터
├── iterations/           # 반복 과정
└── intermediate_states/  # 중간 상태
```

## 사용 한도 참고 (Gemini API Tier 2)

그림 1장당 약 10~20 API 호출을 소비한다.
Tier 2 기준 일일 500요청이면 하루 약 25~50장의 figure를 생성할 수 있다.
Rate limit 에러 시 잠시 후 재시도하거나 모든 슬롯을 `gemini-2.5-flash-lite`로 통일한다.
