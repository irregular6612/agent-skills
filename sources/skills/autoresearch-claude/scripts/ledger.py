#!/usr/bin/env python3
"""Trial ledger for experiment-loop runs. Stdlib only.

    ledger.py init   <rundir> [--direction lower|higher]
    ledger.py log    <rundir> --status keep --knob "lr 0.02->0.04" [--metric 0.993] [--ref a1b2c3d] [--note "..."]
    ledger.py report <rundir> [--noise 0.0004]

The ledger is append-only TSV. Tabs, not commas: knob and note fields
routinely contain commas and would silently corrupt a CSV.
"""
import argparse
import json
import pathlib
import sys

HEADER = ["trial", "ref", "metric", "status", "knob", "note"]
STATUSES = ("baseline", "keep", "discard", "crash", "blocked")


def paths(rundir):
    d = pathlib.Path(rundir)
    return d, d / "ledger.tsv", d / "meta.json"


def read_rows(tsv):
    if not tsv.exists():
        return []
    lines = tsv.read_text().splitlines()
    return [dict(zip(HEADER, ln.split("\t"))) for ln in lines[1:] if ln.strip()]


def as_float(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def beats(candidate, incumbent, direction, noise):
    """Is `candidate` a real improvement over `incumbent`?

    The conservative rule: the gain must exceed the full observed noise
    spread. Half-spread accepts roughly twice as many trials and roughly
    twice as many coin flips with it; on a long run those accumulate into
    a baseline you cannot reproduce. Loosen it only when trials are cheap
    enough to confirm a keep by re-running it.
    """
    if candidate is None or incumbent is None:
        return False
    gain = incumbent - candidate if direction == "lower" else candidate - incumbent
    return gain > noise


def cmd_init(a):
    d, tsv, meta = paths(a.rundir)
    (d / "logs").mkdir(parents=True, exist_ok=True)
    if not tsv.exists():
        tsv.write_text("\t".join(HEADER) + "\n")
    if not meta.exists():
        meta.write_text(json.dumps({"direction": a.direction, "noise": 0.0}, indent=2) + "\n")
    for name in ("PLAN.md", "journal.md"):
        (d / name).touch()
    print(f"initialized {d} (direction: {a.direction} is better)")


def cmd_log(a):
    d, tsv, _ = paths(a.rundir)
    if not tsv.exists():
        sys.exit(f"no ledger at {tsv} — run `ledger.py init {a.rundir}` first")
    trial = len(read_rows(tsv)) + 1
    row = [str(trial), a.ref, a.metric if a.metric is not None else "-",
           a.status, a.knob, a.note]
    with tsv.open("a") as f:
        f.write("\t".join(x.replace("\t", " ") for x in row) + "\n")
    print("\t".join(row))


def cmd_report(a):
    d, tsv, meta = paths(a.rundir)
    rows = read_rows(tsv)
    if not rows:
        sys.exit("ledger is empty")
    cfg = json.loads(meta.read_text()) if meta.exists() else {}
    direction = cfg.get("direction", "lower")
    noise = a.noise if a.noise is not None else cfg.get("noise", 0.0)

    widths = [max(len(r[k]) for r in rows + [dict(zip(HEADER, HEADER))]) for k in HEADER]
    fmt = "  ".join("{:<%d}" % w for w in widths)
    print(fmt.format(*HEADER))
    for r in rows:
        print(fmt.format(*(r[k] for k in HEADER)))

    scored = [(as_float(r["metric"]), r) for r in rows if as_float(r["metric"]) is not None]
    counts = {s: sum(1 for r in rows if r["status"] == s) for s in STATUSES}
    print("\n" + "  ".join(f"{s}={counts[s]}" for s in STATUSES) + f"  total={len(rows)}")

    if not scored:
        return
    best_v, best_r = min(scored) if direction == "lower" else max(scored)
    base = next((v for v, r in scored if r["status"] == "baseline"), None)
    print(f"best:     trial {best_r['trial']}  {best_v}  ({best_r['knob']})")
    if base is not None:
        delta = base - best_v if direction == "lower" else best_v - base
        verdict = "real" if beats(best_v, base, direction, noise) else "WITHIN NOISE"
        print(f"baseline: {base}   delta: {delta:+.6g}   noise floor: {noise:g}   -> {verdict}")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    i = sub.add_parser("init"); i.add_argument("rundir")
    i.add_argument("--direction", choices=["lower", "higher"], default="lower")
    i.set_defaults(func=cmd_init)

    l = sub.add_parser("log"); l.add_argument("rundir")
    l.add_argument("--status", required=True, choices=STATUSES)
    l.add_argument("--knob", default="-")
    l.add_argument("--metric")
    l.add_argument("--ref", default="-")
    l.add_argument("--note", default="")
    l.set_defaults(func=cmd_log)

    r = sub.add_parser("report"); r.add_argument("rundir")
    r.add_argument("--noise", type=float)
    r.set_defaults(func=cmd_report)

    a = p.parse_args()
    a.func(a)


if __name__ == "__main__":
    main()
