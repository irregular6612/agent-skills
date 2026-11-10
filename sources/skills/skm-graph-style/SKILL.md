---
name: skm-graph-style
description: Fixed visual and accessibility rules for the skm dependency graph dashboard (node shapes, colors, borders, edge styles, keyboard navigation, text summary). Use when generating or changing dashboard/index.html, or when the user asks how to read the skm graph.
metadata:
  prompt_version: graph-style-v1
---

# skm 그래프 출력 스킬

`skm/dashboard_template.html` 의 Cytoscape 스타일이 이 규칙을 구현한다 (`install.py graph` 가 사용). 둘은 항상 같이 바꾼다.

## 노드
| 종류 | 모양 | 크기 |
|---|---|---|
| 스킬 | 원 (`ellipse`) | 연결 수에 비례 22~48px |
| 에이전트 | 둥근 사각형 (`round-rectangle`) | 동일 |
| MCP 서버 | 육각형 (`hexagon`) | 동일 |
| 패키지 | 점 (`ellipse`, 8px, 라벨은 확대 시) | 고정 |

- **색 = 카테고리** (`categorize.py`, `modes.yaml: categories`). 색맹 대비를 위해 Okabe–Ito 계열 팔레트.
- **색 기준 전환**: "패키지·플러그인"을 고르면 색 = 그룹(agent-skills 패키지, 또는 `plugin: <이름>`, MCP 설정, 패키지 없음).
  스킬·에이전트 수가 많은 순으로 위 7개 그룹만 검증된 7색을 쓰고 나머지는 회색. 패키지 점 노드도 그룹 색 + 라벨 표시.
  범례의 그룹은 `<button aria-pressed>` 목록(개수 포함)이고, 누르면 그 그룹 노드와 이웃만 남기고 흐리게, 다시 누르면 해제.
- **테두리 = 심각도**: error = 굵은 이중선(6px `double`), warn = 굵은 점선(4px `dashed`), info = 얇은 점선, 문제 없음 = 얇은 실선.
  색(빨강/주황)도 쓰지만 선 모양만으로 구분 가능해야 한다.

## 엣지
| 관계 | 선 | 화살표 |
|---|---|---|
| `requires` / `uses` | 실선 | 있음 (A → B: A 가 B 필요) |
| `overlaps` (LLM trigger overlap) | 점선 | 없음 |
| `mentions` (규칙: 이름만 언급) | 파선, 얇게 | 있음 |
| `part_of` (패키지) | 아주 얇은 실선, 흐리게 | 없음 |
- **굵기 = confidence** (1 + 4 × confidence px).
- LLM 이 확정한 엣지는 라벨 없이 굵기로만, 규칙 엣지는 hover 시 근거 문장을 툴팁으로.

## 끊긴 연결 (가장 강하게 표시)
- **경고 배너**: 페이지 맨 위, `role="alert"`, 빨간 배경 + 3px 빨간 아래 테두리. "⛔ 끊긴 연결 N개 (전체|세부 모드 X)".
  항목마다 부르는 쪽(클릭하면 그래프에서 포커스) → 없는 대상, `[자동 해결: install <pkg> · <harness>]` 또는 `[수동 조치]`, 근거 문장.
  자동 해결이 하나라도 있으면 `python3 install.py doctor --mode <mode> --fix` 를 함께 보여 준다.
- **유령 노드**: 없는 대상(subagent·MCP·파일·skill)을 마름모(◇)로, 빨간 4px 점선 테두리, 라벨 "⚠ 없음: 이름" (하네스 한쪽에만 없으면 "이름 · codex에 없음").
- **끊긴 선**: 4px 빨간 점선 + 끝이 막힌 화살표(`tee`). 부르는 쪽 노드에는 빨간 underlay(후광).
- **세부 모드 밖**: 선택한 세부 모드의 멤버가 `requires/uses`(confidence ≥ 0.6)하는데 모드에 없는 skill/agent 는
  같은 빨간 점선으로 잇고 대상 노드에 빨간 점선 테두리를 둔다(플러그인 skill 은 항상 로드되므로 제외).
- 색만으로 구분하지 않는다: 마름모 모양·"⚠ 없음" 라벨·막힌 화살표·배너 텍스트가 함께 같은 뜻을 전한다.

## 접근성
1. **색 단독 금지**: 카테고리는 범례에 이름으로, 심각도는 테두리 모양으로, 관계는 선 모양으로 함께 표시.
2. **키보드 이동**: 그래프 영역에 포커스 후 `←/→` 또는 `Tab` 순서로 노드 순회, `Enter` 로 상세 패널, `Esc` 로 해제, `/` 로 검색창.
   목록·문제 탭은 일반 표(`<table>`)라 스크린리더와 Tab 이동이 그대로 된다.
3. **그래프 요약문**: 그래프 위에 `aria-live` 문단으로 "노드 N개(스킬 a, 에이전트 b, MCP c), 의존 엣지 M개, error x · warn y.
   가장 많이 의존받는 것: …" 을 모드가 바뀔 때마다 갱신.
4. 다크/라이트 모드 모두 대비 4.5:1 이상의 라벨 색.
