# 샘플 기능 Implementation Plan

## Global Constraints

- Node >= 20.11

---

아래 블록은 "Task는 이렇게 쓴다"는 예시일 뿐 실제 Task가 아니다.
실제 Task 헤더가 하나도 없으므로 SDD task-brief는 아무것도 뽑지 못한다.
GATE3는 여기서 거부해야 한다 — 통과시키면 SDD에 들어가서야 터진다.

````markdown
### Task 1: 링버퍼

**Files:**
- Create: `src/ringbuffer.js`

**Interfaces:**
- Consumes: 없음
- Produces: `push(item): void`, `drain(): item[]`

- [ ] **Step 1: 실패하는 테스트 작성**

```js
test('overflow drops oldest', () => {})
```
````
