# Paper Understand — NotebookLM 통합 계약

`paper-understand`가 **노트 + 원문 이중 소스**를 사용자 본인의 Gemini Notebook(NotebookLM)에 올려두고, 인용이 붙은 합성 답변을 튜터링 보조 자료로 쓰기 위한 규약이다.

**NotebookLM은 가속기지 의존성이 아니다.** 없어도 `paper-understand`는 그대로 동작한다.

---

## 0. 백엔드 사실관계 (숨기지 않는다)

| 항목 | 값 |
|---|---|
| backend | `notebooklm-py-unofficial` |
| client_version | `0.8.0rc1 (7d0aa42c)` |
| CLI 경로 | `~/.local/bin/notebooklm` |
| 호출 형태 | `env PATH="$HOME/.local/bin:$PATH" notebooklm ...` |
| 자격증명 | `~/.notebooklm/profiles/<profile>/storage_state.json` (mode 0600) |

이 클라이언트는 **비공식(unofficial)** 이며 문서화되지 않은(undocumented) 소비자용 Gemini Notebook/NotebookLM 웹 API를 사용한다. 언제든 깨지거나 rate limit에 걸릴 수 있고, Google 세션 쿠키(베어러 토큰에 준하는 값)를 로컬에 저장한다. 사용자가 처음 이 기능을 쓸 때 이 사실을 한 번 알린다. 안정적인 공식 API인 것처럼 설명하지 않는다.

`storage_state.json`을 출력하거나 복사하거나 버전 관리에 넣지 않는다. 쿠키·토큰 값은 로그·state·세션 노트 어디에도 남기지 않는다.

MCP 실행 스텁은 패키지에 포함되지만 `fastmcp` extra를 설치·구성하지 않아 현재 사용할 수 없다. **이 계약은 검증된 CLI를 Bash로만 호출한다.** MCP 경로를 시도하지 않는다.

---

## 1. 모드와 건강 검사

기본 정책: `notebooklm_mode: auto`

| 모드 | 동작 |
|---|---|
| `auto` | **기본값.** 건강하면 사용, 아니면 조용히 로컬 폴백 |
| `on` | 사용 불가면 그 사실을 **눈에 띄게 보고**하고 NotebookLM 분기를 중단한다. 로컬 튜터링은 폴백으로 계속 제안한다 |
| `off` | 어떤 업로드·질의도 하지 않는다 |

사용자 오버라이드: `/paper-understand {대상} --notebooklm on|off|auto`

### 건강 검사 (세션당 1회)

```bash
env PATH="$HOME/.local/bin:$PATH" notebooklm auth check --test --json
```

**두 조건을 모두** 만족해야 사용 가능으로 판정한다.

- `status == "ok"`
- `checks.token_fetch == true`

`--test`는 네트워크 요청을 한다. `--test` 없는 결과(로컬 파일 검사만)로 사용 가능을 판정하지 않는다. `token_fetch`가 `null`이면 확인되지 않은 것이지 통과가 아니다.

인증이 없으면 `checks.storage_exists: false`가 나온다. 이는 **정상 상태**이며 스킬 실패가 아니다.

### 로그인 안내 (자동화 금지)

인증은 사용자 대화형 1회 작업이다. 필요하면 명령만 안내한다.

```bash
env PATH="$HOME/.local/bin:$PATH" notebooklm login
```

Google 비밀번호를 대신 입력하지 않는다. 브라우저 자동 로그인을 시도하지 않는다.

### 로컬 폴백

CLI 부재 / 인증 없음·만료 / rate limit / 비공식 엔드포인트 파손 — **어떤 경우에도 튜터링을 막지 않는다.**

```text
NotebookLM 연동은 지금 쓸 수 없습니다 ({짧은 사유}). 노트와 원문만으로 계속합니다.
```

한 줄로 알리고 기존 워크플로를 그대로 진행한다. 사유를 길게 설명하거나 세션을 중단하지 않는다.

---

## 2. 소스 권위 순서

```text
1. 원문 논문 / 공식 부록
2. paper-driller canonical preread
3. NotebookLM 답변과 인용        ← 파생 합성물
4. 관련 Wiki 노트
5. 튜터 배경 지식
```

**NotebookLM도 또 하나의 모델이다.** 그 답변을 1차 근거로 취급하지 않는다.

다음은 NotebookLM이 말했다는 이유만으로 사용자에게 전달할 수 없다. 반드시 원문에서 재확인한다.

- 정확한 수치·점수·비율
- 수식
- Table / Figure / Section / Theorem 식별자
- 저자·소속·venue 귀속

NotebookLM에서 온 재료를 쓸 때는 `NotebookLM 합성` 레이블을 붙인다. 기존 4레이블(`논문 주장 / 근거 / 튜터 해석 / 열린 질문`)을 대체하지 않고 출처 표시로 병기한다.

```text
NotebookLM 합성: 3.2절이 방법의 핵심이라고 정리함 → 원문 Section 3.2에서 확인함
NotebookLM 합성: 개선 폭 수치 언급 → 원문 미확인. [위치 미확인]으로 두고 사용자에게 제시하지 않음
```

**"환각 없음(zero hallucinations)"이라고 절대 말하지 않는다.** NotebookLM은 인용을 붙일 뿐 정확성을 보장하지 않는다.

---

## 3. 원문 해결 — 보수적으로

노트북에는 **canonical preread**와 **원문** 둘만 올린다.

원문 해결 순서:

1. **로컬 PDF/전문 파일** — 논문 식별자(arXiv ID / DOI) 또는 제목이 canonical 노트와 일치하는 것. 최우선.
2. **검증된 canonical URL** — arXiv PDF, DOI 출판사 전문, 공식 프로젝트 논문 링크. canonical 노트의 식별자와 일치할 때만.

금지:

- **초록 페이지는 원문이 아니다.** (`arxiv.org/abs/...`는 전문 소스로 올리지 않는다)
- URL을 추측하지 않는다. 패턴으로 만들어내지 않는다.
- 제목이 비슷한 다른 논문(near-match)을 올리지 않는다. 버전·저자·연도가 어긋나면 올리지 않는다.

원문을 해결하지 못하면:

- preread만 동기화한다.
- `source_sync_status: preread-only`, `original_source_id: "N/A"`로 기록한다.
- **노트북에 원문이 있다고 말하지 않는다.**
- 로컬 튜터링 범위는 여전히 노트의 `source-coverage`가 정한다. NotebookLM에 preread를 올렸다는 사실이 coverage를 올려주지 않는다.

---

## 4. 노트북 · 소스 동기화

### 논문당 노트북 1개

`canonical_key` 우선순위: `arxiv_id` → `doi` → 정규화 제목의 sha256 앞 12자리.

노트북 제목: `Paper — {논문 제목} [{canonical_key}]`

state에 `notebook_id`가 있으면 **재사용한다.** 매 세션 새 노트북을 만들지 않는다. state에 없으면 `notebooklm list`로 같은 `canonical_key`를 가진 제목을 먼저 찾고, 없을 때만 생성한다.

### 소스 제목 규약

```text
Canonical preread — {논문 제목}
Original paper — {논문 제목}
```

### 중복 방지

소스를 추가하기 **전에**:

1. 저장된 `preread_sha256` / `original_sha256_or_url`을 현재 파일의 다이제스트와 비교한다.
2. `notebooklm source list -n {notebook_id} --json`으로 현재 소스 목록을 확인한다.

변하지 않은 소스는 다시 올리지 않는다.

canonical preread가 바뀌었으면 **갱신본을 새 소스로 추가하고** 새 source ID를 기록한다. 옛 소스를 조용히 지우지 않는다. **삭제는 사용자의 명시적 확인이 필요하다** (`source delete` / `source clean` 포함).

### 업로드 금지 대상

다음은 어떤 모드에서도 올리지 않는다.

- `learner-profile.md`
- `state.yaml`
- 세션 노트 (`sessions/*.md`)
- 오개념 기록, 사용자 답변, 숙달 상태
- 그 논문의 preread가 아닌 다른 Obsidian/`Public/` 노트

**기본 업로드 대상은 정확히 둘뿐이다: 해당 논문의 원문과 그 논문의 canonical preread.**

### 명령 (0.8.0rc1 pinned `7d0aa42c` 계약)

```bash
export PATH="$HOME/.local/bin:$PATH"

# 노트북 생성
notebooklm create "Paper — {제목} [{canonical_key}]" --json

# 소스 추가
notebooklm source add "{preread_path}" -n {notebook_id} --type file \
  --title "Canonical preread — {제목}" --json
notebooklm source add "{pdf_path}" -n {notebook_id} --type file \
  --title "Original paper — {제목}" --json
# URL 폴백(검증된 canonical URL일 때만)
notebooklm source add "{canonical_url}" -n {notebook_id} --type url \
  --title "Original paper — {제목}" --json

# 준비 대기 — 질의 전에 반드시
notebooklm source wait {source_id} -n {notebook_id} --timeout 180 --json

# 현재 소스 확인 (dedup)
notebooklm source list -n {notebook_id} --json
notebooklm source fulltext {source_id} -n {notebook_id} --json
```

`source wait` exit code: `0` ready / `1` missing·처리 실패 / `2` timeout. **두 소스가 모두 ready가 되기 전에는 질의하지 않는다.**

---

## 5. 질의 정책

매 대화 턴마다 부르지 않는다. 다음 순간에만 전략적으로 쓴다.

| 시점 | 목적 |
|---|---|
| 세션 부트스트랩 (Phase 1–3) | 개념 지도 초안, claim/evidence 지도, 선수 지식 공백 후보 |
| Phase 5 근거 감사 | 주장↔근거 연결의 교차 확인 |
| 온디맨드 | 사용자가 교차 소스 질문을 하거나, preread와 원문이 충돌할 때 |

```bash
notebooklm ask "{질문}" -n {notebook_id} --json
notebooklm ask --prompt-file {path} -n {notebook_id} --json     # 긴 프롬프트
```

`--json` 응답에서 보존하는 것:

- `answer`
- `conversation_id`
- 참조된 source ID
- 인용된 텍스트 스니펫

`--new`는 서버측 대화를 파괴한다. 사용자가 요청하지 않는 한 쓰지 않는다.

### 인용 검사

응답의 참조가 **preread 소스만** 가리키는데 그 주장이 원문에 근거해야 하는 종류(수치·실험 조건·수식·표)라면:

```text
근거 불충분 — NotebookLM 인용이 preread에만 걸려 있다. 원문에서 직접 확인한 뒤 사용한다.
```

확인 전에는 사용자에게 수치를 제시하지 않는다.

### state에 남기는 것

전체 응답을 덤프하지 않는다. 남기는 것은 압축 provenance뿐이다: `conversation_id`, 참조 source ID, 미해결 쟁점, `last_query_at`.

---

## 6. 동의와 투명성

인증이 건강할 때 사용자 본인 Notebook에 preread + 원문을 올리는 것이 요청된 기본 동작이다. 다만 **첫 성공 동기화에서는 무엇을 올렸는지 정확히 보고한다.**

```text
NotebookLM 동기화 완료
  노트북: Paper — {제목} [{canonical_key}] (ID: {notebook_id})
  올린 소스 2건:
    1. Canonical preread — {제목}   ({preread 경로})
    2. Original paper — {제목}      ({PDF 경로 또는 URL})
  올리지 않은 것: 학습 상태·세션 노트·프로필·다른 Wiki 노트
```

원문을 못 올렸으면 1건만 보고하고 `preread-only`임을 명시한다. 올리지 않은 것을 올렸다고 쓰지 않는다.

---

## 7. 실패 처리

| 증상 | 판정 | 행동 |
|---|---|---|
| CLI 없음 (`command not found`) | disabled | 1줄 안내 후 로컬 진행 |
| `storage_exists: false` | 미인증 | `notebooklm login` 안내, 로컬 진행 |
| `token_fetch: false/null` | 만료·네트워크 | 재로그인 안내, 로컬 진행 |
| 429 / rate limit | 일시 실패 | 이번 세션 질의 중단, 로컬 진행 |
| 스키마 불일치·엔드포인트 파손 | 비공식 API 파손 | `last_error`에 요약 기록, 로컬 진행 |
| `source wait` exit 2 | pending | `source_sync_status: pending`, 질의하지 않음 |

`last_error`는 **redact한다.** 쿠키·토큰·전체 응답 본문을 넣지 않는다. 한 줄 사유만.

`--notebooklm on`일 때만 실패를 눈에 띄게 보고한다. `auto`에서는 짧게 알리고 넘어간다.

---

## 8. 자기 점검

- [ ] `auth check --test --json`의 `status`와 `token_fetch`를 **둘 다** 확인했는가
- [ ] 노트북을 새로 만들기 전에 `notebook_id` 재사용을 확인했는가
- [ ] 다이제스트 비교로 재업로드를 피했는가
- [ ] 올린 것이 원문과 preread **둘뿐**인가 (state·프로필·세션 노트 아님)
- [ ] 두 소스가 ready가 된 뒤에 질의했는가
- [ ] NotebookLM 재료에 `NotebookLM 합성` 레이블을 붙였는가
- [ ] 수치·식별자를 원문에서 재확인했는가
- [ ] "환각 없음"이라고 쓰지 않았는가
- [ ] 실패 시 로컬 튜터링이 그대로 이어졌는가
