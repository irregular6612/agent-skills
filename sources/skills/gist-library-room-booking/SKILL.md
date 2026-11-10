---
name: gist-library-room-booking
description: >-
  GIST 중앙도서관 시설(그룹스터디룸·캐럴·강의실, library.gist.ac.kr) 검색·예약. 날짜·시간대를 주면 빈 방을(기본 2–3층) 정원·운영시간과 함께 나열하고, 사용자 확정 시 예약. 트리거: 빈 스터디룸/회의실/세미나실/강의실 찾기, what rooms are free, 도서관 시설예약, 미팅룸 예약, 스터디룸 예약, GIST library room booking. 브라우저는 aside-browser 스킬(Aside CLI)로 다룸.
compatibility: >-
  Claude Code and Codex alike. Requires the aside-browser skill and the Aside CLI
  (`aside`, driven by scripts/aside_run.py through `aside repl`) — no MCP server.
  Requires a credentials file at ~/.claude/gist-library-credentials.local.json
  (or GIST_LIB_ID / GIST_LIB_PW env vars).
---

# GIST Library Room Booking

Find and reserve rooms in the GIST central library facility-reservation system
(`https://library.gist.ac.kr/#/facilityReservation`). The site is an Angular SPA
backed by a clean JSON API; this skill logs in through the browser, then talks to
that API from inside the authenticated page.

**Browser = the `aside-browser` skill.** Every step below is one shell command,
`python3 {스킬폴더}/scripts/aside_run.py <command>`, which runs a single `aside repl`
script: log in, call the API inside the page, print one JSON result, close the tab.
`{스킬폴더}` is the folder of this SKILL.md (Claude Code `~/.claude/skills/gist-library-room-booking`,
Codex `~/.codex/skills/gist-library-room-booking`). If `aside` is missing or outdated, follow the
`aside-browser` skill first (it installs/updates the CLI only with the user's permission).
`aside repl` sessions are incognito and end with each run, so every command logs in again —
that is expected, not a failure.

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

`aside_run.py` reads them itself and passes them to `aside repl` on stdin, so you never
need to read, type or print the password — and **never print the password or the
session token into the conversation.** If neither source exists the script stops and
says so; ask the user how they want to provide the login (don't invent one).

## Step 1 — Log in

Nothing to do by hand: each `aside_run.py` command fills `#userId` / `#userPwd` on
`https://library.gist.ac.kr/#/login`, submits, and waits for the session token. If it
returns `{"error": "login failed ..."}`, tell the user — most likely the password
changed. Do not retry blindly more than once.

## Step 2 — Search for available rooms

```bash
python3 {스킬폴더}/scripts/aside_run.py search --date 2026-06-10 --from 14 --to 18
# --rooms 302,303 to narrow; default = 2F group (202–210) + 2F small carrels (219–236) + 3F group (302–307)
```

It calls `POST .../work/getRoom` for each room (shapes in `references/api-and-rooms.md`)
and returns, per bookable room, `roomNo`, `floor`, `facility`, `freeHours`, and
`coversWindow` (true when every hour of `--from..--to` is free):
- `freeHours = [FROM_TIME .. TO_TIME]` minus hours in `roomOther` (others' bookings)
  minus hours in `room` (your own existing bookings).
- Rooms whose `normalRoomGroupDates` is empty (not bookable by this user that day) are skipped.
- Rooms 237–240 are refused by the script even if asked.

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

Only once they say yes, run:

```bash
python3 {스킬폴더}/scripts/aside_run.py book --room 302 --date 2026-06-10 --hours 14-17 --confirmed
```

Without `--confirmed` the script only prints the plan and books nothing — pass it only
after the user's explicit yes for that exact room + date + hours. It books **each hour**
(`POST .../work/makeFacilityreservation`, one call per hour), then re-reads the room and
returns `perHour[{hour, status, message, nowYours}]`. A `200` with `nowYours: true` means
that hour is booked.

Watch the limits while booking: **4 hours/day and 80 hours/month** for undergrads
(values come from `getFacilityInfo.info.FAC_DUR4 / FAC_DUR5`). The script refuses a request
longer than the daily cap without booking anything; say so and ask how to proceed.

After booking, report exactly which hours were reserved from `perHour` (or check with
`aside_run.py mine`, which returns `getMyReservation`). If any hour failed (e.g. it
was taken between search and book), report which succeeded and which didn't.

## Cancelling

The user's core request does not include cancellation, but if they ask: find the
`RES_ID` with `aside_run.py mine`, confirm the exact slot with the user, then
`aside_run.py cancel --room <id> --date <day> --hour <h> --res-id <RES_ID> --confirmed`
(`POST .../work/cancelFacilityreservation`). The UI path is
나의예약현황 → 취소 → confirm dialog.

## Failure modes to handle gracefully

- **Not logged in / token missing** → the script returns an `error`; run the command again once.
- **`aside` not found / outdated / Aside app not running** → follow the `aside-browser` skill.
- **Empty `normalRoomGroupDates`** for a room → that room isn't bookable by this user
  that day (e.g. undergrads have no permission for Room 108); skip it silently.
- **Date outside the reservable window** (`getFacilityInfo.info.DATE_START..DATE_END`,
  ~today through +30 days) → tell the user the valid range instead of failing.
- **Slot taken between search and booking** → report the conflict; offer the next
  free room/hour from the latest search.
