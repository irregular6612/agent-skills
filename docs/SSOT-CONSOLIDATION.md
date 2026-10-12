# 공용 skill 통합 및 외부 pack 재현 — t_b8b0fced

이 문서는 승인 base `00030ea9861d6a126afd286abbe94ef1c3b77341` 이후의 구현 결정이다. 운영 HOME/repo 변경이나 독립 PASS, 전체 SSOT release 완료를 뜻하지 않는다. 실행 결과와 후보 HEAD는 별도 구현 보고서에 남긴다.

## 공용 원본과 현재 범위

canonical 경로는 `sources/skills/<native-skill-name>/`이다. 양 harness의 item link는 본문과 supporting assets를 같은 디렉터리에서 읽는다. 최종 목록과 개수는 `SYMLINK-INVENTORY.json`에 있다. 현재 155 item links이며 Claude skill37/agent34/command2/guideline1/hook1, Codex skill42/role34/reference prompt2/guideline1/hook1이다. 과거 141 및 승인 base138은 역사적 수치다.

공용 skill 25개:

- autoskill, citation-management, humanize, hwpx
- iterative-academic-writer, latex-posters, latex-publication, literature-review
- markdown-mermaid-writing, paper-banana, paper-digest, paper-driller
- paper-readability-review, paper-section-rewrite, peer-review
- scientific-schematics, scientific-slides, scientific-writing
- brandkit, design-taste-frontend, full-output-enforcement, image-to-code
- industrial-brutalist-ui, minimalist-ui, redesign-existing-projects

본래 15개 divergent source의 `-claude`/`-codex` 전체 snapshot은 제거했다. 기존 동일 scientific 3개는 유지했다. 기존 CLI 이름을 바꾸지 않았다. 공용 LaTeX supporting 역할 3개는 Claude native discovery에도 등록했으며 Codex의 기존 이름과 같다.

## 최신성·기능 선택 근거

`HARNESS-VARIANTS.json`은 항목별 결정과 base changed files를 기록한다. `<name>-BASE-DIFF.patch`는 승인 base의 양 snapshot 원문 diff다. Git import 날짜나 복사 mtime를 source 작성 날짜로 해석하지 않았다.

- description만 다른 항목은 도메인 본문과 supporting bytes가 동등하다. 축약 전 trigger 설명을 공통으로 보존했으며 시간상 최신이라고 주장하지 않는다.
- iterative writer: 명시 changelog의 v5.x 2026-07-22는 Codex v4.x 2026-06-01보다 뒤의 개정이다. 공통 `critic-review-protocol.md`, User-Attested/Unverifiable와 C1–C9/W1–W17 계약을 유지한다. Codex Critic의 구형 inline 평가표를 제거해 양 native consumer가 같은 protocol 절대경로를 읽는다.
- paper-driller: `legacy-workflow.md`가 pre-2026-09-22 v2를 명시적으로 보존하며 새 v3 template/manifest·13키 schema v4 계약을 도입한다. v2 노트를 일괄 변환하지 않는다. 공통 static 검사는 canonical references/template만 검사한다. 개인 vault 엔진·PyYAML·unmanaged frontmatter hook은 명시적 로컬 통합이며 새 기기 자동 설치를 주장하지 않는다.
- LaTeX: `engine-selection.md`와 `templates/latexmkrc`의 명시 개정이 구 고정 XeLaTeX/2025 계약을 대체한다. Codex의 구 compile/template은 initial `756141c` import와 같고 Claude resolver는 후속 개정이다. 하위 명령·bibliography·diagnostic도 프로젝트 설정 계약으로 맞췄다. legacy MD 독립 변환기는 XeLaTeX preamble/로컬 폰트 제한이 남으며 다른 엔진 지원이나 PDF 품질을 검증한 것은 아니다.
- PaperBanana: 본문의 명시 모델 개정 2026-07-30과 config.py slot map이 Codex 2026-05/June 설명 뒤의 개정을 입증한다. 해당 defaults를 보존했지만 현재 모델 가용성·가격·성능은 미검증이다. 개인 fork 경로를 새 기기 입력에서 제거했다.
- readability PDF: textbox overflow 재시도 및 전체 search-hit highlight라는 기능 diff를 선택했다. snapshot 작성 날짜 우열 대신 corrective merge임을 명시한다.
- Humanize: 경로/native model metadata를 제외한 공통 도메인 규칙을 보존했다. `summary.md`의 main orchestrator 소유권은 공통 protocol이다. 양 CLI의 runtime Write 차단을 보장한다는 복제 문구는 제거했다.

## 필요한 얇은 adapter

- Humanize 7역할 및 LaTeX 3역할: supporting domain 본문은 `sources/skills/.../agents/<role>.md` 한 곳이다. `sources/agents/*-claude.md`의 native frontmatter와 `*-codex.toml`의 native metadata만 harness별로 유지한다. consumer는 전달된 discovered SKILL_ROOT·본문·reference 절대경로를 먼저 읽는다. 전달이 없을 때만 해당 harness의 installed item 경로를 사용한다. 읽기 실패 시 중단한다.
- academic-reviewer: 양 native consumer는 전달된 `critic-review-protocol.md`를 읽는다. 채점표를 각 adapter에 복제하지 않는다.
- MCP: 같은 local PaperBanana command argv를 `claude mcp add --scope user --transport stdio ...`와 `codex mcp add ...`로 등록하는 구문만 다르다. setup이 등록하지 않는다. 등록 metadata readback은 서버 연결·유료 모델 실행 증거가 아니다.
- Claude commands는 Codex reference prompts이며 native command 실행 동등성을 주장하지 않는다. 실제 모델/agent/hook 행동은 discovery와 분리해 미검증이다.

## taste-skill immutable provenance와 설치

`dependencies/lock.yaml`과 `TASTE-PROVENANCE.json`은 public repository `Leonxlnx/taste-skill`의 commit `84ff339312d29955ce2040c02fd6e5bedb934608`, 7개 upstream 경로/tree, 파일별 SHA256, MIT license 원문/hash를 기록한다.

기존 installer lock의 11개 folder Git tree를 만족하는 path-changing history 후보를 조사하고, 실제 기존 7개 skill의 전체 파일 집합과 bytes를 대조했다. 모두 같은 commit과 일치했다. 모든 unchanged Git commit 중 유일하다는 주장은 아니다. 조사 때의 upstream HEAD를 임의 선택하지 않았다. 새 public clone의 locked HEAD·Git tree·실제 bytes·LICENSE 재대조도 별도 실행 증빙에 남긴다.

새 기기에서는 이 repository의 검증된 후보 commit을 clone하고 `./setup`을 실행한다. seven vendored sources가 양 harness의 개별 skill item으로 링크된다. upstream installer script나 과거 `.agents` payload를 실행/복사할 필요 없다.

```bash
python3 tools/verify_external_skills.py
# public repository를 별도 clone하고 정확한 locked HEAD로 checkout한 뒤:
python3 tools/verify_external_skills.py --upstream-checkout <upstream-clone>
./setup --validate
./setup --dry-run
./setup
./setup --uninstall
```

외부 checksum 검사는 baseline provenance audit다. 공용 원본을 의도적으로 편집하면 양 HOME에 즉시 전파되며 baseline audit는 변경을 감지한다. provenance를 갱신하려면 별도 검토가 필요하다.

## 보존과 검증 경계

`.agents` 기존 외부 pack, agentcat-usage, lost-me, `.system`, unmanaged frontmatter hooks 및 관련 없는 native plugin은 소유 범위 밖이다. 특히 denylist는 managed import/install 제외이며 기존 `mattpocock-skills@claude-plugins-official` enabled=true를 자동 비활성화하는 정책이 아니다. managed destination에 있던 충돌 파일/링크는 백업하고 uninstall 시 복원한다. 알 수 없는 자산을 최신본으로 선택하거나 import/delete하지 않는다.

원본 repo/HOME는 prior provenance 조사와 부모 readback의 읽기 범위로만 사용했다. 수정·CLI 설치·편집 전파·복원은 workspace clone/fake HOME만 사용한다. auth/history/DB를 복사하지 않는다. paid API·push·launchd 변경은 하지 않는다.

`test_ssot_consolidation.py`는 공용 경로·locked bytes·tamper refusal·양 HOME readthrough·기존 파일/링크 metadata 복원·native consumer·schema 연결·static 검사·diagnostic engine 선택을 검사한다. F1–F13 전체 회귀와 live native suite도 유지한다. 최종 bundle fresh clone에서 다시 실행한 결과는 구현 보고서와 실행 증빙을 확인한다. 다음 gate는 독립 dev-verifier `t_7c17b269`이며 운영 적용은 root가 별도 operator 단계를 배정해야 한다.
