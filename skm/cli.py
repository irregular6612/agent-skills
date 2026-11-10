"""`install.py skm ...` — sub-mode commands: run / switch / modes / sync / prune.

install.py passes `scan(mode) -> skm nodes`; everything else lives here.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from . import analysis, audit, modes

PARENTS = ("day", "night")


def _resolve(scan, parent, mode_expr):
    nodes = scan(parent)
    rep = analysis.analyze(nodes, parent, use_llm=False, cache_only=True, log=lambda *_: None)
    res = modes.resolve(mode_expr, modes.load_config(), nodes, rep["categories"], rep["edges"])
    return nodes, rep, res


def _print_resolve(mode_expr, res):
    msg = "sub-mode {}: {} items".format(mode_expr, len(res["members"]))
    if res["added_by_closure"]:
        msg += " (closure added: {})".format(", ".join(res["added_by_closure"]))
    print(msg)
    if res["missing"]:
        print("  in submodes.json but not installed in this mode: " + ", ".join(res["missing"]))


def apply_mode(scan, sid, mode_expr, parent):
    nodes, rep, res = _resolve(scan, parent, mode_expr)
    if res["unknown_modes"]:
        print("unknown sub-mode: {} (see `install.py skm modes`)".format(", ".join(res["unknown_modes"])),
              file=sys.stderr)
        return None
    _print_resolve(mode_expr, res)
    modes.prepare(sid)                                   # folder first
    out = modes.link_set(sid, res["members"], nodes, mode_expr, parent)
    print("  {} links (+{} -{}) -> {}".format(out["total"], out["added"], out["removed"], out["dir"]))
    iss = analysis.mode_issues(rep, nodes, res["members"])  # one audit pass, cached verdicts only
    mark = "!" if any(i["severity"] in ("error", "warn") for i in iss) else "ok"
    print("  [{}] {} ({}): {}".format(mark, mode_expr, parent, audit.summarize(iss))
          + ("  (details: install.py check --mode {} --llm --submode {})".format(parent, mode_expr) if iss else ""))
    return res["members"]


def main(argv, scan):
    cmd_argv = []
    if "--" in argv:
        i = argv.index("--")
        argv, cmd_argv = argv[:i], argv[i + 1:]
    ap = argparse.ArgumentParser(prog="install.py skm", description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd")
    p_run = sub.add_parser("run", help="build a session folder for SUBMODE and run a command (default: claude)")
    p_run.add_argument("submode", help="e.g. paper or paper+office")
    p_run.add_argument("--mode", choices=PARENTS, default="day", help="parent mode whose installed skills are used")
    p_run.add_argument("--session", help="session id (default: new)")
    p_sw = sub.add_parser("switch", help="swap a session's skill set to another sub-mode")
    p_sw.add_argument("submode")
    p_sw.add_argument("--session", default=os.environ.get("SKM_SESSION"), help="default: $SKM_SESSION")
    p_mo = sub.add_parser("modes", help="list sub-modes (sizes after closure)")
    p_mo.add_argument("--mode", choices=PARENTS, default="day")
    p_mo.add_argument("--show", help="print the members of one sub-mode")
    p_mo.add_argument("--sessions", action="store_true", help="list session folders")
    sub.add_parser("sync", help="re-apply submodes.json to every session folder")
    p_pr = sub.add_parser("prune", help="archive stale session folders; report skills no sub-mode uses")
    p_pr.add_argument("--mode", choices=PARENTS, default="day")
    p_pr.add_argument("--days", type=int, default=7)
    p_pr.add_argument("--apply", action="store_true", help="actually move (default: preview)")
    args = ap.parse_args(argv)

    if args.cmd == "run":
        sid = args.session or modes.new_session_id(args.submode)
        if apply_mode(scan, sid, args.submode, args.mode) is None:
            return 2
        cmd = cmd_argv or ["claude"]
        if Path(cmd[0]).name == "claude":
            cmd = [cmd[0]] + modes.claude_args(sid) + cmd[1:]
        env = dict(os.environ, SKM_SESSION=sid, SKM_MODE=args.submode)
        print("session {} -> {}".format(sid, " ".join(cmd)))
        sys.stdout.flush()
        os.execvpe(cmd[0], cmd, env)
    elif args.cmd == "switch":
        if not args.session:
            ap.error("--session <id> is required (see `install.py skm modes --sessions`)")
        meta = modes.load_json(modes.session_dir(args.session) / "session.json")
        if not meta:
            ap.error("no session " + args.session)
        if apply_mode(scan, args.session, args.submode, meta.get("parent", "day")) is None:
            return 2
        print("  if the running claude does not pick it up, /clear or restart it")
    elif args.cmd == "modes":
        if args.sessions:
            for s in modes.list_sessions():
                print("{:40} {:20} {:6} {:4} items  {}".format(s["id"], s["mode"], s.get("parent", "day"),
                                                              len(s["members"]), s["updated_at"]))
            return 0
        cfg = modes.load_config()
        if args.show:
            _, _, res = _resolve(scan, args.mode, args.show)
            _print_resolve(args.show, res)
            for m in sorted(res["members"]):
                print("  " + m + ("  (closure)" if m in res["added_by_closure"] else ""))
            return 0
        nodes, rep, _ = _resolve(scan, args.mode, "")
        base = modes.resolve("", cfg, nodes, rep["categories"], rep["edges"])
        print("parent mode {} — base: {} items".format(args.mode, len(base["members"])))
        for name, spec in (cfg.get("submodes") or {}).items():
            res = modes.resolve(name, cfg, nodes, rep["categories"], rep["edges"])
            print("  {:16} {:3} items  {}".format(name, len(res["members"]), (spec or {}).get("description", "")))
    elif args.cmd == "sync":
        sessions = modes.list_sessions()
        if not sessions:
            print("no sessions")
        for s in sessions:
            print("{} ({}, {})".format(s["id"], s["mode"], s.get("parent", "day")))
            apply_mode(scan, s["id"], s["mode"], s.get("parent", "day"))
    elif args.cmd == "prune":
        nodes, rep, _ = _resolve(scan, args.mode, "")
        plan = modes.prune_plan(nodes, modes.load_config(), rep["categories"], rep["edges"], args.days)
        print("stale session folders: {}".format(len(plan["stale_sessions"])))
        for s in plan["stale_sessions"]:
            print("  - " + s["id"])
        if plan["unused"]:
            print("installed in '{}' but in no sub-mode ({}): {}".format(
                args.mode, len(plan["unused"]), ", ".join(n["name"] for n in plan["unused"])))
            print("  -> add them to submodes.json, or remove with `install.py uninstall <package>`")
        if not args.apply:
            print("preview only; --apply moves the stale session folders to the archive")
            return 0
        for m in modes.prune_apply(plan):
            print("  moved " + m)
    else:
        ap.print_help()
    return 0
