# iCloud 저장소 이동 · 기존 홈 자산 조사 인계

상태: 실행 검증 완료 — 이 카드의 저장소 이동·읽기 전용 inventory 단계만 완료. 상위 symlink SSOT 전환/중복 제거/새 setup/최종 release는 미완료다.
카드: t_8f75d661 / 보드: agent-skills / run: 53 / 담당: arena-operator / 다음: dev-engineer t_56a6df31 (보드 재배정 readback 반영).
모델: gpt-6.1-sol / openai-codex. 유료 모델 실험·GitHub push·launchd 변경 없음.
이 작업은 agent-skills 운영 작업이며 LLM Squid Game 게임 rubric 합격 판정이 아니다.

## 1. 실제 이동 결과
- 원본: `/Users/bagjuhyeon/Library/Mobile Documents/com~apple~CloudDocs/Workspace/agent-skills`
- 현재: `/Users/bagjuhyeon/Workspace/agent-skills`
- branch: `setup/plugin-layout` / HEAD: `4e32046a17d8832c15ed69925cc6e8f1dd8dd9d5`
- origin: `https://github.com/irregular6612/agent-skills.git`. fetch refspec, refs 3개, stash 빈 목록 동일.
- 전후 25,468 entries / 22,503 files / 598,732,128 bytes. .git·ignored/untracked 파일도 포함.
- .icloud 파일명 및 macOS SF_DATALESS(0x40000000) 전수 검사: 0. 해시 계산 전에 확인; 다운로드 안 된 항목을 성공으로 간주하지 않음.
- 전체 상대경로·종류·size·SHA-256·mode·mtime·symlink target 동일. inode/device는 복사에 따라 달라지므로 비교에서 제외.
- `git fsck --full` 전후 exit 0; 기존 dangling blob `cf9899e8701ab6aa8d320f1e34596f5b8efb97d0` 1개는 동일하게 남음. 손상/새 결함으로 보고하지 않음.
- 이동 직후 `git status --porcelain=v1 --untracked-files=all`: clean. 보고서 추가 이후 `docs/`만 새 untracked 산출물이어야 한다.
- 최종 재검사에서 일반 git status/diff 이후 `.git/index` 1개의 stat-cache refresh가 관찰됐다. 이동 직후 snapshot에서는 index 포함 모든 파일 bytes가 동일했다. 최종 index byte SHA는 달라졌지만 `git ls-files --stage -z`와 `git ls-tree -r -z HEAD`의 433개 mode/object/path가 정확히 일치하고 staged/working diff도 없다. 최초 최종-test 시도는 10개 중 이 byte 검사 1개 실패였으며 INDEX-REFRESH-READBACK.json에 보존했다. 최종 불변 파일 검사와 가변 index 의미 검사를 분리한다. 이후 Git 검사는 GIT_OPTIONAL_LOCKS=0으로 실행했다.
- 구 iCloud 경로는 새 저장소를 가리키는 absolute symlink. 로컬 resolve 및 구 경로 git HEAD readback PASS. 다른 기기의 iCloud 링크 동기화/이동 대상 존재 여부는 미검증이며 휴대용 설치 경로로 간주하지 않음.
- 기존 .DS_Store·.venv·외부 reference 등도 전체 이동 요구 때문에 보존. 새 SSOT의 공개/패키징 대상으로 승인한 것이 아니므로 다음 단계에서 포함 금지 정책을 따로 적용해야 한다.

### 실행 명령과 대안 경로
모든 Python 스크립트는 이 카드 workspace에서 실행했다. 스크립트와 raw digest manifest는 EVIDENCE.zip에 있다.
- `python3 repo_audit.py before` → exit 0: 전수 baseline·Git 검사.
- `python3 move_repo.py` → exit 1: iCloud File Provider os.rename errno 11 EDEADLK; 실제 이동 없음.
- `ditto --rsrc --extattr --acl "/Users/bagjuhyeon/Library/Mobile Documents/com~apple~CloudDocs/Workspace/agent-skills" "/Users/bagjuhyeon/Workspace/agent-skills"` → exit 0: 원본 유지 상태에서 .git 포함 전체 복사.
- `python3 repo_audit.py after` → exit 0: 새 경로 전수·Git 검사.
- `python3 finalize_move.py (첫 시도)` → exit 1: symlink 7개의 mtime 차이 발견, 원본 정리 전 fail-closed.
- `python3 finalize_move.py (timestamp 복원 후)` → exit 0: 새 위치 symlink mtime만 원래 값 복원; 전 파일 재검증 후 구 사본 정리·호환 링크 생성.
- `python3 home_inventory.py` → exit 0: 허용된 자산 파일 digest·경로·소유 분류.
- `python3 native_inventory.py` → exit 0: 양 native plugin list 안전 메타데이터.
- `python3 verify_inventory.py` → exit 0: 507/507·850/850 전체 managed readback.
- ditto는 ACL/resource fork/xattr 보존 옵션으로 실행했으나 해당 속성별 독립 전후 digest 검사는 하지 않았다. 파일 bytes/mode/mtime/링크·Git 보존은 별도 실제 검사했다.

## 2. 홈 자산 inventory
- claude/skills: 41
- claude/agents: 36
- claude/commands: 2
- codex/skills: 36
- codex/agents: 34
- 총 직접 자산 149개. .system/.remember/.trash/synced 등은 별도 metadata-only 보존 대상으로 분리했다. nested Claude agent 폴더는 상위 자산 1개이며 동봉 파일별 digest는 JSON에 있다.
- Codex commands/prompts 및 Claude prompts 디렉터리는 현재 없음. Codex claude-command-library/claude-subagent-library는 reference adapter이며 native 명령/agent 등록과 동일하지 않다.
- 기존 자산 entrypoint symlink broken 0. 전체 시스템 모든 링크 0을 주장하지 않으며 nested safe-scope links는 JSON tree.nested_symlinks에서 구분한다.
- t_263e9531 state의 Claude 507/507, Codex 850/850 파일 digest가 모두 원래 rendered_sha256와 일치한다. asset별 asset_ids, managed 파일 수/일치 수 포함. copied managed 상태를 symlink로 바꾸지 않았다.
- state: `/Users/bagjuhyeon/.hermes/kanban/boards/agent-skills/workspaces/t_263e9531/release/state.json` / SHA-256 `c28718e50e25c7576ed556e3ba2b898fb51ac1f6cb6a190456b02208cb358e3e`
- 중요: 이 기존 copy 상태의 native owned source/marketplace는 t_263e9531 scratch workspace를 참조한다. 새 setup은 durable repo 기반 경로로 이관해야 하며 현재 scratch 의존을 장기 안정성으로 승인하지 않는다.

### 소유/출처 판정 규칙과 분류
원본 README의 claude-code/juhyeon 소유 선언 + exact 원본 파일/SKILL.md hash match는 user_owned로 분류한다. Codex mirror라는 사실만으로 저작권/사용자 저작을 확정하지 않는다. approved manifest에 들어간 자산은 user_packaged_managed로 구분하며 이것은 사용자 저작 증거가 아니다. 외부 installer lock·외부 reference match는 external_dependency, 근거가 부족하면 undetermined로 보존한다.
- undetermined: 8
- user_owned: 18
- excluded_preserve: 1
- external_dependency: 14
- user_packaged_managed: 108

판단 불가 — 모두 유지; 이 조사에서 삭제·흡수·출처 확정 안 함:
- `/Users/bagjuhyeon/.claude/skills/agentcat-usage`
- `/Users/bagjuhyeon/.claude/skills/hermes-codex-turn-timeout-patch`
- `/Users/bagjuhyeon/.claude/skills/lost-me`
- `/Users/bagjuhyeon/.claude/agents/lost-me-auditor.md`
- `/Users/bagjuhyeon/.claude/agents/lost-me-judge-academic.md`
- `/Users/bagjuhyeon/.claude/agents/lost-me-judge-humanness.md`
- `/Users/bagjuhyeon/.claude/agents/lost-me-judge-readability.md`
- `/Users/bagjuhyeon/.claude/agents/lost-me-writer.md`
hermes-codex-turn-timeout-patch는 기존 inventory에서도 local runtime patch로 portable SSOT에서 제외했다. 이 프로필/다른 Hermes 봇 설정은 수정하지 않았다.

### ~/.agents와 ~/.agentcat 링크
- `/Users/bagjuhyeon/.claude/skills/agentcat-usage` → `/Users/bagjuhyeon/.agentcat/connectors/skills/agentcat-usage` / undetermined / 출처/저작 판단 불가
- `/Users/bagjuhyeon/.claude/skills/brandkit` → `../../.agents/skills/brandkit` / external_dependency / Leonxlnx/taste-skill :: skills/brandkit/SKILL.md
- `/Users/bagjuhyeon/.claude/skills/design-taste-frontend` → `../../.agents/skills/design-taste-frontend` / external_dependency / Leonxlnx/taste-skill :: skills/taste-skill/SKILL.md
- `/Users/bagjuhyeon/.claude/skills/full-output-enforcement` → `../../.agents/skills/full-output-enforcement` / external_dependency / Leonxlnx/taste-skill :: skills/output-skill/SKILL.md
- `/Users/bagjuhyeon/.claude/skills/image-to-code` → `../../.agents/skills/image-to-code` / external_dependency / Leonxlnx/taste-skill :: skills/image-to-code-skill/SKILL.md
- `/Users/bagjuhyeon/.claude/skills/industrial-brutalist-ui` → `../../.agents/skills/industrial-brutalist-ui` / external_dependency / Leonxlnx/taste-skill :: skills/brutalist-skill/SKILL.md
- `/Users/bagjuhyeon/.claude/skills/minimalist-ui` → `../../.agents/skills/minimalist-ui` / external_dependency / Leonxlnx/taste-skill :: skills/minimalist-skill/SKILL.md
- `/Users/bagjuhyeon/.claude/skills/redesign-existing-projects` → `../../.agents/skills/redesign-existing-projects` / external_dependency / Leonxlnx/taste-skill :: skills/redesign-skill/SKILL.md
- Leonxlnx/taste-skill의 원래 skillPath 이름(taste-skill/output-skill/brutalist-skill 등)과 설치 명칭이 다른 alias mapping을 JSON에 남겼다. skillFolderHash는 installer 관찰값이며 immutable Git commit으로 검증한 값이 아니다. 외부 의존성 lock의 ref/commit/license 확정은 engineer/verifier 단계에서 수행해야 한다.
- agentcat-usage는 양쪽 entrypoint/tree가 같지만 agentcat 소프트웨어/런타임 외부 의존성 및 저작 출처는 미확정. .agentcat의 DB/로그/token/state를 repo로 가져오지 않는다.

## 3. 중복과 Claude/Codex 차이
- 실제 native list: Claude 20개, Codex 30개; 양 명령 exit 0. 등록·목록 관찰이며 실제 skill/agent 실행·인증 검증 아님.
- claude superpowers:
  - `superpowers@claude-plugins-official` 6.4.1 enabled=True
  - `superpowers@generated-local-cache` 6.4.1 enabled=True
  - 기존 lock 관찰 pin: `v6.4.1`, commit `5bf4e78011075bcfc0dc295f0724994cd123ee71`, tag object `b92c4fa87ea1252077a7f7d3bf420e52325dd25e`. generated-local-cache가 해당 managed pin 등록; 외부 레지스트리를 제거하지 않았다.
- codex superpowers:
  - `superpowers@generated-local-cache` 6.4.2 enabled=True
  - `superpowers@openai-curated-remote` 6.4.2 enabled=True
  - 기존 lock 관찰 pin: `v6.4.2`, commit `8ca22dba9a94f28898bbce59f2537ff4d87c747d`, tag object `668b16d4d8d4d603fd257567684fbbffccbf2022`. generated-local-cache가 해당 managed pin 등록; 외부 레지스트리를 제거하지 않았다.
- 같은 이름 직접 skill 19개 중 SKILL.md와 safe scoped tree가 동일한 것은 4개, SKILL.md가 다른 것은 15개. hash/공통·전용/변경 파일 목록은 HOME-INVENTORY.json parity 참조.
- 직접 활성 skill roots에서 서로 다른 이름의 exact SKILL.md·frontmatter 제거 body 중복 그룹은 발견되지 않았다. plugin payload cache 전체의 skill alias 동일성은 검사하지 않았으므로 전 시스템 중복 0을 주장하지 않는다.
- 같은 이름이라도 user data/support file 차이가 있는 경우 삭제/덮어쓰기 금지. 파일 mtime는 copied/rendered 시간을 반영할 수 있으므로 최신판 결정 근거가 아니다. 현재 rendered state는 승인된 기존 candidate provenance와 exact digest로 확인했지만, 서로 다른 원문을 하나로 합치는 결정은 다음 담당자가 내용·harness contract를 검토해야 한다.

| Skill | SKILL.md 동일 | scoped tree 동일 | 변경 파일 수 |
|---|---|---|---|
| agentcat-usage | True | True | 0 |
| autoskill | False | False | 1 |
| citation-management | False | False | 1 |
| humanize | False | False | 9 |
| hwpx | False | False | 1 |
| iterative-academic-writer | False | False | 6 |
| latex-posters | False | False | 1 |
| latex-publication | False | False | 21 |
| literature-review | False | False | 1 |
| markdown-mermaid-writing | False | False | 1 |
| paper-banana | False | False | 7 |
| paper-digest | False | False | 1 |
| paper-driller | False | False | 4 |
| paper-readability-review | False | False | 2 |
| paper-section-rewrite | False | False | 1 |
| peer-review | False | False | 1 |
| scientific-schematics | True | True | 0 |
| scientific-slides | True | True | 0 |
| scientific-writing | True | True | 0 |
차이의 의미: humanize/latex-publication은 agent·command semantics, paper-banana는 engine/config, iterative-academic-writer는 eval/reference 변경을 포함한다. 차이를 단지 이름 adapter라고 확정하지 않았다.

## 4. 전역 지침·설정·denylist
- `/Users/bagjuhyeon/.claude/CLAUDE.md`: file / SHA-256 `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`
- `/Users/bagjuhyeon/.claude/settings.json`: file / SHA-256 `21c2eae495aa0bd1b4c08da62e4ee0484ff577f3774b3369fe027ed8b821d130`
- `/Users/bagjuhyeon/.claude/settings.local.json`: file / SHA-256 `64f554cd37b972acf262cdc156d7e244382dd8a2c03e8319d3635fb3255d7786`
- `/Users/bagjuhyeon/.claude/.ssot-lock.json`: file / SHA-256 `6cc7b3a8a16eed5ced7d2d8a63c3684878621902e1c29053b2e9799fc48f8ce2`
- `/Users/bagjuhyeon/.claude/.claude-plugin/plugin.json`: file / SHA-256 `1ff310b743b8b0e8d8b114af0dc119b7f51d3b9ada2a39fc808e3833634b891d`
- `/Users/bagjuhyeon/.claude/plugins/known_marketplaces.json`: file / SHA-256 `fc30701169c5216d60817e97eeb7c7cf4e2d2c5565b5ed41bf0066082d8a51e9`
- `/Users/bagjuhyeon/.claude/plugins/installed_plugins.json`: file / SHA-256 `dae7281293f0482d5c3a7aa22cc2b86e5ef74e6ae9c554c589570274cdc3f8c9`
- `/Users/bagjuhyeon/.claude/plugins/config.json`: file / SHA-256 `ad5cad4f50e8180bd74a9bf743f1724da735d13ab7163841a93ae41e4b7de0e5`
- `/Users/bagjuhyeon/.claude/plugins/blocklist.json`: file / SHA-256 `bcddf957baf119b907fbc531a752da35b669f9d09ed59578d77abd487a82efd2`
- `/Users/bagjuhyeon/.codex/AGENTS.md`: file / SHA-256 `b1979127c731935573213a111cc0e38ec88b98c1dce7ae0969d67ce52af22163`
- `/Users/bagjuhyeon/.codex/config.toml`: file / SHA-256 `589c68ff35ee256cee38a762e3c956955645e4fc946342d978a6770903cc3ab4`
- `/Users/bagjuhyeon/.codex/.ssot-lock.json`: file / SHA-256 `e0acc2547f858f02e152c9ad813de8f3749452aec7adc299614b6a059a20c784`
- `/Users/bagjuhyeon/.codex/.codex-plugin/plugin.json`: file / SHA-256 `aa8d0885204832bdf3d0862f31dd0330222ab9621b4673410374dc55d01e7846`
- settings/config 원문 값은 보고서에 쓰지 않았다. top-level key와 허용된 enabled plugin/agent config path만 기록. env/MCP/project trust/provider 등 private/machine 값은 export하지 않았다. hooks/permissions/enabled plugins/marketplace의 template 범위는 다음 작업에서 백업 후 병합; 이 카드는 병합/링크 변경 안 함.
- native list 전후 추적 config/registry 파일 digest가 모두 동일하다. HOME-INVENTORY에 전역 지침·settings/config·registry digest와 metadata baseline을 기록했다.
- denylist 보존: matt-pocock / mattpocock-skills / matt-potcock / mattpocock / auto-code. 기존 mattpocock-skills@claude-plugins-official 1.2.3 및 ~/.claude/skills/auto-code는 원래 외부 상태로 남겨 두었다. denylist는 새 SSOT import/install 제외이며 기존 사용자의 자산을 이 카드에서 지우라는 뜻이 아니다.
- plugin cache는 marketplace/plugin/version/path metadata만 수집. credentials/auth/history/sessions/projects-memory/logs/sqlite 및 cache payload를 수집·복사·vendoring하지 않았다.

## 5. 다음 담당자와 복원 안내
- durable corrective archive: `/Users/bagjuhyeon/.hermes/kanban/boards/agent-skills/attachments/t_064fc190/project-corrective-t064fc190.tar.gz`, SHA-256 `e719092b967e330253d7c776c538ed2fbb3cb08df592749d734d1ec7bee012c2`. 같은 카드 attachment의 FINAL-HANDOFF.md SHA-256 `f93ce9264e8618a81ea3c2c4c2e1345e8fde03def3a40b83f96aacdb07d80960`. 이 run에서 두 파일 hash를 재확인했다. scratch 경로가 정리되면 이 durable attachment를 사용한다.
- dev-engineer t_56a6df31: 이 보고서·JSON을 읽고 새 위치 repo 사본에서 item symlink setup을 구현한다. 기존 최신 canonical snapshot은 t_263e9531 candidate/sources 및 t_064fc190 corrective archive; 이동된 원본 repo에는 그 snapshot을 이번 카드에서 통합하지 않았다. 원본 README의 Codex plugin 부재 설명은 현재 CLI 관찰과 충돌하므로 새 문서를 실제 CLI 기준으로 갱신해야 한다.
- 독립 verifier와 실제-home operator 후속 카드는 이미 root t_5703b727 그래프에 있음. 이 조사 카드에서는 홈 migration/중복 삭제/정기 작업/공개 게시/commit/push를 시작하지 않는다.
- 이동 되돌리기: 현재 구 경로가 정확히 NEW를 가리키는 링크임을 확인한 뒤 링크만 해제하고, NEW 전체를 OLD로 되돌린다. iCloud rename이 재차 EDEADLK면 동일 ditto→전 파일·Git 검증→검증된 source 정리 순서를 사용한다. 새 repo에 후속 수정이 생긴 뒤에는 예전 baseline으로 복원하지 말고 현재 전체를 보존해야 한다. 자동 rollback은 실행 안 함.
- 기존 홈 copy 설치 복구 근거: `/Users/bagjuhyeon/.hermes/kanban/boards/agent-skills/workspaces/t_263e9531/release/backups/0.1.0` 및 state.json. 이 카드에서 backup/registry/state를 수정하지 않았다.
- 미검증: iCloud 다른 기기 링크 동기화, ACL/xattr의 독립 동일성, plugin payload 전체 alias 비교, 모든 skill/agent/hook/MCP 실제 실행, 출처 판단 불가 자산 저작, 새 setup/새 HOME/최종 release. 한계를 기록했다고 상위 목표 PASS로 처리하지 않는다.

## 부록: 직접 자산별 분류
| Harness | Category/name | Kind | Ownership | managed matched/records |
|---|---|---|---|---|
| claude | skills/agentcat-usage | symlink | undetermined | 0/0 |
| claude | skills/aha | directory | user_owned | 3/3 |
| claude | skills/auto-code | directory | excluded_preserve | 0/0 |
| claude | skills/autoresearch | directory | user_owned | 6/6 |
| claude | skills/autoskill | directory | external_dependency | 15/15 |
| claude | skills/book-qa-note | directory | user_packaged_managed | 3/3 |
| claude | skills/brandkit | symlink | external_dependency | 0/0 |
| claude | skills/citation-management | directory | user_packaged_managed | 16/16 |
| claude | skills/design-taste-frontend | symlink | external_dependency | 0/0 |
| claude | skills/ditto-writer | directory | user_packaged_managed | 25/25 |
| claude | skills/eli5 | directory | user_packaged_managed | 2/2 |
| claude | skills/full-output-enforcement | symlink | external_dependency | 0/0 |
| claude | skills/gist-library-room-booking | directory | user_packaged_managed | 2/2 |
| claude | skills/hermes-codex-turn-timeout-patch | directory | undetermined | 0/0 |
| claude | skills/humanize | directory | user_owned | 0/0 |
| claude | skills/hwpx | directory | user_packaged_managed | 13/13 |
| claude | skills/image-to-code | symlink | external_dependency | 0/0 |
| claude | skills/industrial-brutalist-ui | symlink | external_dependency | 0/0 |
| claude | skills/iterative-academic-writer | directory | user_owned | 11/11 |
| claude | skills/korean-scholarship-search | directory | user_packaged_managed | 8/8 |
| claude | skills/latex-posters | directory | user_packaged_managed | 13/13 |
| claude | skills/latex-publication | directory | user_packaged_managed | 57/57 |
| claude | skills/literature-review | directory | user_packaged_managed | 9/9 |
| claude | skills/lost-me | directory | undetermined | 0/0 |
| claude | skills/markdown-mermaid-writing | directory | user_packaged_managed | 37/37 |
| claude | skills/minimalist-ui | symlink | external_dependency | 0/0 |
| claude | skills/notebooklm | directory | user_packaged_managed | 1/1 |
| claude | skills/paper-banana | directory | user_owned | 107/107 |
| claude | skills/paper-digest | directory | user_owned | 2/2 |
| claude | skills/paper-driller | directory | user_packaged_managed | 21/21 |
| claude | skills/paper-radar | directory | user_packaged_managed | 6/6 |
| claude | skills/paper-readability-review | directory | user_owned | 4/4 |
| claude | skills/paper-section-rewrite | directory | user_owned | 7/7 |
| claude | skills/paper-understand | directory | user_owned | 7/7 |
| claude | skills/peer-review | directory | user_packaged_managed | 5/5 |
| claude | skills/redesign-existing-projects | symlink | external_dependency | 0/0 |
| claude | skills/research-grants | directory | user_packaged_managed | 12/12 |
| claude | skills/research-proposal | directory | user_packaged_managed | 6/6 |
| claude | skills/scientific-schematics | directory | external_dependency | 6/6 |
| claude | skills/scientific-slides | directory | external_dependency | 24/24 |
| claude | skills/scientific-writing | directory | external_dependency | 31/31 |
| claude | agents/academic-planner | file | user_packaged_managed | 1/1 |
| claude | agents/academic-reviewer | file | user_packaged_managed | 1/1 |
| claude | agents/academic-writing-assistant | file | user_packaged_managed | 1/1 |
| claude | agents/claude-for-dslab | directory | user_packaged_managed | 4/4 |
| claude | agents/code-cleanup-optimizer | file | user_packaged_managed | 1/1 |
| claude | agents/code-reviewer | file | user_packaged_managed | 1/1 |
| claude | agents/debugger | file | user_packaged_managed | 1/1 |
| claude | agents/execution-logger | file | user_packaged_managed | 1/1 |
| claude | agents/experiment-interpreter | file | user_packaged_managed | 1/1 |
| claude | agents/experiment-verifier | file | user_packaged_managed | 1/1 |
| claude | agents/humanize-fidelity-auditor | symlink | user_owned | 0/0 |
| claude | agents/humanize-ko-detector | symlink | user_owned | 0/0 |
| claude | agents/humanize-ko-monolith | symlink | user_owned | 0/0 |
| claude | agents/humanize-ko-rewriter | symlink | user_owned | 0/0 |
| claude | agents/humanize-naturalness-reviewer | symlink | user_owned | 0/0 |
| claude | agents/humanize-taxonomist | symlink | user_owned | 0/0 |
| claude | agents/humanize-web-architect | symlink | user_owned | 0/0 |
| claude | agents/lost-me-auditor | symlink | undetermined | 0/0 |
| claude | agents/lost-me-judge-academic | symlink | undetermined | 0/0 |
| claude | agents/lost-me-judge-humanness | symlink | undetermined | 0/0 |
| claude | agents/lost-me-judge-readability | symlink | undetermined | 0/0 |
| claude | agents/lost-me-writer | symlink | undetermined | 0/0 |
| claude | agents/modular-code-architect | file | user_packaged_managed | 1/1 |
| claude | agents/paper-comparison | file | user_packaged_managed | 1/1 |
| claude | agents/paper-digest-composer | file | user_packaged_managed | 1/1 |
| claude | agents/paper-evidence | file | user_packaged_managed | 1/1 |
| claude | agents/paper-meta | file | user_packaged_managed | 1/1 |
| claude | agents/paper-preread-analyst | file | user_packaged_managed | 1/1 |
| claude | agents/paper-section-driller | file | user_packaged_managed | 1/1 |
| claude | agents/paper-spine | file | user_packaged_managed | 1/1 |
| claude | agents/report-planner | file | user_packaged_managed | 1/1 |
| claude | agents/report-reviewer | file | user_packaged_managed | 1/1 |
| claude | agents/security-reviewer | file | user_packaged_managed | 1/1 |
| claude | agents/spec-bridge | file | user_packaged_managed | 1/1 |
| claude | agents/task-planner-analyzer | file | user_packaged_managed | 1/1 |
| claude | agents/test-writer | file | user_packaged_managed | 1/1 |
| claude | commands/humanize-redo | file | user_owned | 1/1 |
| claude | commands/humanize | file | user_owned | 1/1 |
| codex | skills/agentcat-usage | directory | user_packaged_managed | 1/1 |
| codex | skills/autoskill | directory | user_packaged_managed | 15/15 |
| codex | skills/citation-management | directory | user_packaged_managed | 16/16 |
| codex | skills/claude-command-library | directory | user_packaged_managed | 14/14 |
| codex | skills/claude-subagent-library | directory | user_packaged_managed | 41/41 |
| codex | skills/cloudflare | directory | user_packaged_managed | 320/320 |
| codex | skills/cloudflare-email-service | directory | user_packaged_managed | 6/6 |
| codex | skills/cloudflare-one | directory | user_packaged_managed | 1/1 |
| codex | skills/cloudflare-one-migrations | directory | user_packaged_managed | 1/1 |
| codex | skills/durable-objects | directory | user_packaged_managed | 4/4 |
| codex | skills/humanize | directory | user_packaged_managed | 16/16 |
| codex | skills/hwpx | directory | user_packaged_managed | 13/13 |
| codex | skills/iterative-academic-writer | directory | user_packaged_managed | 10/10 |
| codex | skills/latex-posters | directory | user_packaged_managed | 13/13 |
| codex | skills/latex-publication | directory | user_packaged_managed | 52/52 |
| codex | skills/literature-review | directory | user_packaged_managed | 9/9 |
| codex | skills/markdown-mermaid-writing | directory | user_packaged_managed | 37/37 |
| codex | skills/paper-banana | directory | user_packaged_managed | 107/107 |
| codex | skills/paper-digest | directory | user_packaged_managed | 1/1 |
| codex | skills/paper-driller | directory | user_packaged_managed | 14/14 |
| codex | skills/paper-readability-review | directory | user_packaged_managed | 4/4 |
| codex | skills/paper-section-rewrite | directory | user_packaged_managed | 7/7 |
| codex | skills/pdf | directory | user_packaged_managed | 12/12 |
| codex | skills/peer-review | directory | user_packaged_managed | 5/5 |
| codex | skills/pptx-posters | directory | user_packaged_managed | 8/8 |
| codex | skills/sandbox-migrate-to-next | directory | user_packaged_managed | 1/1 |
| codex | skills/sandbox-next | directory | user_packaged_managed | 3/3 |
| codex | skills/sandbox-stable | directory | user_packaged_managed | 1/1 |
| codex | skills/scientific-schematics | directory | external_dependency | 6/6 |
| codex | skills/scientific-slides | directory | external_dependency | 24/24 |
| codex | skills/scientific-writing | directory | external_dependency | 31/31 |
| codex | skills/turnstile-spin | directory | user_packaged_managed | 13/13 |
| codex | skills/web-perf | directory | user_packaged_managed | 1/1 |
| codex | skills/weekly-report-writer | directory | user_packaged_managed | 1/1 |
| codex | skills/workers-best-practices | directory | user_packaged_managed | 3/3 |
| codex | skills/wrangler | directory | user_packaged_managed | 1/1 |
| codex | agents/academic-planner | file | user_packaged_managed | 1/1 |
| codex | agents/academic-reviewer | file | user_packaged_managed | 1/1 |
| codex | agents/academic-writing-assistant | file | user_packaged_managed | 1/1 |
| codex | agents/code-cleanup-optimizer | file | user_packaged_managed | 1/1 |
| codex | agents/code-reviewer | file | user_packaged_managed | 1/1 |
| codex | agents/debugger | file | user_packaged_managed | 1/1 |
| codex | agents/execution-logger | file | user_packaged_managed | 1/1 |
| codex | agents/experiment-interpreter | file | user_packaged_managed | 1/1 |
| codex | agents/experiment-verifier | file | user_packaged_managed | 1/1 |
| codex | agents/humanize-fidelity-auditor | file | user_packaged_managed | 1/1 |
| codex | agents/humanize-ko-detector | file | user_packaged_managed | 1/1 |
| codex | agents/humanize-ko-monolith | file | user_packaged_managed | 1/1 |
| codex | agents/humanize-ko-rewriter | file | user_packaged_managed | 1/1 |
| codex | agents/humanize-naturalness-reviewer | file | user_packaged_managed | 1/1 |
| codex | agents/humanize-taxonomist | file | user_packaged_managed | 1/1 |
| codex | agents/humanize-web-architect | file | user_packaged_managed | 1/1 |
| codex | agents/md-fragment-converter-coordinator | file | user_packaged_managed | 1/1 |
| codex | agents/md-tex-injection-planner | file | user_packaged_managed | 1/1 |
| codex | agents/modular-code-architect | file | user_packaged_managed | 1/1 |
| codex | agents/paper-comparison | file | user_packaged_managed | 1/1 |
| codex | agents/paper-digest-composer | file | user_packaged_managed | 1/1 |
| codex | agents/paper-evidence | file | user_packaged_managed | 1/1 |
| codex | agents/paper-meta | file | user_packaged_managed | 1/1 |
| codex | agents/paper-section-driller | file | user_packaged_managed | 1/1 |
| codex | agents/paper-spine | file | user_packaged_managed | 1/1 |
| codex | agents/portfolio-chart | file | user_packaged_managed | 1/1 |
| codex | agents/portfolio-fundamentals | file | user_packaged_managed | 1/1 |
| codex | agents/portfolio-news | file | user_packaged_managed | 1/1 |
| codex | agents/report-planner | file | user_packaged_managed | 1/1 |
| codex | agents/report-reviewer | file | user_packaged_managed | 1/1 |
| codex | agents/security-reviewer | file | user_packaged_managed | 1/1 |
| codex | agents/task-planner-analyzer | file | user_packaged_managed | 1/1 |
| codex | agents/test-writer | file | user_packaged_managed | 1/1 |
| codex | agents/tex-fragment-format-auditor | file | user_packaged_managed | 1/1 |
