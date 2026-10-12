# GIST Library Facility-Reservation — API & Room Catalog

All facts below were captured live from `library.gist.ac.kr` on 2026-06-03 by
observing the SPA's network traffic. If the site changes, re-verify against the
running app.

## Endpoints

Base: `https://library.gist.ac.kr:8443/work/` — **all POST, JSON body**.
Every request carries `Authorization: Bearer <JWT>` and
`Content-Type: application/json;charset=UTF-8`. The JWT is issued at login and the
Angular app stores it in `localStorage`/`sessionStorage`; the search snippet in
SKILL.md reads it from there at call time (a value matching `eyJ...\.....\.....`).
Never print the token.

Responses share the envelope `{ "status":200, "message":"OK", "data": <payload> }`.

### `getFacilityInfo` — room list + your limits
Request: `{}` (empty object is fine).
`data.facility[]` — every room: `{ FAC_NM, FLOOR, ROOM_ID, ROOM_GROUP, ROOM_NO }`.
`data.info` — the logged-in user:
`{ USER_ID, USER_NM, DEPARTMENT_NM, KOREAN_NM (e.g. 학부생),
   DATE_START, DATE_END,         // reservable window, e.g. 2026-06-03 .. 2026-07-02
   FAC_DUR4,                      // max hours per DAY  (undergrad = 4)
   FAC_DUR5 }                     // max hours per MONTH (undergrad = 80)
Use this to learn the valid date range and the per-day / per-month caps.

### `getRoom` — hourly availability for one room on one date  ← the workhorse
Request: `{ START_DT_YYYYMMDD, END_DT_YYYYMMDD, ROOM_ID, RES_YYYYMMDD }`
(use the month bounds for the two DT fields, e.g. `"20260601"`/`"20260701"`, and the
target day for `RES_YYYYMMDD`).
Response `data`:
- `normalRoomGroupDates[0]` → `{ FAC_NM, FLOOR, ROOM_ID, ROOM_NO, FROM_TIME, TO_TIME }`
  — operating hours are `FROM_TIME..TO_TIME` inclusive (observed **8..23**, i.e.
  bookable `RES_HOUR` ∈ {8,…,23}; slot `Nh` means N:00–(N+1):00).
  **If this array is empty, the room is not bookable by this user that day — skip it.**
- `roomOther[]` → hours already booked by **other** people:
  `{ GROUP_NM, DEPT_NM, REMARK, RES_HOUR }` (e.g. 화학과 학부생 @ 20,21,22,23).
- `room[]` → **your own** existing bookings for that room/day (same shape).
- `notAvailableRoomDates[]`, `canAvailableRoomDates[]`, `infoCount` — usually unused here.

**Free hours = {FROM_TIME..TO_TIME} − roomOther.RES_HOUR − room.RES_HOUR.**

### `makeFacilityreservation` — reserve ONE hour (instant, no confirmation)
Request: `{ ROOM_ID, CREATE_ID:"<student id>", REMARK:"", RES_YYYYMMDD, RES_HOUR, ADMIN_YN:"N" }`.
Success: `{ status:200, message:"OK", data:<n> }`. Call once per hour to book a range.
**This is a real reservation the instant it returns 200 — only call it after the
user has explicitly confirmed the room + date + hours.**

### `cancelFacilityreservation` — cancel ONE hour
Request: `{ ROOM_ID, RES_YYYYMMDD, RES_HOUR, RES_ID }`.
`RES_ID` comes from `getMyReservation`. Success → `200`.

### `getMyReservation` — your current/upcoming reservations
Returns your bookings with their `RES_ID`, room, date, hour — used to verify a
booking and to find `RES_ID` for cancellation.

### `getFacilityReservation` — month-level calendar data
Request: `{ START_DT, END_DT, ROOM_ID }`. Drives the calendar's day markers; not
needed for the per-day search (use `getRoom`). Empty `result` = nothing booked.

## Booking-loop reference (adapt; run after explicit confirmation)

```js
async () => {
  let tok = null;
  for (const s of [localStorage, sessionStorage]) {
    for (let i = 0; i < s.length; i++) {
      const m = (s.getItem(s.key(i)) || '').match(/eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+/);
      if (m) { tok = m[0]; break; }
    }
    if (tok) break;
  }
  if (!tok) return { error: 'not logged in' };

  const CREATE_ID = '<학번>';      // the student id (CREATE_ID == login id)
  const ROOM_ID = 302;
  const RES_YYYYMMDD = '20260610';
  const hours = [14, 15, 16, 17];    // 14:00–18:00
  const results = [];
  for (const RES_HOUR of hours) {
    const r = await fetch('https://library.gist.ac.kr:8443/work/makeFacilityreservation', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json;charset=UTF-8', 'Authorization': 'Bearer ' + tok },
      body: JSON.stringify({ ROOM_ID, CREATE_ID, REMARK: '', RES_YYYYMMDD, RES_HOUR, ADMIN_YN: 'N' })
    });
    const j = await r.json();
    results.push({ hour: RES_HOUR, ok: j.status === 200, message: j.message });
  }
  return results;
}
```

## Room catalog (capacity is embedded in `FAC_NM`)

| ROOM_ID(s) | Floor | Type | Capacity | Notes |
|---|---|---|---|---|
| 108 | 1F | Mini Theater | 50 | **Undergrads have NO permission** (shows 예약권한없음) |
| 110 | 1F | Exhibition Hall | — | |
| 202, 203, 204 | 2F | Group Study Room | **8명** | |
| 205–210 | 2F | Group Study Room | **5명** | |
| 219–236 | 2F | Small-sized Carrel | **1인용** (개인석) | |
| 237–240 | 2F | Medium-sized Carrel | 1–2인용 | **No booking permission for this user — never search or report (non-bookable area)** |
| 302–307 | 3F | Group Study Room | **10명** | |
| 310 | 3F | Lecture Room | **30명** | |
| 406–409 | 4F | Multi Media Room | — | |

**Default search scope (floors 2–3, the rooms a student actually uses):**
`[202,203,204,205,206,207,208,209,210, 219..236, 302,303,304,305,306,307]`
= 2F group study + 2F **small** carrels (219–236) + 3F group study.

**Excluded from the default search:**
- `237`–`240` — 2F Medium-sized Carrels. **The user has no booking permission here
  — a non-bookable area. Never search and never report these, even on explicit request.**
- `310` — 3F Lecture Room (30인). A lecture hall, not a study space the user wants
  surfaced (only include if the user explicitly asks).
- `108`/`110` (1F), `406`–`409` (4F), and any room the undergrad has no permission for.

Hours of operation: **08:00–23:00** (`RES_HOUR` 8–23). Each reservation is one hour;
book consecutive hours to hold a longer block.

## Availability colour codes (only relevant if reading the DOM instead of the API)

In the time-slot table the inner cell `<div>` carries a class:
- `color-b` → 예약 가능 (free) — empty cell.
- `color-c` → 타인예약 (booked by someone else) — cell shows their dept/group.
- `color-d` → 예약불가 / 예약권한없음 (unavailable or no permission).
- (`color-a` / "W" marker → your own reservation, 내 예약.)

The JSON API is preferred over DOM scraping — it is faster and unambiguous.
