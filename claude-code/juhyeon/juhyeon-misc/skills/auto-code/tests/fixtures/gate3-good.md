# 샘플 기능 Implementation Plan

## Global Constraints

- Node >= 20.11

---

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
