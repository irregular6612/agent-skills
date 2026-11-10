#!/usr/bin/env python3
"""Drive library.gist.ac.kr through the Aside browser (`aside repl`), for Claude Code and Codex alike.

Each command is ONE `aside repl` run: log in, call the site's JSON API from inside the
authenticated page, print one JSON result, close the tab. `aside repl` sessions are
incognito and end with the run, so every command logs in again.

  python3 aside_run.py search --date 2026-06-10 [--from 14 --to 18] [--rooms 302,303]
  python3 aside_run.py book   --room 302 --date 2026-06-10 --hours 14-17 [--confirmed]
  python3 aside_run.py mine
  python3 aside_run.py cancel --room 302 --date 2026-06-10 --hour 14 --res-id 123 [--confirmed]

Credentials: env GIST_LIB_ID / GIST_LIB_PW, else ~/.claude/gist-library-credentials.local.json
({"id": ..., "pw": ...}). They go to `aside repl` on stdin, never on the command line,
and any echo of the password in Aside's output is masked. The JWT never leaves the page.
book/cancel do nothing without --confirmed (they only print the plan).
Standard library only.
"""
import argparse
import datetime as dt
import json
import os
import subprocess
import sys
from pathlib import Path

CRED_FILE = Path.home() / ".claude" / "gist-library-credentials.local.json"
API = "https://library.gist.ac.kr:8443/work/"
# 2F group study + 2F small carrels + 3F group study. Never 237–240 (no booking permission).
DEFAULT_ROOMS = list(range(202, 211)) + list(range(219, 237)) + list(range(302, 308))
FORBIDDEN_ROOMS = set(range(237, 241))

# Runs inside the logged-in page: reads the JWT there and calls the API, so the token
# is never returned to the REPL or printed.
PAGE_CALL = r"""
async ({ api, calls }) => {
  let tok = null;
  for (const s of [localStorage, sessionStorage]) {
    for (let i = 0; i < s.length && !tok; i++) {
      const m = (s.getItem(s.key(i)) || '').match(/eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+/);
      if (m) tok = m[0];
    }
  }
  if (!tok) return { error: 'not logged in (no token)' };
  const out = [];
  for (const [endpoint, body] of calls) {
    const r = await fetch(api + endpoint, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json;charset=UTF-8', 'Authorization': 'Bearer ' + tok },
      body: JSON.stringify(body),
    });
    let j = null;
    try { j = await r.json(); } catch (e) { j = { status: r.status, message: 'non-JSON response' }; }
    out.push(j);
  }
  return { results: out };
}
"""

TEMPLATE = r"""
const __gl = await (async () => {
  const t = await openTab('https://library.gist.ac.kr/#/login');
  try {
    await t.fill('#userId', __ID__);
    await t.fill('#userPwd', __PW__);
    try { await t.locator('button[type="submit"]').first().click({ timeout: 8000 }); }
    catch (e) { await t.evaluate(() => document.querySelector('#userPwd').form.requestSubmit()); }
    const hasTok = () => [localStorage, sessionStorage].some(s =>
      Array.from({ length: s.length }, (_, i) => s.getItem(s.key(i)) || '').some(v => /eyJ[\w-]+\.[\w-]+\.[\w-]+/.test(v)));
    let ok = false;
    for (let i = 0; i < 30 && !ok; i++) { ok = await t.evaluate(hasTok); if (!ok) await sleep(500); }
    if (!ok) return { error: 'login failed (still no token) — check the ID/password' };
    const pageCall = __PAGE_CALL__;
    const run = (calls) => t.evaluate(pageCall, { api: __API__, calls });
    __TASK__
  } finally {
    await closeTab(t);
  }
})();
console.log('SKM_RESULT ' + JSON.stringify(__gl));
"""

# --- per-command JS (uses `run(calls)`; returns a JSON-able value) ---

TASK_SEARCH = r"""
    const q = __ARGS__;
    const res = await run(q.rooms.map(ROOM_ID => ['getRoom',
      { START_DT_YYYYMMDD: q.monthStart, END_DT_YYYYMMDD: q.monthEnd, ROOM_ID, RES_YYYYMMDD: q.date }]));
    if (res.error) return res;
    const rooms = [];
    res.results.forEach((j, k) => {
      const meta = ((j.data || {}).normalRoomGroupDates || [])[0] || {};
      if (meta.FROM_TIME == null) return;                 // not bookable by this user that day
      const taken = new Set([...(j.data.roomOther || []), ...(j.data.room || [])].map(o => o.RES_HOUR));
      const free = [];
      for (let h = meta.FROM_TIME; h <= meta.TO_TIME; h++) if (!taken.has(h)) free.push(h);
      rooms.push({ roomId: q.rooms[k], roomNo: meta.ROOM_NO, floor: meta.FLOOR, facility: meta.FAC_NM, freeHours: free,
                   coversWindow: q.window ? q.window.every(h => free.includes(h)) : null });
    });
    return { date: q.date, window: q.window, rooms };
"""

TASK_BOOK = r"""
    const q = __ARGS__;
    const info = await run([['getFacilityInfo', {}]]);
    if (info.error) return info;
    const lim = ((info.results[0] || {}).data || {}).info || {};
    if (lim.FAC_DUR4 && q.hours.length > Number(lim.FAC_DUR4))
      return { error: `daily cap is ${lim.FAC_DUR4} hours; ${q.hours.length} requested — nothing booked` };
    const made = await run(q.hours.map(RES_HOUR => ['makeFacilityreservation',
      { ROOM_ID: q.room, CREATE_ID: __ID__, REMARK: '', RES_YYYYMMDD: q.date, RES_HOUR, ADMIN_YN: 'N' }]));
    const after = await run([['getRoom', { START_DT_YYYYMMDD: q.monthStart, END_DT_YYYYMMDD: q.monthEnd,
                                           ROOM_ID: q.room, RES_YYYYMMDD: q.date }]]);
    const mine = new Set((((after.results || [])[0] || {}).data || {}).room?.map(o => o.RES_HOUR) || []);
    return { room: q.room, date: q.date,
             perHour: q.hours.map((h, k) => ({ hour: h, status: (made.results[k] || {}).status,
                                               message: (made.results[k] || {}).message, nowYours: mine.has(h) })) };
"""

TASK_MINE = r"""
    const res = await run([['getMyReservation', {}]]);
    if (res.error) return res;
    return res.results[0];
"""

TASK_CANCEL = r"""
    const q = __ARGS__;
    const res = await run([['cancelFacilityreservation',
      { ROOM_ID: q.room, RES_YYYYMMDD: q.date, RES_HOUR: q.hour, RES_ID: q.resId }]]);
    if (res.error) return res;
    return { cancelled: { room: q.room, date: q.date, hour: q.hour }, response: res.results[0] };
"""


def credentials():
    uid, pw = os.environ.get("GIST_LIB_ID"), os.environ.get("GIST_LIB_PW")
    if uid and pw:
        return uid, pw
    try:
        d = json.loads(CRED_FILE.read_text())
        if d.get("id") and d.get("pw"):
            return str(d["id"]), str(d["pw"])
    except (OSError, ValueError):
        pass
    sys.exit("no credentials: set GIST_LIB_ID/GIST_LIB_PW or create " + str(CRED_FILE)
             + ' with {"id": ..., "pw": ...} (ask the user; never invent one)')


def ymd(s):
    s = s.replace("-", "")
    dt.datetime.strptime(s, "%Y%m%d")
    return s


def month_bounds(d):
    first = dt.date(int(d[:4]), int(d[4:6]), 1)
    nxt = (first.replace(day=28) + dt.timedelta(days=4)).replace(day=1)
    return first.strftime("%Y%m%d"), nxt.strftime("%Y%m%d")


def hours_arg(s):
    if "-" in s:
        a, b = s.split("-", 1)
        return list(range(int(a), int(b) + 1))
    return [int(h) for h in s.split(",")]


def build(task, args, uid, pw):
    code = TEMPLATE.replace("__PAGE_CALL__", PAGE_CALL.strip()).replace("__TASK__", task)
    code = code.replace("__ARGS__", json.dumps(args)).replace("__API__", json.dumps(API))
    return code.replace("__ID__", json.dumps(uid)).replace("__PW__", json.dumps(pw))


def run_aside(code, pw):
    p = subprocess.run(["aside", "repl", "--file", "-"], input=code, capture_output=True, text=True, timeout=180)
    out = (p.stdout + p.stderr).replace(pw, "***")
    for line in out.splitlines():
        if line.startswith("SKM_RESULT "):
            return json.loads(line[len("SKM_RESULT "):])
    return {"error": "aside repl gave no result", "exit": p.returncode, "output": out[-1500:]}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("search")
    s.add_argument("--date", required=True, type=ymd)
    s.add_argument("--from", dest="h_from", type=int)
    s.add_argument("--to", dest="h_to", type=int, help="end hour (exclusive), e.g. --from 14 --to 18 = 14:00–18:00")
    s.add_argument("--rooms", help="comma-separated ROOM_IDs (default: 2F group, 2F small carrels, 3F group)")
    b = sub.add_parser("book")
    b.add_argument("--room", required=True, type=int)
    b.add_argument("--date", required=True, type=ymd)
    b.add_argument("--hours", required=True, type=hours_arg, help="14-17 or 14,15 (start hours)")
    b.add_argument("--confirmed", action="store_true", help="the user explicitly confirmed room + date + hours")
    sub.add_parser("mine")
    c = sub.add_parser("cancel")
    c.add_argument("--room", required=True, type=int)
    c.add_argument("--date", required=True, type=ymd)
    c.add_argument("--hour", required=True, type=int)
    c.add_argument("--res-id", required=True)
    c.add_argument("--confirmed", action="store_true")
    ap.add_argument("--print-code", action="store_true", help="print the generated REPL code (password masked) and exit")
    a = ap.parse_args(argv)

    room = getattr(a, "room", None)
    if room in FORBIDDEN_ROOMS or (getattr(a, "rooms", None) and FORBIDDEN_ROOMS & {int(r) for r in a.rooms.split(",")}):
        sys.exit("rooms 237–240 are not bookable for this user; not searching or booking them")
    if a.cmd in ("book", "cancel") and not a.confirmed and not a.print_code:
        plan = {"would": a.cmd, "room": a.room, "date": a.date,
                "hours" if a.cmd == "book" else "hour": a.hours if a.cmd == "book" else a.hour}
        print(json.dumps({"not_run": "needs --confirmed after the user explicitly agrees", "plan": plan}, ensure_ascii=False))
        return 2

    if a.cmd == "search":
        ms, me = month_bounds(a.date)
        window = list(range(a.h_from, a.h_to)) if a.h_from is not None and a.h_to is not None else None
        rooms = [int(r) for r in a.rooms.split(",")] if a.rooms else DEFAULT_ROOMS
        task, args = TASK_SEARCH, {"date": a.date, "monthStart": ms, "monthEnd": me, "window": window, "rooms": rooms}
    elif a.cmd == "book":
        ms, me = month_bounds(a.date)
        task, args = TASK_BOOK, {"room": a.room, "date": a.date, "hours": a.hours, "monthStart": ms, "monthEnd": me}
    elif a.cmd == "mine":
        task, args = TASK_MINE, {}
    else:
        task, args = TASK_CANCEL, {"room": a.room, "date": a.date, "hour": a.hour, "resId": a.res_id}

    if a.print_code:
        print(build(task, args, "<id>", "***"))
        return 0
    uid, pw = credentials()
    res = run_aside(build(task, args, uid, pw), pw)
    print(json.dumps(res, ensure_ascii=False, indent=1))
    return 1 if isinstance(res, dict) and res.get("error") else 0


if __name__ == "__main__":
    sys.exit(main())
