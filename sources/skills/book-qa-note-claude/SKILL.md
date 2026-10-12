---
name: book-qa-note
description: 서울대 권장도서 100선·일반 책을 "직접 안 읽고 문답으로 배우는" Obsidian 책 노트(Public/Books) 형식으로 조사·작성하고, 문답 기록·읽기 상태를 갱신한다. 트리거 — 책 정리해줘, 책 노트 만들어줘, 서울대 권장도서, 문답으로 책 공부, 이 책 요약, 오늘 문답 기록해줘, book note, book summary.
---

# book-qa-note

사용자는 책을 직접 읽지 않는다. Claude가 인터넷으로 조사해 정리한 핵심을 듣고 문답으로 배운다. 이 스킬은 그 노트를 vault의 기존 문답 책 노트 106개와 **똑같은 구조**로 만들고, 문답 뒤에는 기록만 덧붙인다.

Vault 루트: `~/Library/Mobile Documents/iCloud~md~obsidian/Documents/obsidian-notes` (아래 경로는 모두 여기 기준).

## 언제 쓰나

- 새 책 노트: "○○ 정리해줘", "서울대 권장도서 n번 노트", "이 책 문답으로 공부하고 싶어".
- 기존 책 노트에 문답 세션 기록: "오늘 문답 기록해줘", "이기적 유전자 이어서".

쓰지 않는 경우: 논문(`type: paper` → paper-driller), `Public/교양/` 개념 노트, 사용자가 직접 읽으며 쓴 독서 노트(`심리학의 오해.md`처럼 `[[Book-study(LCBL).base]]`·`[[AI-Books.base]]`를 단 노트). 이런 노트의 형식을 이 스킬로 바꾸지 않는다.

## 먼저 읽을 것

1. vault `CLAUDE.md`, `_wiki/SCHEMA.md`(이 vault의 불변 규칙).
2. `references/template.md` — frontmatter·본문 뼈대, 장르별 변형, 실제 예시. **노트를 쓰기 전에 반드시 연다.** 구조를 기억에 의존해 쓰면 키 순서와 절 이름이 틀어진다.

## 1. 중복 확인과 자리 정하기

쓰기 전에 같은 책이 있는지 본다. 노트 이름·H1·Author가 다른 표기일 수 있다(예: 「루쉰전집」 노트의 실제 책은 『루쉰 소설 전집』).

```bash
cd "<vault>"
ls Public/Books "Public/Books/서울대 권장도서 100선"
grep -rl -i "<제목 일부>\|<저자 성>" Public --include='*.md'   # zsh: glob은 따옴표로
grep -i "<제목 일부>" "Public/Books/서울대 권장도서 100선/snu-100.csv"
```

있으면 새로 만들지 말고 사용자에게 알린다. 없으면 자리를 정한다.

| 경우 | 위치 | `linked-bases` | 추가 키 |
| --- | --- | --- | --- |
| `snu-100.csv`에 있는 책 | `Public/Books/서울대 권장도서 100선/<제목>.md` | `[[SNU-100.base]]` | `SNU-No: <번호>` (Author 다음이 아니라 linked-bases 다음) |
| 100선 밖 책 | `Public/Books/<제목>.md` | `[[QA-Books.base]]` | 없음 |

100선 100권은 이미 노트가 다 있다(97번 이기적 유전자만 `Public/Books/`에 있음). 그래서 100선 요청은 보통 "기존 노트에 문답 기록"이다. 파일 이름은 목록 노트의 링크와 같게 한다. 이름이 겹치는 책은 `고향 (이기영)`처럼 괄호로 구분한다.

## 2. 조사

원칙: **확인한 것만 쓴다.** 확인하지 못한 것은 본문에 단정하지 않고 `## 출처와 불확실한 점`에 적는다. 저자 문장을 따옴표로 인용하려면 출처에서 그 문장을 직접 봤어야 한다. 그렇지 않으면 의역임을 밝힌다.

1. **기준판 고르기**: 지금 새 책으로 살 수 있는 한국어판을 우선한다. 번역·해설이 좋은 판, 원전 완역을 고른다. 고른 이유와 다른 판(역자·연도·ISBN)을 `> [!note] 판 선택`에 적는다. 절판뿐이면 절판이라고 적고 그 판을 쓴다.
2. **서지**: 출판사, 옮긴이, 출간일, ISBN-13, 쪽수, 원서 정보. 서점끼리 쪽수·표기가 다르면 둘 다 적는다.
3. **목차**: YES24·알라딘·교보문고 상품 페이지의 목차를 **원문 그대로** 코드블록에 옮긴다. 줄바꿈만 정리하고 표기 오류도 고치지 않는다(차이는 아래 bullet로 적는다). 둘째 출처(다른 서점, 출판사 페이지, 전자책, 도서관 서지, 알라딘 차례 이미지)로 항목과 순서를 대조한다. 출처를 하나밖에 못 찾으면 그렇게 적는다. 한국어 목차를 못 찾으면 원서 목차를 쓰고, 그 사실을 `## 목차` 머리말과 출처 절 둘 다에 적는다. 웹 추출 흔적(`L735: ####` 같은 줄)은 지운다.
4. **내용**: 한국민족문화대백과사전, Stanford Encyclopedia of Philosophy, 출판사 책 소개, 원서 영어판, Wikipedia 등. 독자 블로그는 "신뢰도 낮음"이라고 표시하고 보조로만 쓴다.

검색이 막히면(세션 WebSearch 한도 등) 서점·백과사전 페이지를 직접 열어 조사한다. 그래도 확인 못 한 줄거리 세부는 출처 절의 "원문과 대조하지 못한 것"에 남긴다.

## 3. 작성

`references/template.md`의 뼈대를 그대로 쓴다. 핵심 구조:

- frontmatter 키 순서: `Reading-Status → Author → Topic → Comment → URL → linked-bases → (SNU-No) → Start-Date → End-date → type`. `type: project`가 맨 끝.
- 새 노트 상태: `Reading-Status:` 리스트에 `  - ☑️ Not Started`, `Start-Date:`·`End-date:` 비움.
- 본문: H1 `# 제목 (저자)` → 머리 인용문(공부 방식, `정리한 날짜: YYYY-MM-DD (아직 문답 전)`) → 서지 표 → 판 선택 note → `## 이 책의 핵심`(**한 줄로 먼저**, 개념 7개 또는 인물과 주제, 흔한 오해) → `## 목차` → `## 장별 핵심`(장마다 `> [!quote] 저자가 가장 하고 싶은 말` 한 문장 + bullet) → `## 문답 기록`(빈 칸) → `## 출처와 불확실한 점`.

문체: 고등학생이 따라올 수 있는 쉬운 한국어. 한 문장에 한 생각. 전문어는 처음 나올 때 괄호로 바로 풀이한다. "~이다/~한다"체. 과장·수사 없이 사실을 먼저 쓴다.

**연결 소절(선택)**: 책이 사용자의 연구(예: LLM 에이전트 생존·협력 실험)와 실제로 이어질 때만 `### 내 연구와의 연결`을 `## 이 책의 핵심` 끝에 짧게 쓴다(`아이, 로봇.md` 선례). 링크는 vault에 **실재하는** 노트만 단다. 쓰기 전에 `ls`/`grep`으로 확인한다. 억지 연결이면 빼는 편이 낫다.

## 4. 검증과 배선

1. 형식 검사:
   ```bash
   python3 ~/.claude/skills/book-qa-note/scripts/check_book_note.py "<새 노트 경로>"
   ```
   FAIL은 고친다. WARN은 이유를 확인한다.
2. 100선 밖 책은 `Public/Books/서울대 권장도서 100선/서울대 권장도서 100선.md` "진행 현황"의 "목록 밖에서 공부한 책:" 줄에 `[[새 노트]] (저자)`를 덧붙인다(본문 한 줄만. 그 노트의 frontmatter는 건드리지 않는다). 기존 100선 밖 문답 책 넷이 모두 여기서 링크된다.
3. vault 파이프라인을 순서대로:
   ```bash
   cd "<vault>"
   python3 Public/_tools/build_catalog.py
   python3 Public/_tools/lint.py
   python3 Public/_tools/quality_queues.py
   python3 Public/_tools/export_public_wiki_stats.py
   cd Public/_tools && /opt/homebrew/bin/pytest -q
   ```
   새 노트가 `META-DATE` 큐에 뜨는 것은 정상이다(날짜를 비운 의도된 상태). `LINK-BROKEN`이 뜨면 연결 소절 링크를 고친다.
4. `_wiki/log.md` 끝에 append:
   ```markdown
   ## [YYYY-MM-DD] ingest | <제목>
   - 신규 책 노트: [[Public/Books/<제목>]] (type: project, Reading-Status: ☑️ Not Started, linked-bases: [[QA-Books.base]]). <100선 여부>
   - 기준판: <출판사 연도(옮긴이, ISBN)>. 목차는 <출처1> + <출처2>로 대조.
   - 미확인: <핵심 불확실 항목>
   ```

## 5. 문답 세션 뒤 갱신

읽기 상태는 **사람의 값**이다. 모델이 노트를 썼다거나 대화가 끝났다는 이유로 바꾸지 않는다.

| 언제 | 할 일 |
| --- | --- |
| 사용자가 문답을 마치고 기록을 원할 때 | `## 문답 기록` 아래 `### YYYY-MM-DD`(그날 날짜, 오래된 순) 소절을 추가하고 짧게 기록(template.md 5절). 첫 세션이면 `Start-Date`를 그 날짜로, 머리 인용문 날짜 줄을 `> 공부한 날짜: YYYY-MM-DD`로 바꾼다. |
| 100선 책의 첫 세션 | 사용자 확인 후 `linked-bases`에 `"[[QA-Books.base]]"`를 첫 항목으로 추가(이기적 유전자 선례. QA-Books.base 표 이름이 "문답으로 공부한 책"). |
| 사용자가 "다 공부했다/끝"이라고 **명시적으로** 말할 때만 | `End-date`, `Reading-Status: ✅ Done`, 100선이면 목록 노트의 `- [ ]` → `- [x]` 체크. 하나라도 애매하면 묻는다. |
| `▶️ In progress` | 사용자가 그렇게 바꿔 달라고 할 때만. |

문답 중 노트 본문이 틀렸다고 밝혀지면 본문을 고치고, 문답 기록에 "정정:"으로 남긴다.

## 하지 말 것

- 다른 노트의 frontmatter를 고치거나 기존 노트를 일괄 정규화하지 않는다(구분선 누락 같은 기존 형식 차이도 그대로 둔다).
- `_wiki/` 파일이나 `.base`를 `Public/`로 옮기거나 복사하지 않는다. `.base`를 손으로 만들지 않는다.
- 목차·ISBN·쪽수·인용을 지어내지 않는다. 못 찾은 것은 "확인하지 못했다"고 쓴다.
- 책 노트에 `tags`·`domains`·`schema-version`·`description` 같은 키를 새로 붙이지 않는다(기존 106개 노트에 없다).
