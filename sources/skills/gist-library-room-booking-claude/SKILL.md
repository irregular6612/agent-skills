---
name: gist-library-room-booking
description: >-
  GIST 중앙도서관 시설(그룹스터디룸·캐럴·강의실, library.gist.ac.kr) 검색·예약. 날짜·시간대를 주면 빈 방을(기본 2–3층) 정원·운영시간과 함께 나열하고, 사용자 확정 시 예약. 트리거: 빈 스터디룸/회의실/세미나실/강의실 찾기, what rooms are free, 도서관 시설예약, 미팅룸 예약, 스터디룸 예약, GIST library room booking. Playwright MCP 필요.
compatibility: >-
  Requires the Playwright MCP server (mcp__plugin_playwright_playwright__*).
  Requires a credentials file at ~/.claude/gist-library-credentials.local.json
  (or GIST_LIB_ID / GIST_LIB_PW env vars).
---

# GIST Library Room Booking

Find and reserve rooms in the GIST central library facility-reservation system
(`https://library.gist.ac.kr/#/facilityReservation`). The site is an Angular SPA
backed by a clean JSON API; this skill logs in through the browser, then talks to
that API from inside the authenticated page.

## The one rule that matters most

**A single booking call reserves the slot instantly. There is no "are you sure?"
step on the site.** In the UI, *clicking an available time cell books it the moment
you click* — the user found this out the hard way. Therefore:

> **Never reserve anything until the user has explicitly confirmed the exact
> room + date + hours.** Searching is always safe (read-only). Booking is a real,
> outward action — treat every `makeFacilityreservation` call as irreversible from
> the user's point of view (it is cancellable, but only as a second deliberate step).

When you present search results, *stop and ask which room/hours to book*. Do not
chain a booking onto a search in the same breath.

## What this skill does

1. **Login** — drive the login form once per session.
2. **Search** — given a target date and (optionally) a time window and floors,
   list every free room with its open hours and capacity.
3. **Book** — only after explicit confirmation, reserve the chosen room for each
   requested hour, then verify.

**Default scope = floors 2–3 group study rooms + personal carrels (개인 열람석),
i.e. the rooms a student actually uses.** Concretely: 2F group rooms (202–210),
2F **small** carrels (219–236), and 3F group rooms (302–307). **Exclude by default
— never search and never report these:**
- **2F Medium-sized Carrels (237–240)** — the user has **no booking permission**
  here. This is a non-bookable area; do not surface it even if the API returns hours.
- the 3F lecture room (310, 30인) — not a study space the user wants surfaced;
- 1F/4F rooms and anything else the undergrad has no permission for.

Search a wider set (e.g. include 310 or 4F) only when the user explicitly asks.
**Even on explicit request, do not include 237–240** — the user cannot book them.

## Step 0 — Read credentials (never echo them)

Load the login from, in order of preference:
1. Env vars `GIST_LIB_ID` / `GIST_LIB_PW`, else
2. `~/.claude/gist-library-credentials.local.json` → `{ "id": ..., "pw": ... }`.

Read them with a tool, hold them only as long as needed, and **never print the
password or the session token into the conversation.** If neither source exists,
ask the user how they want to provide the login (don't invent one).

## Step 1 — Log in

Using the Playwright MCP tools:

1. `browser_navigate` → `https://library.gist.ac.kr/#/login`
2. A chatbot pop-up may cover the page — if a "close" / "다시 보지 않기" button is
   present, close it first.
3. `browser_snapshot`, then fill the **ID** and **Password** textboxes
   (`browser_fill_form` or `browser_type`) with the loaded credentials.
4. Click the **Log-in** button (it is disabled until both fields are filled).
5. On success the page redirects to `#/home` and the header shows **Log Out**.
6. `browser_navigate` → `https://library.gist.ac.kr/#/facilityReservation`.

If login fails (still on `#/login`, or an error toast), tell the user — most
likely the password changed. Do not retry blindly more than once.

## Step 2 — Search for available rooms

Everything downstream uses the site's JSON API, called from inside the page so the
browser attaches the auth token automatically. Use **one** `browser_evaluate` call
that loops over the candidate rooms and returns *only availability data* (no token).

The room catalog, capacities, hours, and the exact request/response shapes live in
`references/api-and-rooms.md`. **Read that file** before writing the evaluate snippet.

The search logic per room (endpoint `POST .../work/getRoom`):
- `freeHours = [FROM_TIME .. TO_TIME]` minus hours in `roomOther` (others' bookings)
  minus hours in `room` (your own existing bookings).
- Then intersect `freeHours` with the user's requested window (e.g. 14–18 →
  hours 14,15,16,17 must all be free for a 14:00–18:00 block).

Reference snippet (adapt rooms/date/window; it reads the token inside the page and
returns only availability):

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
  if (!tok) return { error: 'not logged in (no token)' };

  const date = '20260610';                 // RES_YYYYMMDD, the target day
  const monthStart = '20260601', monthEnd = '20260701';
  // Default scope: 2F group + 2F SMALL carrels + 3F group.
  // EXCLUDED (never add): 237–240 (2F medium carrels, no booking permission), 310 (lecture room).
  const rooms = [
    202,203,204,205,206,207,208,209,210,                                          // 2F group study
    219,220,221,222,223,224,225,226,227,228,229,230,231,232,233,234,235,236,      // 2F small carrels
    302,303,304,305,306,307,                                                      // 3F group study
  ];
  const out = [];
  for (const ROOM_ID of rooms) {
    const r = await fetch('https://library.gist.ac.kr:8443/work/getRoom', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json;charset=UTF-8', 'Authorization': 'Bearer ' + tok },
      body: JSON.stringify({ START_DT_YYYYMMDD: monthStart, END_DT_YYYYMMDD: monthEnd, ROOM_ID, RES_YYYYMMDD: date })
    });
    const j = await r.json();
    const meta = (j.data.normalRoomGroupDates || [])[0] || {};
    if (meta.FROM_TIME == null) { continue; }   // no permission / not bookable that day
    const taken = new Set([
      ...(j.data.roomOther || []).map(o => o.RES_HOUR),
      ...(j.data.room || []).map(o => o.RES_HOUR),
    ]);
    const free = [];
    for (let h = meta.FROM_TIME; h <= meta.TO_TIME; h++) if (!taken.has(h)) free.push(h);
    out.push({ roomId: ROOM_ID, roomNo: meta.ROOM_NO, floor: meta.FLOOR, facility: meta.FAC_NM, freeHours: free });
  }
  return { date, rooms: out };
}
```

Then present a clear table to the user. For each qualifying room show:
**호실(Room No.)**, **수용 인원(capacity)**, **층(floor)**, and **예약 가능 시간대
(free hours)**. Derive capacity from the facility name per `references/api-and-rooms.md`
(e.g. "for 10 people" → 10명; carrels → 1인용 개인석). Format hours human-readably,
e.g. `14h` slot = 14:00–15:00, so free hours [14,15,16,17] = "14:00–18:00 가능".

If the user gave a time window, lead with rooms that fully cover it; still list
partial matches below so they can adjust.

## Step 3 — Book (only after explicit confirmation)

Confirm back to the user in plain language *before* doing anything:
"Room 302 (3F, 10인용)에 2026-06-10 14:00–18:00 (14·15·16·17시) 예약합니다. 진행할까요?"

Only once they say yes, book **each hour** in the range (one API call per hour —
the system reserves a single hour at a time). Endpoint `POST .../work/makeFacilityreservation`,
body `{ ROOM_ID, CREATE_ID:<student id>, REMARK:"", RES_YYYYMMDD, RES_HOUR, ADMIN_YN:"N" }`.
A `200` with `data` ≥ 0 means success. See `references/api-and-rooms.md` for the exact
shape and a ready-to-adapt loop.

Watch the limits while booking: **4 hours/day and 80 hours/month** for undergrads
(values come from `getFacilityInfo.info.FAC_DUR4 / FAC_DUR5`). If a request exceeds
the daily cap, say so and ask how to proceed rather than partially booking silently.

After booking, verify with `POST .../work/getMyReservation` (or re-run the search for
that room) and report exactly which hours were reserved. If any hour failed (e.g. it
was taken between search and book), report which succeeded and which didn't.

## Cancelling

The user's core request does not include cancellation, but if they ask, the endpoint
is `POST .../work/cancelFacilityreservation` with
`{ ROOM_ID, RES_YYYYMMDD, RES_HOUR, RES_ID }` (the `RES_ID` comes from
`getMyReservation`). Same rule: confirm the exact slot first. The UI path is
나의예약현황 → 취소 → confirm dialog.

## Failure modes to handle gracefully

- **Not logged in / token missing** → redo Step 1.
- **Empty `normalRoomGroupDates`** for a room → that room isn't bookable by this user
  that day (e.g. undergrads have no permission for Room 108); skip it silently.
- **Date outside the reservable window** (`getFacilityInfo.info.DATE_START..DATE_END`,
  ~today through +30 days) → tell the user the valid range instead of failing.
- **Slot taken between search and booking** → report the conflict; offer the next
  free room/hour from the latest search.
