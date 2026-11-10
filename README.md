# agent-skills

Claude Code와 Codex에서 쓰는 제 skill·subagent·설정을 **파일 하나로 골라서 설치하고, 골라서 지우는** 저장소입니다.

- **내 skill**은 `sources/`에 원본 하나만 둡니다. Claude Code와 Codex 양쪽이 같은 원본을 symlink로 씁니다(SSOT).
- **남의 skill**은 이 저장소에 복사해 두지 않습니다. `catalog.json`에 원작자 repo, 고정 커밋, 경로만 적어 두고, 설치할 때 원작자 repo에서 받아 옵니다.
- superpowers 같은 외부 plugin도 skill 단위로 받아서 골라 설치합니다. MCP 서버, hook, plugin 전용 런타임이 꼭 필요한 것만 공식 `claude plugin` CLI로 설치합니다.
- 설치할 때마다 지금 설치된 skill, subagent, MCP 서버의 **의존성 그래프**(Obsidian 스타일 HTML)를 다시 만듭니다.

## 설치

macOS / Linux:

```bash
curl -fsSL https://raw.githubusercontent.com/irregular6612/agent-skills/master/install.sh | bash
```

Windows (PowerShell, 아직 검증 전):

```powershell
irm https://raw.githubusercontent.com/irregular6612/agent-skills/master/install.ps1 | iex
```

저장소를 `~/.agent-skills/repo`에 받은 뒤 선택 화면을 엽니다. 번호(`1 3 5-8`), 패키지 id, 패키지 안의 skill 하나(`k-dense:literature-review`), 프리셋 이름(`mine`, `day`, `night`) 중 무엇이든 입력하면 됩니다.

필요한 것: Python 3.9+ (표준 라이브러리만 씁니다), git. plugin 항목을 고를 때만 `claude` / `codex` CLI가 필요합니다.

## 사용법

```bash
python3 install.py                                  # 대화형 선택
python3 install.py list                             # 카탈로그와 설치 상태 ([x])
python3 install.py install ditto-writer humanize    # 골라서 설치
python3 install.py install superpowers:brainstorming k-dense:literature-review   # 패키지 안의 skill 하나만
python3 install.py install --preset day             # 제 낮 세팅 (mattpocock + 내 skill, pstack 없음)
python3 install.py install --preset night           # 제 밤 세팅 (pstack 전체 + 내 skill, mattpocock 없음)
python3 install.py install pstack --mode night      # 특정 mode에 설치
python3 install.py home night claude                # night 세션용 폴더 경로 (alias가 사용)
python3 install.py uninstall humanize               # 골라서 제거 (인자 없으면 대화형)
python3 install.py uninstall --all                  # 이 도구가 설치한 것 전부 제거
python3 install.py graph --open [--mode night]      # 의존성 그래프 열기 (day·night 한 페이지, --mode = 처음 보일 모드)
python3 install.py check [--mode night]             # skill 의존성 점검 (문제가 있으면 exit 1)
python3 install.py check --llm [--limit 20]         # + LLM 판정(트리거 겹침·지시 충돌, 캐시) — warn까지만
python3 install.py doctor [--mode night] [--fix]    # 끊긴 연결 찾기 → --fix 면 고치는 패키지를 설치
python3 install.py skm run paper -- claude          # 세부 모드: paper 스킬 세트만 켠 세션
python3 install.py skm switch autopilot-code --session <id>   # 세션의 스킬 세트 교체
python3 install.py skm modes [--show paper | --sessions]      # 세부 모드 목록 / 멤버 / 세션
```

자주 쓰는 옵션은 아래와 같습니다.
- `--harness claude,codex,hermes`: 대상을 고릅니다. 기본값은 이 기기에 있는 쪽입니다. Hermes는 낮/밤 구분 없이 `~/.hermes/skills`에 바로 링크합니다(catalog에 `"harness": "hermes"` 항목이 있는 패키지만).
- `--mode day|night`: 어느 skill 조합에 설치·제거할지 고릅니다. 기본값은 day입니다(`--preset night`이면 night).
- `--method link|copy`: 기본값은 mac/linux가 link, windows가 copy입니다.
- `--dry-run`: 실제로 바꾸지 않고 무엇이 바뀔지만 보여 줍니다.
- `-y`: 확인 질문 없이 진행합니다.
- `--force`: 설치 후 직접 수정한 항목도 교체하거나 제거합니다.

한 줄 설치에 인자를 넘길 수도 있습니다: `curl -fsSL …/install.sh | bash -s -- install ditto-writer -y`

## 낮 / 밤 mode

skill·subagent·명령만 mode별로 따로 조합하고, 대화 기록·설정·로그인·plugin·MCP는 `~/.claude`, `~/.codex` 한 곳을 같이 씁니다.

```text
원본     sources/ (내 skill)  +  ~/.agent-skills/vendor/ (원작자 repo)
  ↓ symlink
조합     ~/.agent-skills/modes/{day,night}/{claude,codex}/{skills,agents,commands|prompts}
  ↓ symlink
실행     day   : ~/.claude/skills 등이 modes/day를 가리킴 → 그냥 `claude`, `codex`
         night : ~/.agent-skills/homes/night/<claude|codex[-계정]>
                 skill 폴더만 modes/night, 나머지는 전부 ~/.claude·~/.codex로 symlink
```

세션을 시작할 때 mode를 고릅니다. 예시 셸 함수(제 `~/.zshrc`):

```zsh
_agent_launch() {   # _agent_launch <claude|codex> <계정> [day|night] [args...]
  local tool=$1 account=$2; shift 2; local mode=day
  if [[ $1 == day || $1 == night ]]; then mode=$1; shift; fi
  local home; home=$(python3 ~/Workspace/agent-skills/install.py home $mode $tool --account $account) || return 1
  if [[ $tool == claude ]]; then
    local token; token=$(security find-generic-password -s "claude-token-$account" -w) || return 1
    if [[ $mode == day ]]; then CLAUDE_CODE_OAUTH_TOKEN=$token claude "$@"
    else CLAUDE_CONFIG_DIR=$home CLAUDE_CODE_OAUTH_TOKEN=$token claude "$@"; fi
  elif [[ $home == $HOME/.codex ]]; then CODEX_HOME=$home codex "$@"
  else CODEX_HOME=$home CODEX_SQLITE_HOME=$HOME/.codex codex "$@"; fi
}
claude-juhyeon() { _agent_launch claude juhyeon "$@"; }   # claude-juhyeon night
codex-jhjh6612() { _agent_launch codex jhjh6612 "$@"; }   # codex-jhjh6612 night
```

Codex night 폴더의 `config.toml`은 평소 설정에서 subagent 등록만 night 것으로 바꿔 자동 생성합니다. Codex는 `~/.agents/skills`를 mode와 상관없이 읽으므로 이 폴더는 비워 둡니다.

## 동작 방식

| 무엇 | 어디에 |
|---|---|
| 내 skill·agent·command·hook 원본 | `sources/` → `~/.agent-skills/modes/<mode>/…`에 symlink (hook·전역 지침은 `~/.claude`, `~/.codex`에 직접) |
| 외부 skill | `~/.agent-skills/vendor/<owner>__<repo>/<commit>/`에 필요한 경로만 받음 (git sparse checkout, git이 없으면 tarball) |
| 설치 기록 | `~/.agent-skills/state.json` |
| 원래 있던 파일 | `~/.agent-skills/backups/`로 옮겨 두었다가 제거할 때 되돌림 |
| Codex subagent 등록 | `~/.codex/config.toml` 끝에 표시된 블록(`# >>> agent-skills managed agents`)으로만 추가·삭제 |
| Claude hook 등록 | `~/.claude/settings.json`에 추가한 항목만 기록해 두고 제거할 때 그것만 뺌 |
| 의존성 그래프 | `~/.agent-skills/graph.html` (day·night 한 페이지, 위쪽 토글로 전환) |

- **uninstall은 이 도구가 놓은 것만 지웁니다.** 설치 뒤 사용자가 고친 항목은 `--force` 없이 건드리지 않습니다.
- **같은 이름 skill이 두 패키지에 있으면** 먼저 설치된 쪽을 유지하고 경고합니다. 예: `pstack`과 `mattpocock-skills`에 둘 다 있는 `tdd`. 그래서 mattpocock은 day에만, pstack은 night에만 둡니다.
- **설치 전에 의존성을 점검합니다.** 새로 넣을 skill마다 아래를 확인하고, 하나라도 있으면 목록을 보여 준 뒤 `Install anyway?`로 묻습니다(`-y`면 보고만 하고 진행). 설치된 전체는 `install.py check --mode <mode>`로 같은 점검을 합니다.
  - 이미 다른 패키지가 같은 이름을 가지고 있어 설치되지 않는 skill
  - 본문이 부르는 skill(`/name`, `` `name` ``, `../name/SKILL.md`, Skill tool로 부르는 이름)이 그 mode에 없는 경우와, 설치할 패키지 이름
  - 외부 skill이 자기 패키지의 skill을 부르는데, 그 mode에는 다른 패키지의 같은 이름 skill이 있는 경우
  - skills 폴더 밖을 가리키는 상대 링크(`../../docs/...`)
- 외부 skill이 skills 폴더 밖의 파일(`../../docs/x.md`)을 링크하면, catalog의 `support_paths`로 그 파일을 함께 받고 링크를 받은 파일의 절대 경로로 바꾼 사본(`~/.agent-skills/overlays/rebased/`)을 설치합니다. 에이전트는 링크를 설치된 위치 기준으로 풀기 때문에, 원본 링크로는 찾지 못합니다.
- catalog의 `files_glob`이 `agents`로 보내는 Markdown subagent는 Codex용으로 TOML(`name`, `description`, `developer_instructions`)로 바꿔 설치합니다.
- 외부 skill을 새 버전으로 올리려면 `catalog.json`의 `ref`를 원하는 커밋 SHA로 바꾼 뒤 `install`을 다시 실행합니다.

## 의존성 그래프

`install`과 `uninstall`이 끝날 때마다, 또는 `install.py graph`를 실행하면 `~/.claude`와 `~/.codex`를 실제로 스캔해 그래프를 다시 만듭니다.

- **노드**: skill(보라), subagent(청록), MCP 서버(주황)
  - 직접 설치한 것, 켜져 있는 plugin 안의 것, `~/.claude.json`과 `~/.codex/config.toml`에 등록된 MCP를 모두 포함합니다.
- **간선**: skill이나 subagent 본문(SKILL.md, references/)이 다른 subagent, skill, MCP를 언급하면 이어집니다.
  - 하이픈이 들어간 이름은 그대로 찾습니다.
  - `pdf`·`debugger`처럼 한 단어 이름은 같은 줄에 skill/agent/MCP 같은 단어가 함께 있을 때만 셉니다.
  - MCP는 `mcp__<server>__` 도구 이름 형태도 찾습니다.
- **조작**: 드래그, 휠 확대, 검색, 종류·대상·출처 필터, 노드를 클릭하면 "쓰는 subagent / MCP / skill"과 "이것을 쓰는 쪽" 목록이 나옵니다.

이 페이지는 이제 skm 대시보드입니다(이전 페이지는 `graph --classic`). 데이터는 위와 같은 스캔을 쓰고, 분석은 `skm/`가 합니다.
- **day / night 토글**: 맨 위 버튼으로 모드를 바꿉니다. 한 파일(`graph.html`)에 설치된 모드가 모두 들어 있고, 주소 끝 `#night`로 바로 열 수도 있습니다.
- **탭**: 그래프 · 목록(정렬되는 표) · 문제. **세부 모드 드롭다운**으로 paper·autopilot-code 등만 남겨 볼 수 있습니다.
- **모양** = 종류(스킬 원, 에이전트 사각형, MCP 육각형, 패키지 점), **색** = 카테고리, **테두리** = 심각도(error 이중선, warn 점선).
- **색 기준** 드롭다운으로 색을 패키지·플러그인별(mattpocock-skills, pstack, `plugin: cloudflare` …)로 바꿀 수 있습니다. 큰 패키지 7개는 색, 나머지는 회색이고, 범례의 패키지 이름을 누르면 그 패키지와 연결만 남기고 강조합니다.
- **선**: 실선 화살표 = 필요(requires/uses), 점선 = 트리거 겹침(LLM), 파선 = 이름만 언급, 굵기 = confidence.
- **끊긴 연결 경고**: 없는 skill·subagent·MCP·파일을 부르는 곳이 있으면 맨 위에 빨간 배너가 뜨고, 그래프에는
  ◇ 유령 노드와 끝이 막힌 빨간 굵은 점선으로 그립니다. 항목마다 `[자동 해결: install …]` 또는 `[수동 조치]`가 붙습니다.
  세부 모드를 고르면 그 모드에 없는 대상을 필요로 하는 연결도 같은 방식으로 표시합니다.
- 키보드: 그래프에서 ←/→ 노드 이동, Enter 상세, Esc 해제, `/` 검색. 그래프 위에 요약문이 있습니다.
- install/uninstall/graph 때는 **LLM을 부르지 않습니다**. 캐시된 판정(`~/.agent-skills/skm/judgments.json`)만 씁니다.

### 점검과 자동 해결 (`check --llm`, `doctor`)

- `check --llm`: 규칙 점검 뒤에 후보 쌍(규칙 점수 상위 `--limit`개, 기본 100)을 `claude -p --model haiku`로 판정해
  trigger_overlap · instruction_conflict 를 보고합니다. 판정은 `sha256(파일A + 파일B + prompt_version)` 키로 캐시되어
  다시 돌리면 호출 0회입니다. LLM 결과는 warn이 상한이라 종료 코드는 규칙 점검 결과 그대로입니다. `--submode paper`는 그 세트 안만 봅니다.
  프롬프트·기준은 `sources/skills/skm-dep-judge`, `skm-conflict-audit` 스킬 문서에 있습니다.
- `doctor`: 모드의 끊긴 연결을 모아 **카탈로그 패키지 하나가 그것을 제공하면 자동 해결**로, 아니면 수동 조치로 분류합니다.
  기본은 미리보기이고 `--fix`를 붙이면 해당 harness에 `install`을 실행합니다(설치 전 확인, `-y`로 생략, `uninstall`로 되돌림).
  제공 패키지가 없거나 여러 개인 경우, 파일 링크, 플러그인과 중복 설치, LLM 경고는 설명만 출력합니다.
  패키지가 그 harness 용 항목을 갖고 있을 때만 자동 해결로 칩니다(claude 전용 패키지는 codex 문제를 고치지 못함).
  일부러 뺀 패키지는 `submodes.json`의 `"doctor": {"skip": [...]}`에 적어 두면 CLI와 대시보드 모두 자동 해결로 내놓지 않습니다(한 번만 빼려면 `--skip <패키지>`).

## 세부 모드 (`install.py skm`)

낮/밤 위에 더 작은 세트를 얹습니다. `submodes.json`에 `base`(항상 켜짐)와 `submodes`(카테고리·include·exclude)를 적고,
`paper+office`처럼 더해 씁니다. 멤버가 `requires`하는 skill은 자동으로 같이 켜집니다(closure).

```text
~/.agent-skills/skm/sessions/<id>/.claude/{skills,agents}  ← 그 세트만 symlink
claude --setting-sources project,local --settings ~/.claude/settings.json --add-dir <세션 폴더>
```
- `~/.claude/skills`(=day 조합)를 빼고 세션 폴더의 skill만 읽습니다. 설정·hook·plugin은 `--settings`로 그대로 씁니다.
- `skm switch`는 세션 폴더 안의 링크만 바꿉니다. 실행 중인 claude가 바로 반영하는지는 아직 확인하지 않았습니다(안 되면 `/clear` 또는 재시작).
- `skm sync`는 `submodes.json`을 고친 뒤 모든 세션 폴더에 다시 반영하고, `skm prune [--apply]`는 오래된 세션 폴더를 `~/.agent-skills/skm/archive/`로 옮기며 어느 세부 모드에도 없는 skill을 알려 줍니다(설치된 skill은 옮기지 않습니다).
- Claude 전용입니다. Codex 세부 모드는 아직 없습니다.

## 패키지 목록

### 내 skill · subagent

| 패키지 | 대상 | 설명 |
|---|---|---|
| `ditto-writer` | claude + codex | 내가 직접 쓴 글로 만든 문체·저자 프로필로, 사람이 쓴 것처럼 글을 다시 쓰는 루프(writer 1 + 매 라운드 새 블라인드 리뷰어 Anthropic·OpenAI). 트리거 — 내 말투로 바꿔줘… |
| `humanize` | claude + codex | AI(ChatGPT·Claude·Gemini)가 쓴 한글·영문 텍스트를 사람이 쓴 것처럼 윤문(한글 Fast/Strict 듀얼 모드, 영문 voice 기반). 내용·사실·수치·인용은 한 글자도 안 … |
| `iterative-academic-writer` | claude + codex | Use when writing academic documents — 논문 섹션(Introduction, Methods, Results, Discussion), 연구 제안서, SoP, 학업계획서, 기… |
| `paper-radar` | claude + codex | 개인 관심 트랙 기반 논문 발굴·선별 레이더. 반복 실행(daily/weekly)해 여러 트랙에서 후보를 모으고, 이전 radar state와 기존 Wiki에 대해 중복 제거한 뒤 학습 가치로 랭킹… |
| `paper-driller` | claude + codex | 논문 1편을 원문 옆에 띄워 놓고 읽기 위한 근거 추적 노트를 만든다. 사용자가 고른 템플릿(기본 general-v1: paper-digest 개요 + 배경 + 지표 + 방법 + 결과 + take-… |
| `paper-understand` | claude + codex | 선택한 논문 1편을 질문·응답으로 이해시키는 다회차 튜터. 원문 근거에 묶인 채로 개념 지도를 세우고, 예측→피드백→teach-back→전이 질문 루프로 숙달을 올리며, 학습 상태를 비공개로 저장해… |
| `lost-me` | claude + codex | AI가 쓴 학술 산문을 독자가 떨어져 나간 지점으로 고치는 스킬. 격리된 독자 시뮬레이터 셋(학술·읽힘·사람다움)이 초안을 읽고 "여기서 멈췄다"의 좌표를 내고, writer 가 그 좌표만 보고 다시 쓴다(subagent 5개는 claude 만)… |
| `paper-section-rewrite` | claude + codex | 학술 논문 한 섹션을 4-Level critic loop(내용→문단 간 구성→문단 내 구성→문장)로 분석·개선하는 윤문 스킬. 두괄식·한 문장 한 역할·단문 비율 ≥ 60%·ML 비전공자 가독성 게… |
| `paper-readability-review` | claude + codex | 논문 PDF를 맥락을 공유하지 않는 두 에이전트가 따로 평가해 리뷰 PDF 하나로 묶는다. (A) 가독성 10개 기준 기준별 100점 + 수정 샘플 마진 카드, (B) 지정 학회·저널(기본 ICML) 리뷰어 관점 claim–evidence·반례 질문·결정권자 우선순위… |
| `paper-digest` | claude + codex | Generate shareable paper summaries for Discord/Slack/Twitter. Use when user provides arxiv paper(s) and wants … |
| `paper-banana` | claude + codex | 논문 텍스트에서 publication-ready 학술 일러스트레이션(methodology diagram, statistical plot, system architecture)을 PaperBanana… |
| `latex-publication` | claude + codex | LaTeX 학술 문서 출판 워크플로 — 5개 서브커맨드 자동 라우팅. TRIGGERS: 한글 LaTeX 셋업/한글 렌더링 안됨/kotex 설정/Overleaf 한글/tex 한국어 → :setup ·… |
| `skm` | claude + codex | `install.py doctor`·`check --llm`·그래프 대시보드·`install.py skm` 세부 모드가 쓰는 프롬프트와 규칙(skm-dep-judge·skm-conflict-audit·skm-graph-style). |
| `hwpx` | claude + codex | Comprehensive HWPX (Korean Hancom Office) document creation, editing, and analysis. When Claude needs to work … |
| `aha` | claude + codex | Use when the user asks for an "aha", today's learning, or a short daily blog post based on a current Codex ses… |
| `autoresearch` | claude + codex | Run an autonomous experiment loop — change one variable, measure, keep or revert, self-debug, repeat — until a… |
| `book-qa-note` | claude + codex | 서울대 권장도서 100선·일반 책을 "직접 안 읽고 문답으로 배우는" Obsidian 책 노트(Public/Books) 형식으로 조사·작성하고, 문답 기록·읽기 상태를 갱신한다. 트리거 — 책 정리… |
| `korean-scholarship-search` | claude + codex | Search Korean scholarship announcements across official KOSAF, university, foundation, company, and public-sec… |
| `gist-library-room-booking` | claude + codex | GIST 중앙도서관 시설(그룹스터디룸·캐럴·강의실, library.gist.ac.kr) 검색·예약. 날짜·시간대를 주면 빈 방을(기본 2–3층) 정원·운영시간과 함께 나열하고, 사용자 확정 시 예약… |
| `research-proposal` | claude + codex | 연구 아이디어를 기반으로 종합 연구 계획서를 작성합니다. 선행 연구 조사, 아이디어 구체화(가설/RQ 분리), 학술 비평 피드백 루프, 학계 기여도 평가, 상세 실험 설계(변인통제/GPU 리소스/G… |
| `weekly-report-writer` | claude + codex | Automatically generate academic-style weekly research reports by analyzing Git changes in the current project … |
| `claude-command-library` | codex | Reuse, inspect, adapt, or run migrated Claude Code slash commands from ~/.codex/commands inside Codex. |
| `claude-subagent-library` | codex | Reuse, inspect, adapt, or run migrated Claude Code specialist prompts as Codex-compatible custom agents. |
| `aside-browser` | claude + codex | 로그인된 개인 계정 작업(메일·일정·메신저·개인 맥락)을 Aside CLI로 처리. 나머지 브라우저 작업은 agent-browser. `aside` CLI 필요 |
| `dev-agents` | claude + codex | General engineering subagents: code-reviewer, debugger, code-cleanup-optimizer, modular-code-architect, securi… |
| `research-agents` | claude + codex | Research workflow subagents: experiment-interpreter, experiment-verifier, academic-planner, academic-writing-a… |
| `portfolio-agents` | codex | Codex-only stock portfolio analysis roles: chart, fundamentals, news |
| `juhyeon-hooks` | claude + codex | Links hook scripts and registers PostToolUse/SubagentStop hooks in ~/.claude/settings.json. |

### 외부 skill (원작자 repo에서 고정 커밋으로 받아 옴)

| 패키지 | 원작자 repo | 커밋 | 라이선스 | 포함 skill |
|---|---|---|---|---|
| `taste-skill` | [Leonxlnx/taste-skill](https://github.com/Leonxlnx/taste-skill) | `84ff339` | MIT | brandkit, design-taste-frontend, full-output-enforcement, image-to-code, industrial-brutalist-ui, minimalist-ui, redesign-existing-projects, gpt-taste, high-end-visual-design, imagegen-frontend-web, stitch-design-taste |
| `k-dense` | [K-Dense-AI/scientific-agent-skills](https://github.com/K-Dense-AI/scientific-agent-skills) | `a25cf9e` | MIT | autoskill, citation-management, latex-posters, literature-review, markdown-mermaid-writing, pptx-posters, research-grants, scientific-schematics, scientific-slides |
| `pstack` | [cursor/plugins](https://github.com/cursor/plugins/tree/main/pstack) | `ae5650f` | MIT | `pstack/skills/` 아래 전부 (원칙 skill, benchmark-checklist, blast-radius, /poteto-mode의 hillclimb 플레이북 등). night 전용. skill 전부 + subagent `poteto-agent`·`comment-sicko` + 링크용 `docs/`·`README.md` |
| `cloudflare-skills` | [cloudflare/skills](https://github.com/cloudflare/skills) | `1a33048` | Apache-2.0 | `skills/` 아래 전부 |
| `document-skills` | [anthropics/skills](https://github.com/anthropics/skills) | `ca45fc4` | Proprietary (see upstream LICENSE.txt) | docx, pdf, pptx, xlsx |
| `notebooklm` | [teng-lin/notebooklm-py](https://github.com/teng-lin/notebooklm-py) | `7db1000` | MIT | notebooklm |
| `eli5` | [DreambigOu/ELI5](https://github.com/DreambigOu/ELI5) | `a766623` | MIT | eli5 |
| `find-skills` | [vercel-labs/skills](https://github.com/vercel-labs/skills) | `773fb2c` | MIT | find-skills |
| `karpathy-guidelines` | [forrestchang/andrej-karpathy-skills](https://github.com/forrestchang/andrej-karpathy-skills) | `2c60614` | unspecified upstream | CLAUDE.md → 전역 지침 |
| `superpowers` | [obra/superpowers](https://github.com/obra/superpowers) | `2ce8aa1` | MIT | `skills/` 아래 전부 |
| `mattpocock-skills` | [mattpocock/skills](https://github.com/mattpocock/skills) | `4ae2317` | MIT | `skills/engineering/` 아래 전부 + 그 skill들이 부르는 `skills/productivity/`의 grill-me, grilling, handoff, teach, to-questionnaire, wait-what, writing-for-agents. day 전용 |
| `claude-official-skills` | [anthropics/claude-plugins-official](https://github.com/anthropics/claude-plugins-official) | `a7ba5b9` | Apache-2.0 | frontend-design, skill-creator, claude-automation-recommender |
| `rea` | [morluto/rea](https://github.com/morluto/rea) | `144843c` | MIT | reverse-engineer-anything + `rea` MCP 서버 (`npm install --global rea-agents` 필요) |
| `agent-browser` | [vercel-labs/agent-browser](https://github.com/vercel-labs/agent-browser) | `5868f7c` | Apache-2.0 | agent-browser (`npm install -g agent-browser && agent-browser install` 필요) |
| `kordoc` | [chrisryugj/kordoc](https://github.com/chrisryugj/kordoc) | `6c17bf1` | MIT | kordoc (`plugins/kordoc/skills/kordoc`, Node.js 20+ 필요 — `npx -y kordoc@<버전>`으로 실행). day·night 둘 다 |

### 외부 plugin (claude/codex CLI로 설치 — MCP·hook·plugin 런타임이 필요한 것만)

| 패키지 | plugin | marketplace |
|---|---|---|
| `understand-anything` | `understand-anything` (claude) | [Lum1104/Understand-Anything](https://github.com/Lum1104/Understand-Anything) |
| `context7` | `context7` (claude) | [anthropics/claude-plugins-official](https://github.com/anthropics/claude-plugins-official) |
| `code-review` | `code-review` (claude) | [anthropics/claude-plugins-official](https://github.com/anthropics/claude-plugins-official) |
| `ralph-loop` | `ralph-loop` (claude) | [anthropics/claude-plugins-official](https://github.com/anthropics/claude-plugins-official) |
| `learning-output-style` | `learning-output-style` (claude) | [anthropics/claude-plugins-official](https://github.com/anthropics/claude-plugins-official) |
| `cloudflare-mcp` | `cloudflare` (claude) | [cloudflare/skills](https://github.com/cloudflare/skills) |

## 내 skill 추가하기

1. `sources/skills/<이름>/SKILL.md`를 만듭니다. 원본은 하나만 두고 Claude Code와 Codex 둘 다 설치합니다(SSOT). 하네스마다 다른 부분(스크립트 경로, 질문·서브에이전트 도구)은 본문에 양쪽을 다 적습니다(예: `{스킬폴더}/scripts/...`, `lost-me`·`research-proposal`의 "하네스별 실행"). 목적 자체가 한쪽 전용인 skill(예: Codex에서 Claude 명령을 쓰게 하는 `claude-command-library`)만 폴더 이름에 `-claude`/`-codex`를 붙입니다.
2. `catalog.json`의 `packages`에 항목을 추가합니다. 예:
   ```json
   {"id": "my-skill", "group": "mine", "title": "my-skill", "description": "…",
    "items": [{"harness": "claude", "dest": "skills/my-skill", "src": "sources/skills/my-skill"},
              {"harness": "codex",  "dest": "skills/my-skill", "src": "sources/skills/my-skill"}]}
   ```
3. `python3 install.py install my-skill`을 실행합니다. symlink 방식이라 이후 원본을 고치면 바로 반영됩니다.

외부 skill은 `source`(repo, 40자 커밋 SHA, license)와 함께 다음 중 하나로 적습니다.
- `skills`: 개별 경로
- `skills_glob`: 폴더 하나 아래 전부
- `files_glob`: command 같은 파일 묶음
- `file_map`: 파일 하나를 특정 위치로
- `mcp`: MCP 서버를 `claude mcp add` / `codex mcp add`로 등록합니다. 필요한 CLI가 없으면 설치 명령만 안내하고 건너뜁니다.

## 플랫폼 상태

- **macOS**: 검증 완료. Python 3.9.6과 3.13에서 테스트 9개가 통과했고, 실제 홈 마이그레이션까지 마쳤습니다.
- **Linux**: 같은 코드 경로(POSIX symlink)를 씁니다. 아직 실제 검증은 하지 않았습니다.
- **Windows**: copy 모드가 기본입니다. `install.ps1` 포함, 아직 검증하지 않았습니다.

```bash
python3 -m unittest discover -s tests -v                                   # 로컬 테스트
AGENT_SKILLS_NETWORK_TESTS=1 python3 -m unittest discover -s tests -v      # + GitHub에서 받아 오기 테스트
```

## 주의

skill은 에이전트에게 코드 실행, 패키지 설치, 네트워크 요청을 시킬 수 있습니다. 외부 skill은 원작자 repo의 `SKILL.md`와 `scripts/`를 읽어 보고 필요한 것만 설치하세요. 외부 skill과 plugin의 저작권과 라이선스는 각 원작자에게 있습니다. `document-skills`는 Anthropic 자체 라이선스라서 이 저장소에 포함하지 않고, 설치하는 사람의 기기에서 Anthropic repo로부터 직접 받습니다.
