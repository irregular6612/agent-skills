---
name: paper-banana
description: 논문 텍스트에서 methodology diagram, architecture diagram, statistical plot 등 학술 figure를 생성·평가한다.
---

# PaperBanana — Academic Illustration Generator

논문 텍스트로부터 publication-ready 학술 일러스트레이션을 자동 생성한다.
5개 에이전트(Retriever, Planner, Stylist, Visualizer, Critic)가 협력하여
방법론 다이어그램, 통계 차트, 시스템 아키텍처 등을 생성하고 반복 개선한다.

## 구조 — 엔진은 이 스킬 폴더 안에 self-contained

이 스킬은 문서만 있는 게 아니라 **실제 엔진을 함께 포함**한다.

```
~/.codex/skills/paper-banana/
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

MCP 등록(`~/.codex/config.toml`)은 새 경로를 가리킨다:

```jsonc
"paperbanana": {
  "type": "stdio",
  "command": "uv",
  "args": ["--directory", "~/.codex/skills/paper-banana/engine", "run", "paperbanana-mcp"],
  "env": { "GOOGLE_API_KEY": "<key>", "VLM_MODEL": "gemini-2.5-flash" }
}
```

연결 확인: `claude mcp list | grep banana` → `✓ Connected`

## 사용법 2 — CLI (셸에서 직접, 배치/PDF 등 고급 옵션)

CLI는 engine 디렉터리 venv 안에서 돈다. 호출 패턴(어디서 실행하든 동일):

```bash
ENGINE=~/.codex/skills/paper-banana/engine
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
cd ~/.codex/skills/paper-banana/engine
uv sync --extra mcp          # 코어 + MCP(fastmcp)
uv sync --extra mcp --extra pdf   # PDF 입력까지 쓰려면 (pymupdf, 네트워크 느릴 수 있음)
```

API 키는 `engine/.env`(`GOOGLE_API_KEY=...`, gitignore)에 둔다.
MCP 등록의 `env`에도 키가 있어 도구 호출 시엔 그쪽이 우선 적용된다.

## 모델 (2026-05 기준)

- 기본 VLM: `gemini-2.5-flash-lite`
- 에이전트별 권장 분배(자동 적용):
  - Planner → `gemini-3.1-pro-preview`  (품질 기준 업그레이드, 2026-06)
  - Visualizer → `gemini-2.5-flash`
  - Critic → `gemini-3.1-pro-preview`  (※ 구 `gemini-3-pro`(텍스트)는 폐기 → 후속 pro로 교체)
  - Optimizer / Retriever / Stylist → `gemini-2.5-flash-lite`
- 이미지: `gemini-3-pro-image-preview` (Nano Banana Pro)

에이전트별 오버라이드(CLI):
```bash
uv run --directory "$ENGINE" paperbanana generate -i fig.txt -c "..." \
  --vlm-model gemini-2.5-flash-lite \
  --vlm-model-planner gemini-3.1-pro-preview \
  --vlm-model-critic gemini-3.1-pro-preview
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
