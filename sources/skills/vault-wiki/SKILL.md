---
name: vault-wiki
description: 내 Obsidian vault(obsidian-notes)를 LLM Wiki로 쓰는 진입점. 위키 근거 질의와 synthesis 환류, 새 노트 배선(catalog·lint·log)을 vault의 SCHEMA 규칙대로 수행한다. quality queue·공개 통계·그래프 연결 제안은 Hermes wiki-librarian이 만들고, 이 스킬은 그 결과를 읽기만 한다. 트리거 — 위키에서 찾아줘, 내 노트에서 찾아줘, vault에서 찾아줘, 위키에 반영해줘, 이 노트 배선해줘, 카탈로그 갱신, 위키 상태, synthesis로 남겨줘, llm-wiki. 논문 노트 생성은 paper-driller, 책 노트는 book-qa-note가 하고 이 스킬은 그 뒤 배선을 맡는다.
---

# vault-wiki

Vault 루트: `~/Library/Mobile Documents/iCloud~md~obsidian/Documents/obsidian-notes`. 아래 경로와 명령은 모두 이 루트에서 실행한다.

Python은 vault 도구 의존성(PyYAML·ruamel.yaml)이 있는 `/opt/homebrew/bin/python3`를 쓴다. 아래 `python3`는 이 인터프리터를 뜻한다.

이 스킬은 **절차와 위치만** 담는다. 형식·품질 규칙의 정본은 vault 문서이고, 이 파일과 vault 문서가 다르면 vault 문서를 따른다. vault 문서끼리 다르면 `_wiki/SCHEMA.md`의 최신 타입별 계약이 이긴다. 단, `type: paper` 노트 형식(general-v2)의 정본은 검사기 `Public/_tools/paper_note.py`다.

## 먼저 읽을 것

1. `_wiki/SCHEMA.md`: 타입 계약, 품질 큐, 생성·갱신 트랜잭션.
2. `Public/WIKI-GUIDE.md`: 운영 흐름과 안전 규칙.
3. 작업할 하위 디렉터리의 `AGENTS.md`.
4. `type: paper` 노트를 건드리면 `python3 Public/_tools/paper_note.py --help`와 paper-driller 스킬의 `references/note-spec.md`.

## 하지 않는 것

근거는 SCHEMA·WIKI-GUIDE·`_wiki/STRUCTURE.md`에 있다.

- 기존 frontmatter를 일괄 정규화하거나 지우지 않는다. 노트를 이동·삭제하지 않는다. 미흡 노트 분리는 librarian이 만드는 `_wiki/queues/`가 맡는다.
- `type: paper`의 frontmatter는 `paper_note.py check`가 보는 17키 계약을 따른다. `tags`·`domains`·`schema-version`을 추가하지 않는다. 빈 값은 추측해 채우지 않는다.
- `Reading-Status`·`Read-Depth`·`publish`·메모 칸(`<!-- 메모 -->` … `<!-- /메모 -->`)은 사람 소유다. 바꾸지 않는다.
- `AUTO:body` 표시가 없는 노트를 LLM 생성물로 추정하지 않는다.
- `_wiki/` 내용을 `Public/`로 옮기거나 공개 JSON에 경로·제목·queue 상세를 넣지 않는다.
- `_wiki/catalog/`, `_wiki/bases/`, `_wiki/queues/`는 손으로 고치지 않는다. 재생성된다.
- 원본 노트에 backlink를 자동으로 끼워 넣지 않는다.
- `git commit`·`git push`는 사용자가 요청할 때("올려")만 한다. push는 블로그 빌드를 트리거한다. 논문 노트는 `publish: ready`인 것만 올라간다.
- catalog·queue·Base·공개 통계 갱신과 그래프 연결 제안(Tier2)은 Hermes `wiki-librarian`이 한다(매일 03:00 cron 포함). 이 스킬은 `quality_queues.py`·`export_public_wiki_stats.py`를 돌리지 않고, librarian이 만든 결과를 읽기만 한다.

## 모드 고르기

| 요청 | 모드 |
|---|---|
| 세션 시작, "위키 상태", 품질 큐·모순·고아·빈틈이 궁금하다 | A. librarian 결과 읽기 |
| 새 노트를 썼다, 다른 스킬이 노트를 만들었다, "배선해줘" | B. 배선 |
| 위키를 근거로 한 질문 | C. 질의·환류 |

## A. librarian 결과 읽기

quality queue·공개 통계·Tier2 그래프 점검은 Hermes `wiki-librarian`이 만든다(`_wiki/LIBRARIAN.md`). 이 스킬은 librarian이 만든 결과를 읽기만 한다. 재생성 스크립트를 대신 돌리지 않고, 결과 파일을 고치지 않는다.

```bash
python3 Public/_tools/lint.py            # 읽기 전용
grep "^## \[" _wiki/log.md | tail -10
```

- 품질: `_wiki/DASHBOARD.md`, `_wiki/queues/`.
- 최근 실행: `_wiki/audit/librarian/latest.json`.
- 그래프 점검과 연결 제안: `_wiki/graph/REPORT.md`, `_wiki/graph/PROPOSALS.md`.

보고는 P0/P1 수, 최근 활동, librarian 결과의 마지막 갱신 시각만 짧게 한다. 결과가 오래됐으면 "librarian 유지보수를 돌릴까?"라고 알리기만 한다. 기존 문제를 이번 세션이 만든 오류로 말하지 않는다. 사용자가 그중 모순 정리를 승인하면 C의 5–6번 형식으로 `_wiki/synthesis/`에 정리 노트를 만든다.

## B. 배선

노트 1개를 위키에 연결한다(catalog·lint·log). 아래 단계가 모두 끝나야 완료다. SCHEMA "생성·갱신 트랜잭션" 중 quality queue와 공개 통계 갱신은 librarian 몫이라 여기서 돌리지 않는다. 여러 편이면 한 편씩 끝내고 다음으로 넘어간다. 사용자가 "배치로"라고 하면 묶어서 처리하되 6번 재생성은 마지막에 한 번만 돌린다.

1. 위치 확인: AI 논문은 `Public/AI/Papers/`, 비-AI 논문은 `Public/{domain}/`. 랩 자료 규칙은 `Public/CLAUDE.md`의 Labs·Conference·Study 절을 따른다.
2. 형식 검증.
   - paper: `python3 Public/_tools/paper_note.py check "<노트 경로>"`. exit 0 통과, 2 규격 위반(stderr에 목록), 1 사용 오류. 위반은 보고만 하고 고치지 않는다. 노트를 다시 쓰는 일은 paper-driller가 한다. `_archive/`에만 있는 노트로의 링크는 "이전 대기"로 나오며 오류가 아니다.
   - 그 밖의 노트: `type`이 `paper | lecture | concept | hub | project | synthesis | moc` 중 하나인지와 SCHEMA의 타입별 필수 키를 확인한다. `Public/교양/` 새 노트는 `Reading-Status: ☑️ Not Started`를 `type:` 다음 줄에 둔다.
3. 중복 확인: paper는 `URL`에서 arXiv id나 DOI를 뽑아 `URL:` 줄에서만 찾는다. 예: `grep -rlE '^URL:.*2310\.06825' Public` (id의 `.`은 `\.`로 쓴다). 본문 인용까지 찾으면 그 논문을 인용한 다른 노트가 걸린다. 자기 자신 말고 다른 파일이 나오면 멈추고 사용자에게 묻는다.
4. `linked-bases` 실재 확인: 값마다 `find _wiki/bases -name "<이름>.base"`가 결과를 내야 한다.
5. 관련 노트 연결: 같은 Topic·개념을 다루는 기존 노트를 catalog에서 찾는다. 새 노트 본문에서 `[[링크]]`를 건다. 기존 노트에 링크를 추가하는 일은 제안하고 승인받은 뒤에만 한다.
6. 재생성과 검증, 이 순서로.

   ```bash
   python3 Public/_tools/build_catalog.py
   python3 Public/_tools/lint.py
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

## 도구를 고쳤을 때

`Public/_tools/` 코드를 바꿨다면 `cd Public/_tools && /opt/homebrew/bin/pytest -q`를 통과시킨 뒤 끝낸다.

## 보고

무엇을 바꿨는지(노트, 파생물, log)와 바꾸지 않고 제안만 한 것을 나눠 말한다. 실행하지 못한 검증이 있으면 그렇다고 적는다.
