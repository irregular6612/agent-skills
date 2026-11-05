---
name: vault-wiki
description: 내 Obsidian vault(obsidian-notes)를 LLM Wiki로 운영하는 진입점. 세션 시작 점검, 새 노트 배선(catalog·lint·quality queue·공개 통계·log), 위키 근거 질의와 synthesis 환류, Tier1/Tier2 lint를 vault의 SCHEMA 규칙대로 수행한다. 트리거 — 위키에서 찾아줘, 내 노트에서 찾아줘, vault에서 찾아줘, 위키에 반영해줘, 이 노트 배선해줘, 카탈로그 갱신, 위키 점검, 위키 lint, Tier2 lint, 위키 상태, synthesis로 남겨줘, llm-wiki. 논문 노트 생성은 paper-driller, 책 노트는 book-qa-note가 하고 이 스킬은 그 뒤 배선을 맡는다.
---

# vault-wiki

Vault 루트: `~/Library/Mobile Documents/iCloud~md~obsidian/Documents/obsidian-notes`. 아래 경로와 명령은 모두 이 루트에서 실행한다.

Python은 vault 도구 의존성(PyYAML·ruamel.yaml)이 있는 `/opt/homebrew/bin/python3`를 쓴다. 아래 `python3`는 이 인터프리터를 뜻한다.

이 스킬은 **절차와 위치만** 담는다. 형식·품질 규칙의 정본은 vault 문서이고, 이 파일과 vault 문서가 다르면 vault 문서를 따른다. vault 문서끼리 다르면 `_wiki/SCHEMA.md`의 최신 타입별 계약이 이긴다.

## 먼저 읽을 것

1. `_wiki/SCHEMA.md`: 타입 계약, 품질 큐, 생성·갱신 트랜잭션.
2. `Public/WIKI-GUIDE.md`: 운영 흐름과 안전 규칙.
3. 작업할 하위 디렉터리의 `AGENTS.md`.
4. `type: paper` 노트를 건드리면 `Public/_tools/PAPER_FRONTMATTER.md`.

## 하지 않는 것

근거는 SCHEMA·WIKI-GUIDE·`_wiki/STRUCTURE.md`에 있다.

- 기존 frontmatter를 일괄 정규화하거나 지우지 않는다. 노트를 이동·삭제하지 않는다. 미흡 노트는 `_wiki/queues/`로만 분리한다.
- `type: paper`에는 정확히 13키만 둔다. `tags`·`domains`·`schema-version`을 추가하지 않는다. 빈 값은 추측해 채우지 않는다.
- `Reading-Status`·`Read-Depth`·사용자 메모는 사람 소유다. 바꾸지 않는다.
- `DRILLER:meta`나 `AUTO:body` 표시가 없는 노트를 LLM 생성물로 추정하지 않는다.
- `_wiki/` 내용을 `Public/`로 옮기거나 공개 JSON에 경로·제목·queue 상세를 넣지 않는다.
- `_wiki/catalog/`, `_wiki/bases/`, `_wiki/queues/`는 손으로 고치지 않는다. 재생성된다.
- 원본 노트에 backlink를 자동으로 끼워 넣지 않는다.
- `git commit`·`git push`는 사용자가 요청할 때만 한다. push는 블로그 빌드를 트리거한다.
- 매일 03:00 catalog·queue·Base 갱신은 Hermes `wiki-librarian` cron이 한다. 이 스킬이 같은 작업을 일정으로 돌리지 않는다.

## 모드 고르기

| 요청 | 모드 |
|---|---|
| 세션 시작, "위키 상태" | A. 점검 |
| 새 노트를 썼다, 다른 스킬이 노트를 만들었다, "배선해줘" | B. 배선 |
| 위키를 근거로 한 질문 | C. 질의·환류 |
| "위키 점검", "lint", 모순·고아·빈틈 찾기 | D. Lint |

## A. 점검

```bash
python3 Public/_tools/lint.py
grep "^## \[" _wiki/log.md | tail -10
ls _wiki/catalog
```

`_wiki/log.md`에서 도메인별 마지막 `lint` 날짜를 확인한다. 30일이 지난 도메인이 있으면 "이 도메인 Tier2 lint를 돌릴까?"라고 알리기만 한다. 자동으로 돌리지 않는다.

보고는 P0/P1 수, 최근 활동, 알림만 짧게 한다. 기존 문제를 이번 세션이 만든 오류로 말하지 않는다.

## B. 배선

노트 1개를 위키에 연결한다. SCHEMA "생성·갱신 트랜잭션"의 11단계가 모두 끝나야 완료다. 여러 편이면 한 편씩 끝내고 다음으로 넘어간다. 사용자가 "배치로"라고 하면 묶어서 처리하되 4–7번 재생성은 마지막에 한 번만 돌린다.

1. 위치 확인: AI 논문은 `Public/AI/Papers/`, 비-AI 논문은 `Public/{domain}/`. 랩 자료 규칙은 `Public/CLAUDE.md`의 Labs·Conference·Study 절을 따른다.
2. 형식 검증.
   - paper: `bash Public/_tools/paper_frontmatter.sh check "<노트 경로>"`. exit 0 통과, 1 계약 위반, 2 실행 오류. 위반은 보고만 하고 `fix --apply`를 자동으로 돌리지 않는다.
   - 그 밖의 노트: `type`이 `paper | lecture | concept | hub | project | synthesis | moc` 중 하나인지와 SCHEMA의 타입별 필수 키를 확인한다. `Public/교양/` 새 노트는 `Reading-Status: ☑️ Not Started`를 `type:` 다음 줄에 둔다.
3. 중복 확인: paper는 `URL`에서 arXiv id나 DOI를 뽑아 `URL:` 줄에서만 찾는다. 예: `grep -rlE '^URL:.*2310\.06825' Public` (id의 `.`은 `\.`로 쓴다). 본문 인용까지 찾으면 그 논문을 인용한 다른 노트가 걸린다. 자기 자신 말고 다른 파일이 나오면 멈추고 사용자에게 묻는다.
4. `linked-bases` 실재 확인: 값마다 `find _wiki/bases -name "<이름>.base"`가 결과를 내야 한다.
5. 관련 노트 연결: 같은 Topic·개념을 다루는 기존 노트를 catalog에서 찾는다. 새 노트 본문에서 `[[링크]]`를 건다. 기존 노트에 링크를 추가하는 일은 제안하고 승인받은 뒤에만 한다.
6. 재생성과 검증, 이 순서로.

   ```bash
   python3 Public/_tools/build_catalog.py
   python3 Public/_tools/lint.py
   python3 Public/_tools/quality_queues.py
   python3 Public/_tools/export_public_wiki_stats.py
   ```

7. catalog 등재 확인: 새 노트 제목이 `_wiki/catalog/{domain}.md`에 있어야 한다. 없으면 lint 출력의 `WIKI-CATALOG`를 본다.
8. `_wiki/log.md` 맨 끝에 append한다. 형식: `## [YYYY-MM-DD] ingest | {노트 제목}`. 다음 줄부터 짧은 요약을 적는다(어디에 두었는지, 연결한 노트, 남은 검토 항목).

## C. 질의·환류

**진입 범위:** 사용자가 위키·내 노트·vault를 근거로 답하라고 할 때만 이 모드를 쓴다. 예: "위키에서", "내 노트 기준으로", "내가 정리한 것 중에". 일반 지식 질문을 자동으로 위키로 돌리지 않는다.

1. 질문 도메인을 정하고 `_wiki/catalog/{domain}.md`만 읽는다. 도메인이 여러 개면 그 catalog들만 읽는다. vault 전체를 읽지 않는다.
2. catalog의 요약 줄로 후보를 고른 뒤 `grep`으로 `Topic`·`Comment`·`tags`를 교차 확인한다. 후보 노트 본문만 연다.
3. 답한다. 모든 주장에 `[[노트 경로|제목]]`을 달고, 논문이면 `URL`도 단다. 노트에 없는 내용은 노트에 없다고 밝히고, 위키 밖 지식과 구분한다.
4. 환류 게이트.
   - 적재 조건: 노트 2개 이상을 종합했고 다시 쓸 가치가 있다(특히 도메인 횡단). 단일 노트 조회는 적재하지 않는다.
   - dedup 먼저: `_wiki/synthesis/`, `_wiki/MOC.md`, catalog에서 비슷한 페이지를 찾는다. 있으면 새로 만들지 않고 그 페이지를 갱신한다.
   - 조건이 명백하면 적재하고 사후에 알린다. 애매하면 적재할지 묻는다.
5. 적재 형식: `_wiki/synthesis/{제목}.md`.

   ```yaml
   ---
   type: synthesis
   updated: "YYYY-MM-DD"
   quality-status: ready
   tags: [synthesis, ...]
   ---
   ```

   본문은 요약이 아니라 비교·분류·연결을 담는다. 핵심 주장마다 `[[source note]]`를 단다. 출처 노트 본문은 고치지 않는다.
6. `_wiki/MOC.md`에 한 줄로 등재하고 `_wiki/log.md`에 `## [YYYY-MM-DD] query | {질문 요지}`를 append한다. 적재하지 않은 질의도 log에는 남긴다.

## D. Lint

**Tier1 (기계적)**

```bash
python3 Public/_tools/lint.py            # 읽기 전용
python3 Public/_tools/lint.py --log      # 요약을 _wiki/log.md에 append
python3 Public/_tools/quality_queues.py  # P0–P4 큐와 _wiki/DASHBOARD.md 갱신
```

자동 수정은 두 가지만 허용한다. catalog 재생성, 그리고 파일명 한 글자 차이 같은 명백한 오타성 끊긴 링크. 나머지는 제안하고 승인받은 뒤 고친다.

**Tier2 (의미적, 사용자가 도메인을 지정해 트리거)**

1. 해당 `_wiki/catalog/{domain}.md`와 `_wiki/queues/` 상세 큐만 먼저 읽는다. Hermes 사서가 만든 `_wiki/graph/REPORT.md`, `_wiki/graph/PROPOSALS.md`가 있으면 중복 제안을 피하는 데 쓴다.
2. 찾는 것: 서로 맞지 않는 주장, 새 출처가 대체한 낡은 주장, 언급되지만 페이지가 없는 개념, 약한 cross-ref, 웹 검색으로 메울 수 있는 빈틈.
3. 결과는 전부 제안이다. 노트를 바로 고치지 않는다.
   - 연결 제안은 `_wiki/graph/PROPOSALS.md`에 날짜 절을 새로 추가해 적는다(`source → target`, 두 본문의 근거, 관계, 넣을 위치). 기존 항목과 사람이 표시한 상태는 보존한다.
   - 모순과 낡은 주장은 양쪽 노트 경로와 해당 문장을 보여 주고 보고한다. 사용자가 승인하면 `_wiki/synthesis/`에 정리 노트를 만든다(C의 5–6번 형식).
4. `_wiki/log.md`에 `## [YYYY-MM-DD] lint | {domain} Tier2`를 append한다.

## 도구를 고쳤을 때

`Public/_tools/` 코드를 바꿨다면 `cd Public/_tools && /opt/homebrew/bin/pytest -q`를 통과시킨 뒤 끝낸다.

## 보고

무엇을 바꿨는지(노트, 파생물, log)와 바꾸지 않고 제안만 한 것을 나눠 말한다. 실행하지 못한 검증이 있으면 그렇다고 적는다.
