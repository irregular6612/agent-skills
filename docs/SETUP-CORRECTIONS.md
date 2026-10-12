# setup 수정 결정 — t_ce71121d

이 문서는 t_70718ee6의 REVISE(F1–F4)에 대한 구현 결정이다. 구현 자체 검증은 실제 HOME 적용 승인이나 독립 검증 PASS를 대신하지 않는다.

## F1: TOML 편집 범위

Python 3.9 stdlib의 대상 필드 편집기와 Python 3.12 tomllib 검증 경로에 동일한 preflight를 적용한다. `[agents.debugger]` 아래 `'config_file' = 'custom-local.toml'`은 정상 병합한다. 관리 필드의 dotted assignment, inline parent table, array table, scalar를 table로 선언한 형태, multiline target value는 명시적으로 거부한다. 에러는 link/config/journal/native CLI 쓰기 전에 발생한다. 독립 Python 3.12 tomllib oracle로 입력/출력 구문을 검사하고, 실패는 HOME snapshot 무변경을 확인한다. Python 3.9의 전체 임의 TOML 구문 검사기라는 주장은 하지 않는다. 관리 밖 dotted/inline table와 리터럴 점이 포함된 quoted key는 보존한다.

## F2: portable destination 정책

manifest destination의 Unicode NFD 정규화 + casefold 결과에서 동일 경로와 부모/자식 중첩을 거부한다. 파일시스템 probe 없이 쓰기 전 수행하므로 잘못된 manifest로 인한 HOME 변경은 0이다. 대소문자를 구별하는 파일시스템에서도 이식 가능한 계약을 위해 더 엄격하게 거부한다. 각 harness는 별도 namespace이다.

## F3: Claude agent 정의 통합과 분리

본문은 native frontmatter 종료 구분자 다음의 전체 문자열로 비교했다. 이름/description만 다르고 다음 본문들은 byte-identical이다.

| 기존 DSLab alias | canonical runtime name | 본문 비교 |
| --- | --- | --- |
| agents/claude-for-dslab/academic-planner.md | academic-planner | 동일, 277줄 |
| agents/claude-for-dslab/report-planner.md | report-planner | 동일, 162줄 |
| agents/claude-for-dslab/report-reviewer.md | report-reviewer | 동일, 233줄 |

위 3개는 manifest `links`에서 제외하고 `retired_links`로 명시했다. 기존 설치에 alias 파일이 있는 경우 승인된 원본 bytes와 같을 때만 백업·retire하고 uninstall 때 복원한다. 사용자 수정본은 쓰기 전 거부한다. 이전 journal이 소유한 alias symlink를 retire할 때도 원래 사용자 백업을 유지한다. source snapshot은 provenance/회귀 비교 자료로 남겨 두며 활성 설치 정의가 아니다.

`academic-reviewer`의 일반 버전은 21줄 본문으로 orchestrator가 제공한 critic protocol을 읽고 read-only 품질 평가만 수행한다. 도구는 Read/Grep/Glob이며 정식 Fact-Checker와 pass/fail 판정을 분리한다. DSLab 버전은 326줄 본문으로 자체 체크리스트·WebSearch 사실 검증·JSON 점수/pass를 포함한다. 두 계약을 임의로 최신판 하나로 합치지 않았다. DSLab의 native name은 `dslab-academic-reviewer`로 분리하고 manifest `native_name`도 기록했다. prompt 본문은 바꾸지 않았다. DSLab 전용 호출자는 새 이름을 사용해야 한다.

활성 manifest는 138 links이다. Claude skills 30, agents 31, commands 2, guideline 1, hooks 1; Codex skills 35, agents 34, reference prompts 2, guideline 1, hooks 1. 과거 141-link inventory는 당시 provenance이며 현재 개수의 기준이 아니다.

Claude SDK control initialize(no user turn)에서 31개 활성 name을 각각 한 번 찾았고 native description도 원본과 일치했다. Claude가 description의 리터럴 `\\n`을 줄바꿈으로 바꾸는 정규화만 비교에 반영했다. 따라서 파일/링크 개수만으로 정의 인식을 주장하지 않는다. Codex app-server `skills/list`와 `config/read`에서도 35 skills/34 roles를 확인했다. 실제 agent 수행과 hook 행동 검증은 아니다.

## F4: marketplace retirement와 복원

`ssot-pinned`를 먼저 설치/readback한 뒤 중복 plugin/cache를 retire한다. marketplace catalog가 superpowers/기존 managed plugin만 포함하고 관련 없는 installed plugin이 참조하지 않을 때만 등록을 해제한다. 이미 plugin이 제거된 dedicated catalog도 처리한다. mixed catalog, unrelated catalog/plugin, 소유권을 확인하지 못한 catalog는 유지한다.

Claude settings/installed_plugins/known_marketplaces와 Codex config를 기존 journal 백업으로 복원한다. native marketplace cache가 있다면 CLI의 재귀 삭제 전에 별도 move backup을 한다. 외부 local catalog source는 이동/편집하지 않는다. 설치 뒤 marketplace 목록에서 실제 부재를, uninstall 뒤 원래 이름/위치를 native readback한다. dry-run은 로컬 registry/catalog만 읽고 native CLI를 호출하지 않는다.

실제 양 CLI의 dedicated + mixed + unrelated fixture에서 superpowers pin만 하나 남기고 unrelated local plugin 두 개와 mixed/unrelated marketplace를 유지했으며 uninstall 뒤 원본 registry bytes 및 native 등록을 복원했다. native bootstrap/log/cache 빈 디렉터리는 사용자 원본 복원과 구분한다. `.system` sentinel 변경은 기존 verifier가 native Codex initialize 자체의 동작으로 분리한 예외를 유지한다.

## 재현

- `PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 -m unittest discover -s tests -p 'test_*.py' -v`
- `PYTHONDONTWRITEBYTECODE=1 python3.12 -m unittest discover -s tests -p 'test_*.py' -v`
- `PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 tests/live_native_duplicates.py`
- `PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 tests/live_native_marketplaces.py`
- `PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 tests/live_native_discovery.py`

전부 checkout의 `.test-tmp` 아래 fake HOME을 사용한다. public plugin network 설치는 있지만 유료 API/model turn은 없다. Python 3.9 회귀의 독립 TOML oracle은 PATH의 Python 3.12를 사용한다(없으면 oracle 포함 테스트를 명시적으로 skip). 실제 HOME·원본 repo·GitHub push·launchd는 범위 밖이다.
