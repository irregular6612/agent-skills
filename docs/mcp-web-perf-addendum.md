# MCP web-perf 계획 보완

이 문서는 t_093ae44e의 64행 계획에 두 reference-only 행을 추가한다. 기존 35행 ASK_USER와 제외 정책은 변경하지 않는다. 등록을 추가하거나 제거하는 승인이 아니다.

## 수정한 repo-owned 문서

sources/skills/web-perf-codex/SKILL.md는 bare Chrome API 호출로 가용성을 시험하지 않는다. 현재 세션의 도구 목록과 권한을 먼저 확인한다. 노출된 웹 문서 조회 및 정적 코드 분석을 기본으로 사용한다. 이미 설치된 사용자 승인 CLI가 있을 때만 실측 대안으로 사용한다. 도구가 없으면 trace/Core Web Vitals/runtime a11y 측정이 불가능하다고 기록하고 측정 범위는 중단한다. Chrome API 예시와 단계 1–4는 전체가 조건부다. name/description와 manifest discovery 계약은 보존한다. 따라서 보존한 description은 현재 환경의 측정 가능성을 보증하지 않는다.

## 새 ASK_USER 예외

파일: /Users/bagjuhyeon/.claude/plugins/cache/cloudflare/cloudflare/1.0.0/skills/web-perf/SKILL.md
서버: chrome-devtools
harness: Claude
scope: active-external-plugin-reference-only

20행은 navigate_page/performance_start_trace를 먼저 호출하도록 지시한다. 22–29행은 설치를 권장한다. 64행 이후 trace/API workflow가 이어진다. 현재 user/활성 plugin 등록에는 이 서버가 없다. 활성 문서이므로 old cache 제외 규칙으로 숨기지 않는다. 외부 upstream 수정 권한이 없으므로 cache는 읽기만 하고 ASK_USER로 보고한다. 이는 KEEP이나 실제 지원 가능 판정이 아니다.

사용자 질문: Cloudflare의 web-perf skill을 그대로 유지할까요, 아니면 승인된 원본 업데이트/개별 skill 보완 경로로 바꿀까요? 그대로 두면 미등록 chrome-devtools 호출·설치 안내가 남고 현재 trace/Core Web Vitals/a11y 측정은 사용할 수 없습니다. 보완하면 정적 분석·기존 보고서 경로는 쓸 수 있지만 별도 승인된 측정 도구 없이 실측 기능은 얻지 못합니다. 이 결정은 Cloudflare의 다른 skill과 서버를 끄는 결정이 아닙니다.

이 카드에서는 외부 plugin cache 수정·삭제, Cloudflare 전체 disable, MCP 설치를 수행하지 않는다. 후속 적용도 독립 verifier PASS 전에는 허용하지 않는다.

## 검사 범위와 한계

tools/mcp_reference_audit.py는 명시 mcp__server__tool, 여섯 Chrome bare API, chrome-devtools/Chrome DevTools MCP prose, 설치 권장과 금지 문구를 별도로 추출한다. 조건부 문서는 전체 safety gate를 갖춘 검토된 repo 문서에만 허용한다. ASK_USER는 정확한 파일·harness·서버에만 적용한다. 등록 이름은 연결/인증/도구 노출 증거가 아니다.

이 검사는 임의 prose·별칭·다른 언어의 모든 도구 의존성을 검증하지 못한다. 전체 활성 문서에서 unsupported 0을 보장한다고 표현하지 않는다. 보고하는 0은 명시된 토큰/여섯 bare API/알려진 prose 패턴과 예외 처리 범위에서만 의미가 있다. 기존 paper-driller prose 별도 검사와 old cache/trash/archive/Squid/denylist 제외 정책은 유지한다. ASK_USER로 남은 활성 plugin 의존성은 해결되지 않았다.
