---
name: paper-driller
description: >-
  논문 1편으로 짧은 동반 노트(general-v2)를 만든다. 읽기 전에 훑고, 원문과 같이 읽으며 절마다 메모를 덧붙이고,
  정리되면 블로그에 올리는 노트다. 본문 5,000자 상한, 핵심 도표 3~4개 이미지 포함. TRIGGERS: 논문 요약,
  paper drill, arxiv 정리, 논문 노트, 논문 읽기 전 요약, 이 논문 정리해줘
allowed-tools:
  - WebFetch
  - WebSearch
  - Read
  - Write
  - Edit
  - Bash
---

# Paper Driller (general-v2)

## Runtime binding

`SKILL_ROOT` is the directory containing this `SKILL.md` (resolve symlinks). `VAULT` is the Obsidian vault:
the user's value → `$PAPER_DRILLER_VAULT` → `$PAPER_VAULT_ROOT` →
`~/Library/Mobile Documents/iCloud~md~obsidian/Documents/obsidian-notes`. If `$VAULT/Public/_tools/paper_note.py`
does not exist, stop and say so. Use whatever web and PDF tools the current harness really exposes
(Claude: `WebFetch`/`WebSearch`/`Read(pages=…)`; Codex: its own web/PDF tools). Never assume another harness's tool names.

## 무엇을 만드나

원문 옆에 두고 읽는 **짧은 요약 노트**다. 끝까지 읽히는 것이 목표라서 길이 상한이 있다. 독자는 이 분야를 처음 보는
똑똑한 고등학생이다. 쉽게 쓰되 숫자·조건·가정은 원문 그대로 남긴다. 노트 형식의 정본은 `references/note-spec.md`,
검사의 정본은 `$VAULT/Public/_tools/paper_note.py` 하나다. 이 둘과 다르게 쓰지 않는다.

## 호출

```text
/paper-driller <arXiv-ID | DOI | URL | 제목> [--ditto]
```

템플릿은 `general-v2` 하나다. 묻지 않고 바로 진행하므로 사람 없이(cron, `codex exec`) 돌려도 된다.
옛 호출의 `--template`, `--mode`, `--auto` 인자는 무시한다. `--ditto`가 있으면 6단계 뒤에 `ditto-writer` 스킬
(`profile=juhyeon-ko-academic rounds=3`)로 서술 문단만 다듬는다. 표·수치·이미지·frontmatter·`**핵심**` 줄·BibTeX는
고정 블록으로 넘기고, 다듬은 뒤 다시 검사한다. ditto-writer가 없으면 건너뛰고 한 줄로 알린다.

## 순서

1. **중복 확인.** `URL`에서 arXiv id(버전 제거)·DOI·정규화 URL을 뽑아 `$VAULT/_wiki/catalog/*.md`와
   `$VAULT/Public/**/*.md`의 `URL`과 비교한다. 같은 논문 노트가 있으면 새로 만들지 않고 갱신한다.
   갱신 전에 원본을 임시 파일로 복사해 두고(검사의 `--previous`), `AUTO:body` 안만 다시 쓴다.
   메모 칸 내용, 사람 소유 frontmatter(`Reading-Status`, `Read-Depth`, `publish` 등), `AUTO:body` 밖은 글자 하나 바꾸지 않는다.
   `$VAULT/_archive/wiki-v1/`에 같은 논문의 옛 노트가 있으면 참고 자료로만 읽는다(사람이 쓴 메모가 있으면 새 노트의 해당 절 메모 칸으로 옮긴다).
2. **원문 수집.** 전문을 목표로 끝까지 읽는다(긴 PDF는 쪽 범위로 나눠서). 확보 범위를 `source-coverage`에 정직하게 적는다:
   `fulltext | section-extract | abstract-only | unknown`. 초록·검색 결과·웹 요약은 전문이 아니다.
3. **도표 목록(manifest).** 쓰기 전에 원문의 Figure/Table 전체를 임시 JSON으로 만든다
   (`${TMPDIR:-/tmp}/paper-driller-<slug>/manifest.json`). 형식은 `references/note-spec.md` 6절.
4. **핵심 도표 고르기와 이미지.** 결론을 받치는 도표 3~4개를 고른다. 슬러그는
   `python3 "$VAULT/Public/_tools/paper_note.py" slug "<노트 경로>"`로 얻는다. 이미지는
   `/opt/homebrew/bin/python3 "$VAULT/Public/_tools/paper_figures.py" --arxiv <id> (또는 --pdf <파일>) --labels "Figure 2,Table 1" --out "<노트 폴더>/assets/<slug>"`로 만든다.
   **만든 이미지를 하나씩 직접 열어 본다.** 잘림·빈 그림·다른 그림이면 그 파일을 지우고 노트에 `이미지 없음: 자동 추출 실패`라고 쓴다.
   이용 조건이 엄격한 출판사 논문(arXiv·CC 라이선스가 아님)은 이미지를 넣지 않고 `이미지 없음: 저작권`이라고 쓴다.
5. **작성.** `references/note-spec.md`대로 절 5개 + `Wiki 연결` + `BibTeX`를 쓴다. 저장 경로는 아래 "저장".
6. **검사.** 저장 직후 실행한다. 실패하면 고치고 다시 실행한다(최대 3회, 그래도 실패하면 보고하고 멈춘다).
   ```bash
   python3 "$VAULT/Public/_tools/paper_note.py" count "$NOTE"      # 절별 글자 수와 상한
   python3 "$VAULT/Public/_tools/paper_note.py" check "$NOTE" --manifest "$MANIFEST" [--previous "$OLD"]
   ```
   `RESULT: PASS`가 나와야 완료다. 글자 수가 넘치면 절 사이 중복부터 줄이고, 그다음 덜 중요한 결과를 "나머지 도표" 한 줄로 내린다.
7. **위키 연결.** `python3 "$VAULT/Public/_tools/build_catalog.py"`, `python3 "$VAULT/Public/_tools/lint.py"`를 실행하고,
   새 오류가 없으면 `$VAULT/_wiki/log.md`에 `## [YYYY-MM-DD] driller | <노트 제목>` 한 줄을 남긴다.

## 공통 규칙

- 원문에 없는 수치·조건·주장·도표·링크를 만들지 않는다. 기억 속 논문 내용으로 빈칸을 채우지 않는다.
- 근거 위치는 짧게: `(§3.2)`, `(Fig. 3)`, `(Table 2)`, `(p.7)`. 확인 못 했으면 `[위치 미확인]`.
- 기본은 저자 주장이다. 작성자가 추론·해석한 문장에만 `[해석]`을 붙인다. 그래프에서 눈으로 읽은 값도 `[해석]`.
- 원문을 다 읽고도 없으면 "보고되지 않았다", 읽지 못한 범위면 "확보한 범위에서 확인하지 못했다". 둘을 섞지 않는다.
- "모두·항상·최고·원인·필수"는 그 범위의 근거가 있을 때만 쓴다. 저자 문장과 표가 다르면 둘 다 적는다.
- 용어는 지우지 않고 처음 나올 때 괄호로 짧게 풀어 쓴다. 예: `attention head(어느 단어를 볼지 나눠 맡는 계산 단위)`.
- `abstract-only`·`unknown` 노트는 `quality-status: review`, 개요 첫머리에 한 번만 한계를 밝히고 채울 수 없는 절은 "확보한 범위에 없음" 한 줄.

## 저장

- 학술 논문만 `type: paper`. AI 논문은 `$VAULT/Public/AI/Papers/`, 그 밖은 `$VAULT/Public/<domain>/`. 하위 폴더를 새로 만들지 않는다.
- 파일 이름은 논문 제목(파일 이름에 못 쓰는 `/ : ? *` 등은 ` - `나 공백으로). 이미지는 노트 폴더의 `assets/<slug>/`.
- 새 노트의 `Reading-Status`는 `"☑️ Not Started"`, `Read-Depth`는 비우고, `publish: draft`. 이 셋은 사람이 바꾼다.
- `Category`·`linked-bases`·`Lab`은 확실할 때만 채우고 추측하지 않는다.

## References

- `references/note-spec.md` — 노트 규격(절별 상한, 도표 블록, 메모 칸, frontmatter 17키, manifest 형식, 전체 예시)
- `$VAULT/Public/_tools/paper_note.py` — 유일한 검사기 (`check`, `count`, `slug`, `hook`)
- `$VAULT/Public/_tools/paper_figures.py` — 핵심 도표 자르기
- `scripts/validate-driller.sh` — 이 스킬 문서와 검사기 테스트의 정적 점검
