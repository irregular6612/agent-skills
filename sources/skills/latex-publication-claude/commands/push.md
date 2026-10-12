# /latex:push — Git / Overleaf push

LaTeX 프로젝트를 GitHub 또는 Overleaf로 토큰 기반 push.

## When to Use

- LaTeX 프로젝트를 처음 GitHub 또는 Overleaf에 push할 때
- 빌드 캐시/IDE 설정을 git에서 제외하면서 push할 때
- `.gitignore`로 민감 파일을 안전하게 관리할 때

## Usage

```
/latex:push <project_dir> [remote_url]
```

내부적으로 `scripts/push_remote.sh` 호출.

## Token Authentication

우선순위:
1. 환경변수 `$GITHUB_TOKEN` 또는 `$OVERLEAF_TOKEN`
2. 사용자에게 직접 입력 요청

토큰은 절대 git에 커밋되면 안 됨. push URL에만 사용 후 즉시 폐기.

## Git URL Formats

| 서비스 | URL 형식 |
|--------|---------|
| GitHub | `https://<user>:<token>@github.com/<user>/<repo>.git` |
| Overleaf | `https://git:<token>@git.overleaf.com/<project_id>` |

## Workflow

```
Phase 1: 초기화
├── git init (없는 경우)
├── .gitignore 생성/확인
├── remote 설정
└── user.name / user.email 설정

Phase 2: 커밋
├── git add (tex, bib, gitkeep, gitignore만)
├── 커밋 메시지 자동 생성
└── git commit

Phase 3: Push
├── git push (또는 force push for 초기 설정)
└── 결과 확인

Phase 4: Critique
├── git ls-files로 tracked 파일 확인
├── 민감 정보 (토큰 등) 커밋에 포함되지 않았는지 확인
└── remote 연결 상태 확인
```

## .gitignore Template

`../templates/gitignore`를 사용. 핵심 내용:

```
*.aux
*.log
*.out
*.toc
*.bbl
*.blg
*.synctex.gz
*.fls
*.fdb_latexmk
*.pdf
.DS_Store
.vscode/
build/
.build/
```

---

## Common Issues & Fixes

| 문제 | 원인 | 해결 |
|------|------|------|
| Overleaf git 403 | 무료 플랜 | Premium 플랜 필요, 또는 GitHub 사용 |
| `RPC failed; HTTP 401` | 토큰 만료/잘못됨 | 새 토큰 생성, env var 재설정 |
| `pack exceeds maximum allowed size` | 빌드 artifact 또는 PDF가 커밋됨 | `.gitignore` 확인, `git rm --cached` |
| 한글 파일명 한자가 깨짐 | `core.quotepath` 기본값 | `git config core.quotepath false` |

더 많은 이슈: `../references/common-issues.md`.

## Related Subcommands

- `/latex:structure` — push 전에 프로젝트 구조화
- `/latex:build` — push 전에 PDF 빌드 검증
