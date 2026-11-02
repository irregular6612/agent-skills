#!/usr/bin/env python3
"""agent-skills: pick and install irregular6612's Claude Code / Codex setup, or remove it.

    python3 install.py                      # interactive picker
    python3 install.py list                 # show catalog + what is installed
    python3 install.py install ditto-writer humanize k-dense:literature-review
    python3 install.py install --preset day      # or: --preset night, --mode night
    python3 install.py uninstall humanize   # or: uninstall --all

My own skills are linked (or copied) from sources/ in this repository, so one
file feeds both Claude Code and Codex. Third-party skills are fetched from the
author's repository at the commit pinned in catalog.json. Third-party plugins
are installed with the official `claude plugin` / `codex plugin` CLIs.

Everything installed is recorded in ~/.agent-skills/state.json. Uninstall only
removes what this tool put there, and restores whatever it had backed up.
Python 3.9+ standard library only; macOS, Linux and Windows.
"""
import argparse
import hashlib
import io
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parent
CATALOG = REPO / "catalog.json"
IS_WINDOWS = platform.system() == "Windows"
STATE_VERSION = 2
MODES = ("day", "night")
MODE_DIRS = {"claude": ("skills", "agents", "commands"), "codex": ("skills", "agents", "prompts")}
BLOCK_BEGIN = "# >>> agent-skills managed agents (edit with install.py) >>>"
BLOCK_END = "# <<< agent-skills managed agents <<<"
SKIP_NAMES = {".DS_Store", "__pycache__", ".git"}

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except (ValueError, OSError):
        pass


class Abort(Exception):
    pass


def say(msg=""):
    print(msg, flush=True)


def warn(msg):
    print("  ! " + msg, file=sys.stderr, flush=True)


# ---------------------------------------------------------------- environment

class Env:
    def __init__(self, args):
        home = Path.home()
        self.state_dir = Path(os.environ.get("AGENT_SKILLS_STATE") or home / ".agent-skills")
        # Base homes are fixed: CLAUDE_CONFIG_DIR / CODEX_HOME point at a mode or account
        # home inside such sessions, which must not become the install target.
        self.homes = {
            "claude": Path(os.environ.get("AGENT_SKILLS_CLAUDE_HOME") or home / ".claude"),
            "codex": Path(os.environ.get("AGENT_SKILLS_CODEX_HOME") or home / ".codex"),
        }
        self.legacy_state = home / ".agent-skills-setup" / "state.json"
        self.dry = getattr(args, "dry_run", False)
        self.force = getattr(args, "force", False)
        self.method = getattr(args, "method", None) or ("copy" if IS_WINDOWS else "link")
        self.target_mode = getattr(args, "mode", None)
        wanted = getattr(args, "harness", None)
        if wanted:
            self.harnesses = [h.strip() for h in wanted.split(",") if h.strip()]
            bad = set(self.harnesses) - set(self.homes)
            if bad:
                raise Abort("unknown harness: " + ", ".join(sorted(bad)))
        else:
            self.harnesses = [h for h in self.homes if self.detect(h)]
            if not self.harnesses:
                raise Abort("neither ~/.claude nor ~/.codex found and no claude/codex CLI on PATH; "
                            "pass --harness claude,codex to install anyway")

    def detect(self, harness):
        return self.homes[harness].is_dir() or shutil.which(harness) is not None


# ---------------------------------------------------------------- state

class State:
    def __init__(self, env):
        self.env = env
        self.path = env.state_dir / "state.json"
        if self.path.exists():
            self.data = json.loads(self.path.read_text(encoding="utf-8"))
            if self.data.get("version") not in (1, STATE_VERSION):
                raise Abort("unsupported state version in " + str(self.path))
        else:
            self.data = {"version": STATE_VERSION, "repo": str(REPO), "items": {}, "plugins": {},
                         "mcp": {}, "codex_agents": {}, "claude_hooks": {}}
        for key in ("items", "plugins", "mcp", "codex_agents", "claude_hooks"):
            self.data.setdefault(key, {})
        self.data["repo"] = str(REPO)
        self.migrate_v1()

    def save(self):
        if self.env.dry:
            return
        self.env.state_dir.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.data, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        os.replace(tmp, self.path)

    def packages(self, mode=None):
        """Installed package ids; with `mode`, only those present in that mode (home-level items count everywhere)."""
        pk = set()
        for section in ("items", "plugins", "mcp"):
            for rec in self.data[section].values():
                if mode is None or rec.get("mode") in (None, mode):
                    pk.add(rec["package"])
        return pk

    def migrate_v1(self):
        """v1 kept skills/agents/commands directly in the harness homes; v2 files them under mode 'day'."""
        for rec in self.data["items"].values():  # v1 stored link/copy under "mode"
            if "method" not in rec:
                old = rec.get("mode")
                rec["method"] = old if old in ("link", "copy") else ("link" if "target" in rec else "copy")
                if old in ("link", "copy"):
                    rec["mode"] = None
        if self.data.get("version", STATE_VERSION) == STATE_VERSION:
            self.data["version"] = STATE_VERSION
            return
        items = {}
        for key, rec in self.data["items"].items():
            if mode_scoped(rec["dest"]):
                rec["mode"] = "day"
                key = "day:" + key
            items[key] = rec
        self.data["items"] = items
        self.data["codex_agents"] = {"day:" + name: {"package": info["package"], "mode": "day", "name": name}
                                     for name, info in self.data["codex_agents"].items()}
        self.data["version"] = STATE_VERSION

    def next_backup(self):
        root = self.env.state_dir / "backups"
        n = 0
        while (root / str(n)).exists():
            n += 1
        return root / str(n)


def load_legacy_backups(env):
    """Map '.claude/skills/x' -> backup path from the previous ./setup journal."""
    try:
        data = json.loads(env.legacy_state.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    if data.get("repo") != str(REPO):
        return {}
    out = {}
    for rec in data.get("records", []):
        if rec.get("kind") == "link" and rec.get("backup"):
            out[rec["path"]] = str(env.legacy_state.parent / rec["backup"])
    return out


# ---------------------------------------------------------------- catalog

def load_catalog():
    cat = json.loads(CATALOG.read_text(encoding="utf-8"))
    if cat.get("schema") != 1:
        raise Abort("unsupported catalog schema")
    ids = [p["id"] for p in cat["packages"]]
    if len(ids) != len(set(ids)):
        raise Abort("duplicate package id in catalog")
    cat["by_id"] = {p["id"]: p for p in cat["packages"]}
    return cat


def short(text, n):
    text = " ".join(str(text).split())
    return text if len(text) <= n else text[: n - 1] + "…"


# ---------------------------------------------------------------- fetching third-party repos

def run(cmd, cwd=None, check=True, capture=True):
    exe = shutil.which(cmd[0])
    if not exe:
        raise Abort(cmd[0] + " not found on PATH")
    proc = subprocess.run([exe] + cmd[1:], cwd=cwd, text=True, encoding="utf-8", errors="replace",
                          stdout=subprocess.PIPE if capture else None,
                          stderr=subprocess.PIPE if capture else None)
    if check and proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "").strip()
        raise Abort(" ".join(cmd) + " failed: " + short(detail, 400))
    return proc


def vendor_dir(env, source):
    owner, name = source["repo"].split("/")
    return env.state_dir / "vendor" / (owner + "__" + name) / source["ref"][:12]


def minimal_paths(paths):
    """Drop paths already covered by a parent in the same set (skills/ covers skills/x)."""
    norm = sorted({p.strip("/") for p in paths})
    return [p for p in norm if not any(p != q and p.startswith(q + "/") for q in norm)]


def fetch(env, source, patterns):
    """Fetch only `patterns` (repo-relative paths) of source.repo at source.ref."""
    if not re.fullmatch(r"[0-9a-f]{40}", source["ref"]):
        raise Abort(source["repo"] + ": catalog ref must be a full commit SHA")
    dest = vendor_dir(env, source)
    marker = dest / ".agent-skills-fetch.json"
    have = set()
    if marker.exists():
        have = set(json.loads(marker.read_text(encoding="utf-8")).get("patterns", []))
        if all(any(p.strip("/") == h or p.strip("/").startswith(h + "/") for h in have) for p in patterns):
            return dest
    want = minimal_paths(have | set(patterns))
    say("  fetch  {}@{}  ({})".format(source["repo"], source["ref"][:12], ", ".join(want)))
    if env.dry:
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = Path(tempfile.mkdtemp(prefix=".fetch-", dir=str(dest.parent)))
    try:
        if shutil.which("git"):
            fetch_git(source, want, tmp)
        else:
            fetch_tarball(source, want, tmp)
        (tmp / ".agent-skills-fetch.json").write_text(json.dumps(
            {"repo": source["repo"], "ref": source["ref"], "patterns": want,
             "fetched": time.strftime("%Y-%m-%dT%H:%M:%S")}, indent=2), encoding="utf-8")
        if dest.exists():
            shutil.rmtree(dest)
        os.replace(tmp, dest)
    finally:
        if tmp.exists():
            shutil.rmtree(tmp, ignore_errors=True)
    return dest


def fetch_git(source, patterns, out):
    url = "https://github.com/" + source["repo"] + ".git"
    work = out / ".git-work"
    run(["git", "clone", "--quiet", "--filter=blob:none", "--no-checkout", url, str(work)])
    sparse = ["/" + p.strip("/") for p in patterns]  # matches a file or a whole directory
    run(["git", "-C", str(work), "sparse-checkout", "set", "--no-cone"] + sparse)
    run(["git", "-C", str(work), "checkout", "--quiet", source["ref"]])
    head = run(["git", "-C", str(work), "rev-parse", "HEAD"]).stdout.strip()
    if head != source["ref"]:
        raise Abort(source["repo"] + ": checked out " + head + ", expected " + source["ref"])
    for p in patterns:
        src = work / p
        if not src.exists():
            raise Abort("{}@{} has no path {}".format(source["repo"], source["ref"][:12], p))
        target = out / p
        target.parent.mkdir(parents=True, exist_ok=True)
        if src.is_dir():
            shutil.copytree(src, target, symlinks=True, ignore=shutil.ignore_patterns(*SKIP_NAMES))
        else:
            shutil.copy2(src, target)
    shutil.rmtree(work, ignore_errors=True)


def fetch_tarball(source, patterns, out):
    url = "https://codeload.github.com/{}/tar.gz/{}".format(source["repo"], source["ref"])
    with urllib.request.urlopen(url, timeout=120) as resp:
        data = resp.read()
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as tar:
        for member in tar.getmembers():
            parts = member.name.split("/", 1)
            if len(parts) < 2 or not parts[1]:
                continue
            rel = parts[1]
            if not any(rel == p.strip("/") or rel.startswith(p.strip("/") + "/") for p in patterns):
                continue
            if ".." in Path(rel).parts or member.issym() or member.islnk():
                continue
            target = out / rel
            if member.isdir():
                target.mkdir(parents=True, exist_ok=True)
            elif member.isfile():
                target.parent.mkdir(parents=True, exist_ok=True)
                with tar.extractfile(member) as fh:
                    target.write_bytes(fh.read())
    for p in patterns:
        if not (out / p).exists():
            raise Abort("{}@{} has no path {}".format(source["repo"], source["ref"][:12], p))


# ---------------------------------------------------------------- expanding packages into units

class Unit:
    """One thing to put on disk (kind='path') or one native plugin (kind='plugin')."""

    def __init__(self, package, kind, harness, **kw):
        self.package = package
        self.kind = kind
        self.harness = harness
        self.files = None
        self.origin = "own"
        self.mode = None
        self.__dict__.update(kw)

    @property
    def key(self):
        if self.kind == "path":
            return item_key(self.harness, self.dest, self.mode)
        return self.harness + ":" + self.name


def external_skills(pkg):
    """Declared skills of an external package: list of (name, path, files, harnesses)."""
    out = []
    for s in pkg.get("skills", []):
        out.append((s["name"], s["path"], s.get("files"), s["harness"]))
    return out


def wanted(env, pkg, sub):
    """Which declared skills / glob of an external package are needed, and their repo paths."""
    declared = external_skills(pkg)
    if sub:
        declared = [d for d in declared if d[0] == sub]
    declared = [d for d in declared if set(d[3]) & set(env.harnesses)]
    glob = pkg.get("skills_glob")
    if glob and not set(glob["harness"]) & set(env.harnesses):
        glob = None
    if glob and sub and any(d[0] == sub for d in external_skills(pkg)):
        glob = None
    patterns = []
    for name, path, only, harnesses in declared:
        patterns += [str(Path(path) / f) for f in only] if only else [path]
    if glob:
        patterns.append(glob["path"] if not sub else str(Path(glob["path"]) / sub))
    files = [] if sub else [fg for fg in pkg.get("files_glob", []) if set(fg["harness"]) & set(env.harnesses)]
    patterns += [fg["path"] for fg in files]
    if not sub:
        patterns += [fm["path"] for fm in pkg.get("file_map", []) if set(fm["harness"]) & set(env.harnesses)]
    return declared, glob, patterns, files


def expand(env, cat, selection):
    """selection: list of (package_id, sub or None). Returns units, fetching what is needed."""
    # One fetch per upstream repository, covering every path this selection needs.
    needs = {}
    for pid, sub in selection:
        pkg = cat["by_id"][pid]
        if "source" in pkg:
            key = (pkg["source"]["repo"], pkg["source"]["ref"])
            needs.setdefault(key, (pkg["source"], set()))[1].update(wanted(env, pkg, sub)[2])
    roots = {key: fetch(env, src, sorted(pats)) for key, (src, pats) in needs.items() if pats}

    units = []
    for pid, sub in selection:
        pkg = cat["by_id"][pid]
        for it in pkg.get("items", []):
            if it["harness"] in env.harnesses:
                units.append(Unit(pid, "path", it["harness"], dest=it["dest"], src=REPO / it["src"]))
        if pkg.get("claude_hooks") and "claude" in env.harnesses:
            units.append(Unit(pid, "hooks", "claude", name="hooks", hooks=pkg["claude_hooks"]))
        if "source" in pkg:
            declared, glob, patterns, files = wanted(env, pkg, sub)
            root = roots.get((pkg["source"]["repo"], pkg["source"]["ref"]))
            origin = pkg["source"]["repo"] + "@" + pkg["source"]["ref"][:12]
            if patterns and root is not None:
                for name, path, only, harnesses in declared:
                    for h in harnesses:
                        if h in env.harnesses:
                            units.append(Unit(pid, "path", h, dest="skills/" + name,
                                              src=root / path, files=only, origin=origin))
                if glob:
                    base = root / glob["path"]
                    if sub:
                        names = [sub]
                    elif base.is_dir():
                        names = sorted(d.name for d in base.iterdir() if (d / "SKILL.md").is_file())
                    else:
                        names = ["<every skill under " + glob["path"] + ">"]  # dry run: not fetched
                    for n in names:
                        for h in glob["harness"]:
                            if h in env.harnesses:
                                units.append(Unit(pid, "path", h, dest="skills/" + n, src=base / n,
                                                  origin=origin))
                for fm in ([] if sub else pkg.get("file_map", [])):
                    for h in fm["harness"]:
                        if h in env.harnesses:
                            units.append(Unit(pid, "path", h, dest=fm["dest"], src=root / fm["path"], origin=origin))
                for fg in files:
                    base = root / fg["path"]
                    names = sorted(f.name for f in base.iterdir() if f.is_file() and f.suffix == ".md") \
                        if base.is_dir() else []
                    for n in names:
                        for h in fg["harness"]:
                            if h in env.harnesses:
                                units.append(Unit(pid, "path", h, dest=fg["dest"] + "/" + n, src=base / n,
                                                  origin=origin))
        for h, spec in pkg.get("plugins", {}).items():
            if h in env.harnesses and not sub:
                units.append(Unit(pid, "plugin", h, name=spec["name"], marketplace=spec["marketplace"]))
        for spec in ([] if sub else pkg.get("mcp", [])):
            for h in spec["harness"]:
                if h in env.harnesses:
                    units.append(Unit(pid, "mcp", h, name=spec["name"], command=spec["command"],
                                      args=spec.get("args", []), requires=spec.get("requires")))
    for u in units:
        if u.kind == "path" and mode_scoped(u.dest):
            u.mode = env.target_mode
    return units


# ---------------------------------------------------------------- filesystem helpers

def lexists(p):
    return os.path.lexists(str(p))


def tree_digest(path):
    h = hashlib.sha256()
    if path.is_file():
        h.update(path.read_bytes())
        return h.hexdigest()
    for root, dirs, files in os.walk(str(path)):
        dirs[:] = sorted(d for d in dirs if d not in SKIP_NAMES)
        for f in sorted(files):
            if f in SKIP_NAMES:
                continue
            fp = Path(root) / f
            h.update(fp.relative_to(path).as_posix().encode() + b"\0")
            h.update(fp.read_bytes() if not fp.is_symlink() else os.readlink(str(fp)).encode())
    return h.hexdigest()


def remove_path(p):
    if p.is_symlink() or p.is_file():
        p.unlink()
    elif p.is_dir():
        if IS_WINDOWS and hasattr(os, "readlink"):
            try:  # directory junction / symlink on Windows
                os.readlink(str(p))
                os.rmdir(str(p))
                return
            except OSError:
                pass
        shutil.rmtree(p)


def prune_empty(directory, stop):
    """Remove now-empty directories up to (not including) the harness home."""
    while directory != stop and stop in directory.parents:
        try:
            directory.rmdir()
        except OSError:
            return
        directory = directory.parent


def place(src, dest, mode, files=None):
    """Create dest from src. Returns the mode actually used."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    if files:  # only selected files of src (e.g. a SKILL.md at a repo root)
        dest.mkdir()
        for f in files:
            shutil.copy2(src / f, dest / f)
        return "copy"
    if mode == "link":
        try:
            os.symlink(str(src), str(dest), target_is_directory=src.is_dir())
            return "link"
        except OSError:
            if not IS_WINDOWS:
                raise
            warn("symlinks unavailable (enable Windows Developer Mode); copying instead")
    if src.is_dir():
        shutil.copytree(src, dest, ignore=shutil.ignore_patterns(*SKIP_NAMES))
    else:
        shutil.copy2(src, dest)
    return "copy"


def matches(rec, path):
    if rec.get("method", rec.get("mode")) == "link":
        return path.is_symlink() and os.readlink(str(path)) == rec["target"]
    return lexists(path) and not path.is_symlink() and tree_digest(path) == rec["digest"]


def points_into_repo(path):
    if not path.is_symlink():
        return False
    target = os.readlink(str(path))
    try:
        Path(target).relative_to(REPO)
        return True
    except ValueError:
        return False



# ---------------------------------------------------------------- modes (day / night)
#
#   sources (repo) + vendor (upstream)          the originals
#     -> ~/.agent-skills/modes/<mode>/<harness>/{skills,agents,...}   one link per item
#       -> day:   ~/.claude/skills etc. are links to modes/day/...
#          night: ~/.agent-skills/homes/night/<harness>[-<account>] mirrors the real home with
#                 links, except skills/agents/... (modes/night) and Codex's config.toml.
# History, settings, login, plugins and MCP stay in the one real home.

def mode_scoped(dest):
    return dest.split("/", 1)[0] in ("skills", "agents", "commands", "prompts")


def item_key(harness, dest, mode):
    return (mode + ":" if mode_scoped(dest) and mode else "") + harness + ":" + dest


def mode_dir(env, mode, harness):
    return env.state_dir / "modes" / mode / harness


def item_path(env, harness, dest, mode):
    if mode_scoped(dest):
        return mode_dir(env, mode or "day", harness) / dest
    return env.homes[harness] / dest


def ensure_wiring(env, state):
    """Point the real homes' skill/agent/command folders at modes/day (once; idempotent)."""
    state.migrate_v1()
    if env.dry:
        return
    for harness, home in env.homes.items():
        if not home.is_dir():
            continue
        for cat in MODE_DIRS[harness]:
            target = mode_dir(env, "day", harness) / cat
            target.mkdir(parents=True, exist_ok=True)
            link = home / cat
            if link.is_symlink():
                if os.readlink(str(link)) != str(target):
                    warn("{} links somewhere else ({}); leaving it".format(link, os.readlink(str(link))))
                continue
            if link.is_dir():
                for child in sorted(link.iterdir()):
                    dest = target / child.name
                    if lexists(dest):
                        same = child.is_symlink() and dest.is_symlink() and os.readlink(str(child)) == os.readlink(str(dest))
                        if not same:
                            spare = state.next_backup()
                            spare.mkdir(parents=True)
                            shutil.move(str(child), str(spare / child.name))
                            warn("{} clashed with {}; moved to {}".format(child, dest, spare))
                        else:
                            child.unlink()
                        continue
                    shutil.move(str(child), str(dest))
                link.rmdir()
            elif lexists(link):
                warn("{} is not a folder; leaving it".format(link))
                continue
            link.symlink_to(target, target_is_directory=True)
            say("  wire   {} -> {}".format(link, target))
    state.save()


def unwire(env):
    """Undo ensure_wiring: real folders again, with whatever is left in modes/day moved back."""
    if env.dry:
        return
    for harness, home in env.homes.items():
        for cat in MODE_DIRS[harness]:
            link, target = home / cat, mode_dir(env, "day", harness) / cat
            if not (link.is_symlink() and os.readlink(str(link)) == str(target)):
                continue
            link.unlink()
            children = sorted(target.iterdir()) if target.is_dir() else []
            if children:
                link.mkdir()
                for child in children:
                    shutil.move(str(child), str(link / child.name))
            say("  unwire {}".format(link))


def strip_tables(text, table):
    """Remove every [table.*] TOML table (header through the line before the next header)."""
    out, skipping = [], False
    head = re.compile(r"^\s*\[\s*{}\s*\.".format(re.escape(table)))
    for line in text.splitlines(keepends=True):
        if HEADER_LINE.match(line):
            skipping = bool(head.match(line))
        if not skipping:
            out.append(line)
    return re.sub(r"\n{3,}", "\n\n", "".join(out))


HEADER_LINE = re.compile(r"^\s*\[")


def agent_block(state, mode, agents_dir):
    entries = []
    for info in sorted(state.data["codex_agents"].values(), key=lambda i: i["name"]):
        if info["mode"] != mode:
            continue
        name = info["name"]
        label = name if re.fullmatch(r"[A-Za-z0-9_-]+", name) else json.dumps(name)
        entries.append("[agents.{}]\nconfig_file = {}\n".format(label, json.dumps(str(agents_dir / (name + ".toml")))))
    return (BLOCK_BEGIN + "\n" + "\n".join(entries) + BLOCK_END + "\n") if entries else ""


def link_entry(link, target, notes):
    if link.is_symlink():
        if os.readlink(str(link)) != str(target):
            link.unlink()
            link.symlink_to(target)
    elif lexists(link):
        notes.append("{} is a real file, not a link to {} (it is not shared)".format(link, target))
    else:
        link.symlink_to(target)


def ensure_home(env, state, mode, harness, account=None):
    """Return the home a session of (mode, harness, account) should use, creating/refreshing it."""
    base = env.homes[harness]
    alt_account = harness == "codex" and account not in (None, "", "main")
    if mode == "day" and not alt_account:
        return base
    notes = []
    if mode == "day":  # a second Codex login sharing everything else
        home = Path.home() / (".codex-" + account)
        home.mkdir(exist_ok=True)
        for entry in base.iterdir():
            if not entry.name.startswith("auth."):
                link_entry(home / entry.name, entry, notes)
    else:
        home = env.state_dir / "homes" / mode / (harness + ("-" + account if alt_account else ""))
        home.mkdir(parents=True, exist_ok=True)
        auth_home = (Path.home() / (".codex-" + account)) if alt_account else base
        for cat in MODE_DIRS[harness]:
            (mode_dir(env, mode, harness) / cat).mkdir(parents=True, exist_ok=True)
        for entry in base.iterdir():
            name = entry.name
            if name in MODE_DIRS[harness]:
                link_entry(home / name, mode_dir(env, mode, harness) / name, notes)
            elif harness == "codex" and name == "config.toml":
                continue
            elif harness == "codex" and name.startswith("auth."):
                if (auth_home / name).exists():
                    link_entry(home / name, auth_home / name, notes)
            else:
                link_entry(home / name, entry, notes)
        for cat in MODE_DIRS[harness]:  # also when the real home has no such folder yet
            link_entry(home / cat, mode_dir(env, mode, harness) / cat, notes)
        if harness == "claude":  # with CLAUDE_CONFIG_DIR set, Claude reads <dir>/.claude.json
            link_entry(home / ".claude.json", Path.home() / ".claude.json", notes)
        else:
            text = (base / "config.toml").read_text(encoding="utf-8") if (base / "config.toml").exists() else ""
            text = re.sub(r"\n*" + re.escape(BLOCK_BEGIN) + r".*?" + re.escape(BLOCK_END) + r"\n?", "\n", text, flags=re.S)
            text = strip_tables(text, "agents")
            block = agent_block(state, mode, home / "agents")
            config = (text.rstrip("\n") + "\n\n" if text.strip() else "") + block
            cfg = home / "config.toml"
            if not cfg.exists() or cfg.read_text(encoding="utf-8") != config:
                tmp = home / ".config.toml.agent-skills-tmp"
                tmp.write_text(config, encoding="utf-8")
                os.chmod(tmp, 0o600)
                os.replace(tmp, cfg)
    for n in notes:
        warn(n)
    return home


# ---------------------------------------------------------------- install / uninstall of path units

def install_path(env, state, unit, legacy):
    dest = item_path(env, unit.harness, unit.dest, unit.mode)
    key = unit.key
    rec = state.data["items"].get(key)
    if rec and rec["package"] != unit.package:
        warn("{} already installed by package '{}'; skipping".format(key, rec["package"]))
        return False
    if not env.dry and not unit.src.exists():
        raise Abort("missing source " + str(unit.src))
    if rec:
        if not matches(rec, dest):
            if not env.force:
                warn("{} was changed after install; leaving it (use --force to replace)".format(dest))
                return False
        elif rec["method"] == "link" and rec["target"] == str(unit.src) and env.method == "link":
            return False  # already up to date
        elif rec["method"] == "copy" and not unit.files and tree_digest(unit.src) == rec["digest"] and env.method == "copy":
            return False
    say("  {:7}{} -> {}".format("update" if rec else env.method if not unit.files else "copy", dest, unit.src))
    if env.dry:
        return True
    backup = rec.get("backup") if rec else None
    if lexists(dest):
        if rec:
            remove_path(dest)
        elif points_into_repo(dest):
            # Left by the previous ./setup of this repo: adopt it, keep its original backup.
            backup = legacy.get("." + unit.harness + "/" + unit.dest)
            remove_path(dest)
        else:
            target = state.next_backup()
            target.mkdir(parents=True)
            backup = str(target / dest.name)
            shutil.move(str(dest), backup)
            say("         backed up existing {} -> {}".format(dest, backup))
    used = place(unit.src, dest, env.method, unit.files)
    new = {"package": unit.package, "harness": unit.harness, "dest": unit.dest, "method": used,
           "mode": unit.mode if mode_scoped(unit.dest) else None, "origin": unit.origin, "backup": backup}
    if used == "link":
        new["target"] = str(unit.src)
    else:
        new["digest"] = tree_digest(dest)
    state.data["items"][key] = new
    state.save()
    if unit.harness == "codex" and unit.dest.startswith("agents/") and unit.dest.endswith(".toml"):
        name = Path(unit.dest).stem
        state.data["codex_agents"][unit.mode + ":" + name] = {"package": unit.package, "mode": unit.mode, "name": name}
        state.save()
    return True


def uninstall_path(env, state, key):
    rec = state.data["items"][key]
    dest = item_path(env, rec["harness"], rec["dest"], rec.get("mode"))
    if lexists(dest) and not matches(rec, dest) and not env.force:
        warn("{} was changed after install; not removing (use --force)".format(dest))
        return False
    say("  remove {}".format(dest))
    if env.dry:
        return True
    if lexists(dest):
        remove_path(dest)
    backup = rec.get("backup")
    if backup and env.legacy_state.parent in Path(backup).parents:
        # A copy from before the previous ./setup took over; it is usually an
        # older version of this same package, so leave it where it is.
        say("         older copy kept at {} (not restored)".format(backup))
        backup = None
    if not (backup and lexists(Path(backup))):
        stop = (mode_dir(env, rec["mode"], rec["harness"]) / rec["dest"].split("/", 1)[0]) if rec.get("mode") \
            else env.homes[rec["harness"]]
        prune_empty(dest.parent, stop)
    if backup and lexists(Path(backup)):
        shutil.move(backup, str(dest))
        say("         restored {}".format(dest))
    del state.data["items"][key]
    if rec["harness"] == "codex" and rec["dest"].startswith("agents/"):
        state.data["codex_agents"].pop("{}:{}".format(rec.get("mode"), Path(rec["dest"]).stem), None)
    state.save()
    return True


# ---------------------------------------------------------------- codex agent registration (config.toml)

def sync_codex_config(env, state):
    if "codex" not in env.harnesses and not state.data["codex_agents"]:
        return
    cfg = env.homes["codex"] / "config.toml"
    text = cfg.read_text(encoding="utf-8") if cfg.exists() else ""
    pattern = re.compile(r"\n*" + re.escape(BLOCK_BEGIN) + r".*?" + re.escape(BLOCK_END) + r"\n?", re.S)
    outside = pattern.sub("\n", text) if pattern.search(text) else text
    entries = []
    for info in sorted(state.data["codex_agents"].values(), key=lambda i: i["name"]):
        if info["mode"] != "day":
            continue  # other modes get their own config.toml in their home
        name = info["name"]
        header = re.compile(r"^\s*\[\s*agents\s*\.\s*(\"?){}\1\s*\]".format(re.escape(name)), re.M)
        if header.search(outside):
            continue  # already declared by the user (or the previous setup); leave it alone
        entries.append("[agents.{}]\nconfig_file = {}\n".format(json.dumps(name) if not re.fullmatch(r"[A-Za-z0-9_-]+", name) else name,
                                                               json.dumps(str(env.homes["codex"] / "agents" / (name + ".toml")))))
    block = ""
    if entries:
        block = BLOCK_BEGIN + "\n" + "\n".join(entries) + BLOCK_END + "\n"
    if block:
        new = (outside.rstrip("\n") + "\n\n" if outside.strip() else "") + block
    else:
        new = outside
    if new == text:
        return
    say("  config {} ({} managed agent entries)".format(cfg, len(entries)))
    if env.dry:
        return
    if not new.strip():
        cfg.unlink()  # only our block was ever in it
        return
    cfg.parent.mkdir(parents=True, exist_ok=True)
    tmp = cfg.with_name(cfg.name + ".agent-skills-tmp")
    tmp.write_text(new, encoding="utf-8")
    os.replace(tmp, cfg)


# ---------------------------------------------------------------- claude hooks (settings.json)

def hook_script(entry):
    cmds = [h.get("command", "") for h in entry.get("hooks", [])]
    names = re.findall(r"([A-Za-z0-9_.-]+\.(?:sh|py))", " ".join(cmds))
    return tuple(sorted(names))


def settings_path(env):
    return env.homes["claude"] / "settings.json"


def install_hooks(env, state, unit):
    path = settings_path(env)
    created = not path.exists()
    settings = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    home = str(env.homes["claude"]).replace("\\", "/")
    added = []
    hooks = settings.setdefault("hooks", {})
    for event, entries in unit.hooks.items():
        current = hooks.setdefault(event, [])
        for entry in entries:
            entry = json.loads(json.dumps(entry).replace("${CLAUDE_HOME}", home))
            if any(hook_script(e) == hook_script(entry) for e in current):
                continue  # same script already registered
            current.append(entry)
            added.append([event, entry])
    if not added:
        return False
    say("  hooks  {} (+{})".format(path, len(added)))
    if env.dry:
        return True
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(settings, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    state.data["claude_hooks"][unit.package] = added
    state.data.setdefault("created_files", [])
    if created and str(path) not in state.data["created_files"]:
        state.data["created_files"].append(str(path))
    state.save()
    return True


def uninstall_hooks(env, state, package):
    added = state.data["claude_hooks"].get(package)
    if not added:
        return
    path = settings_path(env)
    if path.exists():
        settings = json.loads(path.read_text(encoding="utf-8"))
        hooks = settings.get("hooks", {})
        for event, entry in added:
            if entry in hooks.get(event, []):
                hooks[event].remove(entry)
            if event in hooks and not hooks[event]:
                del hooks[event]
        if "hooks" in settings and not settings["hooks"]:
            del settings["hooks"]
        say("  hooks  {} (-{})".format(path, len(added)))
        if not env.dry:
            created = state.data.get("created_files", [])
            if not settings and str(path) in created:
                path.unlink()
                created.remove(str(path))
            else:
                path.write_text(json.dumps(settings, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if not env.dry:
        del state.data["claude_hooks"][package]
        state.save()


# ---------------------------------------------------------------- native plugins

def cli_json(cmd):
    proc = run(cmd, check=False)
    if proc.returncode != 0:
        return None
    try:
        return json.loads(proc.stdout)
    except ValueError:
        return None


def installed_plugins(harness):
    if harness == "claude":
        data = cli_json(["claude", "plugin", "list", "--json"]) or []
        return {p["id"] for p in data if isinstance(p, dict) and "id" in p}
    data = cli_json(["codex", "plugin", "list", "--json"]) or {}
    return {p["pluginId"] for p in data.get("installed", []) if p.get("installed")}


def marketplaces(harness):
    data = cli_json([harness, "plugin", "marketplace", "list", "--json"])
    names = set()

    def walk(x):
        if isinstance(x, dict):
            if isinstance(x.get("name"), str):
                names.add(x["name"])
            for v in x.values():
                if isinstance(v, (list, dict)):
                    walk(v)
        elif isinstance(x, list):
            for v in x:
                walk(v)
    walk(data)
    return names


def install_plugin(env, state, unit, cache):
    h = unit.harness
    if not shutil.which(h):
        warn("{} CLI not found; skipping plugin {}".format(h, unit.name))
        return False
    if unit.key in state.data["plugins"]:
        return False
    if h not in cache:
        cache[h] = {"plugins": installed_plugins(h), "markets": marketplaces(h)}
    have = cache[h]
    if any(p.split("@")[0] == unit.name for p in have["plugins"]):
        say("  skip   {} plugin {} (already installed)".format(h, unit.name))
        return False
    market = unit.marketplace
    plugin_id = unit.name + "@" + market["name"]
    added_market = False
    if market["name"] not in have["markets"]:
        say("  market {} plugin marketplace add {}".format(h, market["source"]))
        if not env.dry:
            run([h, "plugin", "marketplace", "add", market["source"]], capture=False)
            have["markets"].add(market["name"])
        added_market = True
    say("  plugin {} {}".format(h, plugin_id))
    if env.dry:
        return True
    if h == "claude":
        run(["claude", "plugin", "install", plugin_id, "--scope", "user"], capture=False)
    else:
        run(["codex", "plugin", "add", plugin_id], capture=False)
    have["plugins"].add(plugin_id)
    state.data["plugins"][unit.key] = {"package": unit.package, "harness": h, "id": plugin_id,
                                       "marketplace": market["name"], "added_marketplace": added_market}
    state.save()
    return True


def uninstall_plugin(env, state, key):
    rec = state.data["plugins"][key]
    h = rec["harness"]
    if not shutil.which(h):
        warn("{} CLI not found; cannot remove plugin {}".format(h, rec["id"]))
        return False
    say("  plugin remove {} {}".format(h, rec["id"]))
    if env.dry:
        return True
    if h == "claude":
        run(["claude", "plugin", "uninstall", rec["id"], "--scope", "user"], check=False, capture=False)
    else:
        run(["codex", "plugin", "remove", rec["id"]], check=False, capture=False)
    del state.data["plugins"][key]
    still_used = any(r["harness"] == h and r["marketplace"] == rec["marketplace"]
                     for r in state.data["plugins"].values())
    if rec["added_marketplace"] and not still_used:
        say("  market remove {} {}".format(h, rec["marketplace"]))
        run([h, "plugin", "marketplace", "remove", rec["marketplace"]], check=False, capture=False)
    state.save()
    return True


# ---------------------------------------------------------------- MCP servers (claude mcp / codex mcp)

def mcp_registered(env, harness, name):
    if harness == "claude":
        try:
            data = json.loads((Path.home() / ".claude.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return False
        return name in (data.get("mcpServers") or {})
    cfg = env.homes["codex"] / "config.toml"
    return cfg.exists() and name in toml_tables(cfg.read_text(encoding="utf-8"), "mcp_servers")


def install_mcp(env, state, unit):
    key = unit.harness + ":" + unit.name
    if key in state.data["mcp"]:
        return False
    if not shutil.which(unit.harness):
        warn("{} CLI not found; skipping MCP server {}".format(unit.harness, unit.name))
        return False
    if not shutil.which(unit.command):
        warn("`{}` not found; MCP server {} skipped{}".format(
            unit.command, unit.name, " (install it with: {})".format(unit.requires) if unit.requires else ""))
        return False
    if mcp_registered(env, unit.harness, unit.name):
        say("  skip   {} MCP {} (already registered)".format(unit.harness, unit.name))
        return False
    say("  mcp    {} {} -> {} {}".format(unit.harness, unit.name, unit.command, " ".join(unit.args)))
    if env.dry:
        return True
    if unit.harness == "claude":
        run(["claude", "mcp", "add", "-s", "user", unit.name, "--", unit.command] + unit.args)
    else:
        run(["codex", "mcp", "add", unit.name, "--", unit.command] + unit.args)
    state.data["mcp"][key] = {"package": unit.package, "harness": unit.harness, "name": unit.name}
    state.save()
    return True


def uninstall_mcp(env, state, key):
    rec = state.data["mcp"][key]
    h = rec["harness"]
    say("  mcp remove {} {}".format(h, rec["name"]))
    if env.dry:
        return True
    if shutil.which(h):
        if h == "claude":
            run(["claude", "mcp", "remove", "-s", "user", rec["name"]], check=False)
        else:
            run(["codex", "mcp", "remove", rec["name"]], check=False)
    del state.data["mcp"][key]
    state.save()
    return True


# ---------------------------------------------------------------- selection

def parse_selection(cat, tokens):
    out = []
    for tok in tokens:
        pid, _, sub = tok.partition(":")
        if pid not in cat["by_id"]:
            raise Abort("unknown package: " + pid + " (see: install.py list)")
        pkg = cat["by_id"][pid]
        if sub:
            names = [s[0] for s in external_skills(pkg)]
            if not names and not pkg.get("skills_glob"):
                raise Abort(pid + " has no sub-skills to pick from")
            if names and not pkg.get("skills_glob") and sub not in names:
                raise Abort("{} has no skill {} (choices: {})".format(pid, sub, ", ".join(names)))
        out.append((pid, sub or None))
    return out


def harness_tags(pkg):
    hs = set()
    for it in pkg.get("items", []):
        hs.add(it["harness"])
    for s in pkg.get("skills", []):
        hs.update(s["harness"])
    if pkg.get("skills_glob"):
        hs.update(pkg["skills_glob"]["harness"])
    hs.update(pkg.get("plugins", {}).keys())
    for m in pkg.get("mcp", []):
        hs.update(m["harness"])
    return "+".join(h for h in ("claude", "codex") if h in hs)


def numbered(cat):
    rows = []
    for g in cat["groups"]:
        for p in cat["packages"]:
            if p["group"] == g["id"]:
                rows.append(p)
    return rows


def print_catalog(cat, state, only_installed=False, mode="day"):
    installed = state.packages(mode)
    n = 0
    for g in cat["groups"]:
        pkgs = [p for p in cat["packages"] if p["group"] == g["id"]]
        if only_installed:
            pkgs = [p for p in pkgs if p["id"] in installed]
        if not pkgs:
            n += len([p for p in cat["packages"] if p["group"] == g["id"]])
            continue
        say("\n" + g["title"])
        for p in cat["packages"]:
            if p["group"] != g["id"]:
                continue
            n += 1
            if only_installed and p["id"] not in installed:
                continue
            mark = "x" if p["id"] in installed else " "
            subs = [s[0] for s in external_skills(p)]
            extra = "  [{}: {}]".format(len(subs), short(", ".join(subs), 60)) if subs else ""
            say("  {:>2} [{}] {:<26} {:<12} {}{}".format(n, mark, p["id"], harness_tags(p),
                                                       short(p["description"], 70), extra))


def interactive_pick(cat, state, env):
    rows = numbered(cat)
    say("agent-skills — choose what to install into mode '{}' for: ".format(env.target_mode) +
        ", ".join("{} ({})".format(h, env.homes[h]) for h in env.harnesses))
    print_catalog(cat, state, mode=env.target_mode)
    say("\nPresets: " + ", ".join("{} ({} packages)".format(k, len(v)) for k, v in cat["presets"].items()))
    say("Type numbers or ids (e.g. `1 3 5-8 k-dense:literature-review`), a preset name, or `q` to quit.")
    tty = open_tty()
    line = tty.readline() if tty else ""
    tokens = line.replace(",", " ").split()
    if not tokens or tokens == ["q"]:
        raise Abort("nothing selected")
    picked = []
    for tok in tokens:
        if tok in cat["presets"]:
            picked += cat["presets"][tok]
        elif re.fullmatch(r"\d+-\d+", tok):
            a, b = map(int, tok.split("-"))
            picked += [rows[i - 1]["id"] for i in range(a, b + 1) if 1 <= i <= len(rows)]
        elif tok.isdigit() and 1 <= int(tok) <= len(rows):
            picked.append(rows[int(tok) - 1]["id"])
        else:
            picked.append(tok)
    return list(dict.fromkeys(picked))


def open_tty():
    if sys.stdin and sys.stdin.isatty():
        sys.stdout.write("> ")
        sys.stdout.flush()
        return sys.stdin
    try:  # `curl ... | bash` leaves stdin on the pipe; read the terminal instead
        tty = open("CON" if IS_WINDOWS else "/dev/tty", encoding="utf-8")
        sys.stdout.write("> ")
        sys.stdout.flush()
        return tty
    except OSError:
        return None


def confirm(env, question):
    if env.yes or env.dry:
        return True
    sys.stdout.write(question + " [Y/n] ")
    sys.stdout.flush()
    tty = sys.stdin if sys.stdin and sys.stdin.isatty() else None
    if tty is None:
        try:
            tty = open("CON" if IS_WINDOWS else "/dev/tty", encoding="utf-8")
        except OSError:
            return True
    return tty.readline().strip().lower() in ("", "y", "yes")


# ---------------------------------------------------------------- dependency graph (graph.html)

TEXT_LIMIT = 400_000


def frontmatter(text):
    """Tiny YAML-frontmatter reader: top-level scalar keys, folded/literal blocks joined."""
    if not text.startswith("---"):
        return {}
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}
    out, key, buf = {}, None, []
    for line in parts[1].splitlines():
        m = re.match(r"^([A-Za-z_][\w-]*):\s*(.*)$", line)
        if m:
            if key and buf:
                out[key] = " ".join(buf)
            key, val, buf = m.group(1), m.group(2).strip(), []
            if val in (">", ">-", "|", "|-", ""):
                continue
            out[key] = val.strip('"').strip("'")
            key = None
        elif key and line.startswith((" ", "\t")):
            buf.append(line.strip())
    if key and buf:
        out[key] = " ".join(buf)
    return out


def read_text(path, limit=TEXT_LIMIT):
    try:
        data = path.read_bytes()[:limit]
    except OSError:
        return ""
    return data.decode("utf-8", errors="replace")


def skill_text(directory):
    """SKILL.md plus markdown under references/ (bounded) — where skills name their helpers."""
    text = read_text(directory / "SKILL.md")
    budget = TEXT_LIMIT - len(text)
    for sub in ("references", "reference", "agents", "prompts"):
        d = directory / sub
        if d.is_dir():
            for f in sorted(d.rglob("*.md")):
                if budget <= 0:
                    break
                chunk = read_text(f, budget)
                text += "\n" + chunk
                budget -= len(chunk)
    return text


def toml_tables(text, table):
    """Names of [table.NAME] / [table."NAME"] headers (stdlib-only fallback for tomllib)."""
    names = re.findall(r'^\s*\[\s*{}\s*\.\s*(?:"([^"]+)"|([A-Za-z0-9_-]+))\s*\]'.format(re.escape(table)), text, re.M)
    return [a or b for a, b in names]


class Inventory:
    def __init__(self, env, state, homes=None, mode="day"):
        self.env = env
        self.state = state
        self.homes = homes or env.homes
        self.mode = mode
        self.nodes = {}

    def add(self, kind, name, harness, source, path, desc, text, plugin=None):
        nid = "{}:{}".format(kind, (plugin + ":" if plugin else "") + name)
        node = self.nodes.get(nid)
        if node is None:
            node = self.nodes[nid] = {"id": nid, "type": kind, "name": name, "plugin": plugin,
                                      "harness": [], "source": source, "path": str(path),
                                      "desc": short(desc or "", 400), "text": text}
        if harness not in node["harness"]:
            node["harness"].append(harness)
        if len(text) > len(node["text"]):
            node["text"] = text
        return node

    def origin_of(self, harness, dest):
        rec = self.state.data["items"].get(item_key(harness, dest, self.mode))
        if not rec:
            return "unmanaged"
        return "mine" if rec.get("origin") == "own" else "third-party: " + rec.get("origin", "")

    # -- skills / agents in the harness homes
    def scan_home(self, harness, home):
        roots = [home / "skills"]
        if harness == "codex":
            roots.append(Path.home() / ".agents" / "skills")
        for root in roots:
            if not root.is_dir():
                continue
            for d in sorted(root.iterdir()):
                if (d / "SKILL.md").is_file():
                    fm = frontmatter(read_text(d / "SKILL.md", 20000))
                    name = fm.get("name") or d.name
                    self.add("skill", name, harness, self.origin_of(harness, "skills/" + d.name),
                             d, fm.get("description"), skill_text(d))
        agents = home / "agents"
        if agents.is_dir():
            for f in sorted(agents.rglob("*.md" if harness == "claude" else "*.toml")):
                text = read_text(f)
                if harness == "claude":
                    fm = frontmatter(text)
                    name = fm.get("name") or f.stem
                    desc = fm.get("description")
                else:
                    m = re.search(r'^name\s*=\s*"([^"]+)"', text, re.M)
                    name = m.group(1) if m else f.stem
                    d = re.search(r'^description\s*=\s*"((?:[^"\\]|\\.)*)"', text, re.M)
                    desc = d.group(1) if d else ""
                self.add("agent", name, harness,
                         self.origin_of(harness, f.relative_to(home).as_posix()), f, desc, text)

    # -- enabled plugins
    def plugin_dir(self, plugin_root, label, harness):
        for d in sorted((plugin_root / "skills").glob("*/")):
            if (d / "SKILL.md").is_file():
                fm = frontmatter(read_text(d / "SKILL.md", 20000))
                self.add("skill", fm.get("name") or d.name, harness, "plugin: " + label, d,
                         fm.get("description"), skill_text(d), plugin=label.split("@")[0])
        for f in sorted((plugin_root / "agents").glob("*.md")):
            text = read_text(f)
            fm = frontmatter(text)
            self.add("agent", fm.get("name") or f.stem, harness, "plugin: " + label, f,
                     fm.get("description"), text, plugin=label.split("@")[0])
        servers = {}
        mcp_file = plugin_root / ".mcp.json"
        try:
            if mcp_file.is_file():
                data = json.loads(read_text(mcp_file))
                servers.update(data.get("mcpServers", data) if isinstance(data, dict) else {})
            manifest = plugin_root / (".claude-plugin" if harness == "claude" else ".codex-plugin") / "plugin.json"
            if manifest.is_file():
                data = json.loads(read_text(manifest))
                if isinstance(data.get("mcpServers"), dict):
                    servers.update(data["mcpServers"])
        except ValueError:
            pass
        for name, spec in servers.items():
            if isinstance(spec, dict):
                self.add("mcp", name, harness, "plugin: " + label, mcp_file, mcp_summary(spec), "",
                         plugin=label.split("@")[0])

    def scan_claude_plugins(self, home):
        installed = home / "plugins" / "installed_plugins.json"
        settings = home / "settings.json"
        try:
            enabled = json.loads(read_text(settings)).get("enabledPlugins", {}) if settings.is_file() else {}
            data = json.loads(read_text(installed)) if installed.is_file() else {}
        except ValueError:
            return
        for pid, entries in (data.get("plugins") or {}).items():
            if enabled.get(pid) is False or not entries:
                continue
            path = Path(entries[0].get("installPath", ""))
            if path.is_dir():
                self.plugin_dir(path, pid, "claude")

    def scan_codex_plugins(self, home):
        cfg = read_text(home / "config.toml")
        cache = home / "plugins" / "cache"
        for pid in toml_tables(cfg, "plugins"):
            block = re.search(r'\[\s*plugins\s*\.\s*"{}"\s*\](.*?)(?=^\s*\[|\Z)'.format(re.escape(pid)), cfg, re.S | re.M)
            if block and re.search(r"^\s*enabled\s*=\s*false", block.group(1), re.M):
                continue
            name, _, market = pid.partition("@")
            base = cache / market / name
            if not base.is_dir():
                continue
            versions = sorted((d for d in base.iterdir() if d.is_dir()), key=lambda d: d.stat().st_mtime)
            if versions:
                self.plugin_dir(versions[-1], pid, "codex")

    # -- user-level MCP servers
    def scan_mcp(self):
        claude_json = Path.home() / ".claude.json"
        try:
            data = json.loads(read_text(claude_json, 50_000_000)) if claude_json.is_file() else {}
        except ValueError:
            data = {}
        for name, spec in (data.get("mcpServers") or {}).items():
            self.add("mcp", name, "claude", "user config (~/.claude.json)", claude_json, mcp_summary(spec), "")
        cfg_path = self.homes["codex"] / "config.toml"
        cfg = read_text(cfg_path)
        for name in toml_tables(cfg, "mcp_servers"):
            self.add("mcp", name, "codex", "user config (config.toml)", cfg_path, "", "")

    def scan(self):
        for harness, home in self.homes.items():
            if home.is_dir():
                self.scan_home(harness, home)
        if self.homes["claude"].is_dir():
            self.scan_claude_plugins(self.homes["claude"])
        if self.homes["codex"].is_dir():
            self.scan_codex_plugins(self.homes["codex"])
        self.scan_mcp()
        return self


def mcp_summary(spec):
    if not isinstance(spec, dict):
        return ""
    if spec.get("url"):
        return "{} {}".format(spec.get("type", "http"), spec["url"])
    return " ".join([str(spec.get("command", ""))] + [str(a) for a in spec.get("args", [])][:4])


def mention_patterns(node, bare=True):
    """Regexes that count as 'this text refers to node'.

    Hyphenated names are distinctive enough on their own. Single-word names
    (debugger, pdf, how, rea ...) need context on the same line: the words
    agent/skill/MCP, a /slash form, or a namespaced tool id.
    """
    name = re.escape(node["name"])
    bound = r"(?<![\w/.-]){}(?![\w-])".format(name)
    pats = []
    if node["type"] == "mcp":
        tool = re.escape(re.sub(r"[^A-Za-z0-9_-]", "_", node["name"]))
        pats.append(re.compile(r"mcp__(?:plugin_[\w-]+?_)?{}__".format(tool), re.I))
        pats.append(re.compile(r"^.*" + bound + r".*$", re.M | re.I) if "-" in node["name"]
                    else re.compile(r"^(?=.*\bmcp\b).*" + bound + r".*$", re.M | re.I))
        return pats
    if node.get("plugin"):
        pats.append(re.compile(r"{}:{}(?![\w-])".format(re.escape(node["plugin"]), name)))
        if not bare:
            return pats
    if node["type"] == "skill":
        pats.append(re.compile(r"(?<![\w.-])/{}(?![\w-])".format(name)))
    if "-" in node["name"] and len(node["name"]) >= 6:
        pats.append(re.compile(bound))
    else:
        ctx = r"(?:agent|에이전트|subagent_type)" if node["type"] == "agent" else r"(?:skill|스킬)"
        pats.append(re.compile(r"^(?=.*{}).*{}.*$".format(ctx, bound), re.M | re.I))
    return pats


def build_graph(inv):
    nodes = list(inv.nodes.values())
    # When a bare name exists both as a user skill and inside a plugin, the bare
    # mention goes to the user's own copy; namespaced mentions still reach the plugin.
    edges = {}
    own_names = {(n["type"], n["name"]) for n in nodes if not n.get("plugin")}
    compiled = [(n, mention_patterns(n, bare=not (n.get("plugin") and (n["type"], n["name"]) in own_names)))
                for n in nodes]
    for src in nodes:
        text = src["text"]
        if not text:
            continue
        for dst, pats in compiled:
            if dst is src or (dst["type"] == src["type"] == "skill" and dst["name"] == src["name"]):
                continue
            if any(p.search(text) for p in pats):
                kind = {"agent": "uses subagent", "mcp": "uses MCP", "skill": "references skill"}[dst["type"]]
                edges[(src["id"], dst["id"])] = kind
    out_nodes = [{k: v for k, v in n.items() if k != "text"} for n in nodes]
    out_edges = [{"source": s, "target": t, "kind": k} for (s, t), k in sorted(edges.items())]
    return {"nodes": out_nodes, "edges": out_edges,
            "generated": time.strftime("%Y-%m-%d %H:%M:%S"),
            "homes": {h: str(p) for h, p in inv.env.homes.items()}}


def mode_homes(env, state, mode):
    if mode == "day" or env.dry:
        return dict(env.homes)
    return {h: ensure_home(env, state, mode, h) if env.homes[h].is_dir() else env.homes[h] for h in env.homes}


def write_graph(env, state, out=None, quiet=False, mode="day"):
    graph = build_graph(Inventory(env, state, mode_homes(env, state, mode), mode).scan())
    graph["mode"] = mode
    out = Path(out) if out else env.state_dir / ("graph.html" if mode == "day" else "graph-{}.html".format(mode))
    html = GRAPH_HTML.replace("/*__DATA__*/null", json.dumps(graph, ensure_ascii=False).replace("</", "<\\/"))
    if env.dry:
        return out, graph
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
    if not quiet:
        counts = {}
        for n in graph["nodes"]:
            counts[n["type"]] = counts.get(n["type"], 0) + 1
        say("Graph: {} ({} skills, {} subagents, {} MCP servers, {} links)".format(
            out, counts.get("skill", 0), counts.get("agent", 0), counts.get("mcp", 0), len(graph["edges"])))
    return out, graph


GRAPH_HTML = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Agent skill graph</title>
<style>
:root{--bg:#1e1e1e;--panel:#252526;--line:#3a3a3a;--text:#dcddde;--muted:#8a8f98;
--skill:#a882ff;--agent:#2bd4bd;--mcp:#ff9f43;--edge:rgba(160,160,170,.22);--hi:#ffffff}
@media (prefers-color-scheme: light){:root:not([data-theme=dark]){--bg:#f6f6f7;--panel:#ffffff;--line:#e2e2e6;
--text:#222;--muted:#666;--edge:rgba(60,60,80,.18);--hi:#000}}
:root[data-theme=light]{--bg:#f6f6f7;--panel:#ffffff;--line:#e2e2e6;--text:#222;--muted:#666;--edge:rgba(60,60,80,.18);--hi:#000}
*{box-sizing:border-box}html,body{margin:0;height:100%;background:var(--bg);color:var(--text);
font:13px/1.45 -apple-system,BlinkMacSystemFont,"Segoe UI","Apple SD Gothic Neo","Malgun Gothic",sans-serif}
#c{position:fixed;inset:0;width:100%;height:100%;cursor:grab}
#c.drag{cursor:grabbing}
.bar{position:fixed;top:12px;left:12px;display:flex;flex-wrap:wrap;gap:8px;align-items:center;
max-width:calc(100% - 24px);z-index:2}
.box{background:var(--panel);border:1px solid var(--line);border-radius:8px;padding:6px 10px}
input[type=search]{background:transparent;border:0;color:var(--text);outline:none;width:190px;font:inherit}
label{display:inline-flex;gap:4px;align-items:center;margin-right:8px;white-space:nowrap;cursor:pointer}
.dot{width:9px;height:9px;border-radius:50%;display:inline-block}
#panel{position:fixed;top:12px;right:12px;width:340px;max-width:calc(100% - 24px);max-height:calc(100% - 24px);
overflow:auto;z-index:3;display:none}
#panel h2{font-size:15px;margin:0 0 4px}#panel .k{color:var(--muted)}#panel ul{padding-left:16px;margin:4px 0}
#panel a{color:var(--text);text-decoration:underline dotted;cursor:pointer}
#panel .close{float:right;cursor:pointer;color:var(--muted)}
.meta{position:fixed;left:12px;bottom:12px;color:var(--muted);z-index:2;font-size:12px}
button{background:transparent;color:var(--text);border:1px solid var(--line);border-radius:6px;padding:2px 8px;cursor:pointer;font:inherit}
@media (max-width:600px){#panel{top:auto;bottom:12px;max-height:45%}input[type=search]{width:120px}}
</style></head><body>
<canvas id="c"></canvas>
<div class="bar">
  <div class="box"><input id="q" type="search" placeholder="Search skills, agents, MCP…"></div>
  <div class="box" id="types"></div>
  <div class="box" id="hs"></div>
  <div class="box" id="srcs"></div>
  <div class="box"><label><input type="checkbox" id="orph"> hide unlinked</label>
  <button id="fit">fit</button> <button id="theme">theme</button></div>
</div>
<div id="panel" class="box"></div>
<div class="meta" id="meta"></div>
<script>
const G=/*__DATA__*/null;
const COLORS={skill:'--skill',agent:'--agent',mcp:'--mcp'};
const css=n=>getComputedStyle(document.documentElement).getPropertyValue(n).trim();
const cv=document.getElementById('c'),ctx=cv.getContext('2d');
let W=0,H=0,DPR=window.devicePixelRatio||1;
const nodes=G.nodes.map((n,i)=>{const r=10*Math.sqrt(i+.5),a=i*2.39996;return Object.assign(n,{i,x:r*Math.cos(a),y:r*Math.sin(a),vx:0,vy:0,out:[],inn:[]})});
const byId=Object.fromEntries(nodes.map(n=>[n.id,n]));
const edges=G.edges.filter(e=>byId[e.source]&&byId[e.target]).map(e=>{const s=byId[e.source],t=byId[e.target];s.out.push({n:t,kind:e.kind});t.inn.push({n:s,kind:e.kind});return{s,t,kind:e.kind}});
nodes.forEach(n=>{n.deg=n.out.length+n.inn.length;n.r=3.5+Math.sqrt(n.deg)*2.2;n.group=n.source.startsWith('plugin')?'plugin':n.source.startsWith('third')?'third-party':n.source==='mine'?'mine':n.source.startsWith('user config')?'user config':'unmanaged'});
const state={types:new Set(['skill','agent','mcp']),hs:new Set(['claude','codex']),groups:new Set(nodes.map(n=>n.group)),orph:false,q:'',hover:null,sel:null};
function chk(box,key,vals,label,colorOf){const el=document.getElementById(box);vals.forEach(v=>{const l=document.createElement('label');const c=document.createElement('input');c.type='checkbox';c.checked=true;c.onchange=()=>{c.checked?state[key].add(v):state[key].delete(v);heat(.3)};l.append(c);if(colorOf){const d=document.createElement('span');d.className='dot';d.style.background=colorOf(v);l.append(d)}l.append(document.createTextNode(label(v)));el.append(l)})}
const count=t=>nodes.filter(n=>n.type===t).length;
chk('types','types',['skill','agent','mcp'],t=>({skill:'skills',agent:'subagents',mcp:'MCP'}[t])+' '+count(t),t=>css(COLORS[t]));
chk('hs','hs',['claude','codex'],h=>h);
chk('srcs','groups',[...state.groups].sort(),g=>g);
document.getElementById('orph').onchange=e=>{state.orph=e.target.checked;heat(.3)};
document.getElementById('q').oninput=e=>{state.q=e.target.value.toLowerCase();const m=nodes.find(n=>visible(n)&&state.q&&n.name.toLowerCase().includes(state.q));if(m)focus(m)};
document.getElementById('fit').onclick=fit;
document.getElementById('theme').onclick=()=>{const r=document.documentElement;r.dataset.theme=(r.dataset.theme||(matchMedia('(prefers-color-scheme: light)').matches?'light':'dark'))==='dark'?'light':'dark'};
document.getElementById('meta').textContent=`${nodes.length} nodes · ${edges.length} links · generated ${G.generated} from ${Object.values(G.homes).join(', ')}`;
function visible(n){if(!state.types.has(n.type)||!state.groups.has(n.group))return false;if(!n.harness.some(h=>state.hs.has(h)))return false;if(state.orph&&!n.out.concat(n.inn).some(o=>visible0(o.n)))return false;return true}
function visible0(n){return state.types.has(n.type)&&state.groups.has(n.group)&&n.harness.some(h=>state.hs.has(h))}
let cam={x:0,y:0,k:1},alpha=1;
function heat(a){alpha=Math.max(alpha,a)}
function resize(){W=innerWidth;H=innerHeight;cv.width=W*DPR;cv.height=H*DPR}
addEventListener('resize',resize);resize();
function tick(){if(alpha<.002)return;const vs=nodes.filter(visible);
 const STR=-160;
 for(let a=0;a<vs.length;a++){const p=vs[a];for(let b=a+1;b<vs.length;b++){const q=vs[b];let dx=q.x-p.x,dy=q.y-p.y,l=dx*dx+dy*dy;
  if(l<1){dx=Math.random()-.5;dy=Math.random()-.5;l=dx*dx+dy*dy}if(l>640000)continue;const w=STR*alpha/l;p.vx+=dx*w;p.vy+=dy*w;q.vx-=dx*w;q.vy-=dy*w}}
 for(const e of edges){if(!visible(e.s)||!visible(e.t))continue;const s=e.s,t=e.t;let dx=t.x+t.vx-s.x-s.vx,dy=t.y+t.vy-s.y-s.vy;const l=Math.sqrt(dx*dx+dy*dy)||1;
  const f=(l-55)/l*alpha*.35/Math.min(s.deg||1,t.deg||1),bs=(s.deg||1)/((s.deg||1)+(t.deg||1));t.vx-=dx*f*bs;t.vy-=dy*f*bs;s.vx+=dx*f*(1-bs);s.vy+=dy*f*(1-bs)}
 for(const n of vs){const g=n.deg?.02:.06;n.vx-=n.x*g*alpha;n.vy-=n.y*g*alpha;if(n!==drag){n.x+=n.vx;n.y+=n.vy}n.vx*=.6;n.vy*=.6}
 alpha+=(0-alpha)*.0228}
function toScreen(n){return[(n.x-cam.x)*cam.k+W/2,(n.y-cam.y)*cam.k+H/2]}
function toWorld(x,y){return[(x-W/2)/cam.k+cam.x,(y-H/2)/cam.k+cam.y]}
function nbrs(n){const s=new Set([n]);n.out.forEach(o=>s.add(o.n));n.inn.forEach(o=>s.add(o.n));return s}
function draw(){ctx.setTransform(DPR,0,0,DPR,0,0);ctx.clearRect(0,0,W,H);
 const focusN=state.hover||state.sel,near=focusN?nbrs(focusN):null,q=state.q;
 ctx.lineWidth=1;
 for(const e of edges){if(!visible(e.s)||!visible(e.t))continue;const on=near&&(e.s===focusN||e.t===focusN);
  ctx.strokeStyle=on?css(COLORS[e.t.type]):css('--edge');ctx.globalAlpha=near&&!on?.15:1;
  const[a,b]=toScreen(e.s),[c,d]=toScreen(e.t);ctx.beginPath();ctx.moveTo(a,b);ctx.lineTo(c,d);ctx.stroke();
  if(cam.k>1.2||on){const ang=Math.atan2(d-b,c-a),r=e.t.r*Math.min(cam.k,2)+2,x=c-Math.cos(ang)*r,y=d-Math.sin(ang)*r;ctx.beginPath();ctx.moveTo(x,y);ctx.lineTo(x-7*Math.cos(ang-.4),y-7*Math.sin(ang-.4));ctx.lineTo(x-7*Math.cos(ang+.4),y-7*Math.sin(ang+.4));ctx.closePath();ctx.fillStyle=ctx.strokeStyle;ctx.fill()}}
 for(const n of nodes){if(!visible(n))continue;const[x,y]=toScreen(n),dim=near?!near.has(n):(q&&!n.name.toLowerCase().includes(q));
  ctx.globalAlpha=dim?.18:1;ctx.fillStyle=css(COLORS[n.type]);const r=n.r*Math.min(Math.max(cam.k,.6),2);
  ctx.beginPath();ctx.arc(x,y,r,0,7);ctx.fill();
  if(n===state.sel){ctx.strokeStyle=css('--hi');ctx.lineWidth=2;ctx.stroke();ctx.lineWidth=1}
  if(!dim&&(cam.k>1.7||(cam.k>.9&&n.deg>=8)||(near&&near.has(n))||(q&&n.name.toLowerCase().includes(q)))){ctx.fillStyle=css('--text');ctx.font=(n===focusN?'600 ':'')+'12px sans-serif';ctx.textAlign='center';ctx.fillText((n.plugin?n.plugin+':':'')+n.name,x,y+r+12)}}
 ctx.globalAlpha=1}
function loop(){tick();draw();requestAnimationFrame(loop)}
function pick(mx,my){let best=null,bd=1e9;for(const n of nodes){if(!visible(n))continue;const[x,y]=toScreen(n),d=Math.hypot(x-mx,y-my);if(d<Math.max(n.r*cam.k,6)+3&&d<bd){bd=d;best=n}}return best}
let drag=null,pan=null,moved=false;
cv.onpointerdown=e=>{moved=false;const n=pick(e.clientX,e.clientY);if(n){drag=n}else{pan=[e.clientX,e.clientY,cam.x,cam.y]}cv.classList.add('drag');cv.setPointerCapture(e.pointerId)};
cv.onpointermove=e=>{if(drag){const[x,y]=toWorld(e.clientX,e.clientY);drag.x=x;drag.y=y;moved=true;heat(.15)}else if(pan){cam.x=pan[2]-(e.clientX-pan[0])/cam.k;cam.y=pan[3]-(e.clientY-pan[1])/cam.k;moved=true}else{const n=pick(e.clientX,e.clientY);state.hover=n;cv.style.cursor=n?'pointer':'grab'}};
cv.onpointerup=e=>{if(!moved){const n=pick(e.clientX,e.clientY);select(n)}drag=null;pan=null;cv.classList.remove('drag')};
cv.onwheel=e=>{e.preventDefault();const[wx,wy]=toWorld(e.clientX,e.clientY);cam.k=Math.min(6,Math.max(.15,cam.k*Math.exp(-e.deltaY*.0015)));const[nx,ny]=toWorld(e.clientX,e.clientY);cam.x+=wx-nx;cam.y+=wy-ny};
function esc(s){return String(s).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]))}
function select(n){state.sel=n;const p=document.getElementById('panel');if(!n){p.style.display='none';return}
 const list=(arr,title)=>arr.length?`<div class="k">${title}</div><ul>${arr.map(o=>`<li><a data-id="${esc(o.n.id)}">${esc((o.n.plugin?o.n.plugin+':':'')+o.n.name)}</a> <span class="k">${esc(o.n.type)}</span></li>`).join('')}</ul>`:'';
 p.innerHTML=`<span class="close" id="x">✕</span><h2><span class="dot" style="background:${css(COLORS[n.type])}"></span> ${esc((n.plugin?n.plugin+':':'')+n.name)}</h2>
 <div class="k">${esc(n.type)} · ${esc(n.harness.join(' + '))} · ${esc(n.source)}</div><p>${esc(n.desc||'')}</p>
 ${list(n.out.filter(o=>o.n.type==='agent'),'Uses subagents')}${list(n.out.filter(o=>o.n.type==='mcp'),'Uses MCP')}${list(n.out.filter(o=>o.n.type==='skill'),'References skills')}${list(n.inn,'Used by')}
 <div class="k" style="word-break:break-all;margin-top:6px">${esc(n.path)}</div>`;
 p.style.display='block';document.getElementById('x').onclick=()=>select(null);
 p.querySelectorAll('a[data-id]').forEach(a=>a.onclick=()=>focus(byId[a.dataset.id]))}
function focus(n){select(n);cam.x=n.x;cam.y=n.y;cam.k=Math.max(cam.k,1.4)}
function fit(){const vs=nodes.filter(visible);if(!vs.length)return;const xs=vs.map(n=>n.x).sort((a,b)=>a-b),ys=vs.map(n=>n.y).sort((a,b)=>a-b),pc=(arr,f)=>arr[Math.min(arr.length-1,Math.floor(f*arr.length))];const x0=pc(xs,.03),x1=pc(xs,.97),y0=pc(ys,.03),y1=pc(ys,.97);cam.x=(x0+x1)/2;cam.y=(y0+y1)/2;cam.k=Math.min(2,.9*Math.min(W/(x1-x0+80),H/(y1-y0+80)))}
for(let i=0;i<350;i++)tick();fit();loop();
</script></body></html>
"""


# ---------------------------------------------------------------- commands

def refresh_homes(env, state, mode):
    """Re-sync existing session homes of `mode` (new links, regenerated Codex config)."""
    if env.dry or mode == "day":
        return
    root = env.state_dir / "homes" / mode
    for home in sorted(root.iterdir()) if root.is_dir() else []:
        harness, _, account = home.name.partition("-")
        if harness in env.homes:
            ensure_home(env, state, mode, harness, account or None)


def cmd_install(env, cat, state, tokens, preset):
    if preset:
        if preset not in cat["presets"]:
            raise Abort("unknown preset: " + preset)
        tokens = list(cat["presets"][preset]) + list(tokens)
        if not env.target_mode and preset in MODES:
            env.target_mode = preset
    env.target_mode = env.target_mode or "day"
    ensure_wiring(env, state)
    if not tokens:
        tokens = interactive_pick(cat, state, env)
    selection = parse_selection(cat, tokens)
    say("\nInstalling {} package(s) into mode '{}' for {} ({}){}".format(
        len(selection), env.target_mode, "+".join(env.harnesses), env.method, " — dry run" if env.dry else ""))
    if not confirm(env, "Continue?"):
        raise Abort("cancelled")
    legacy = load_legacy_backups(env)
    units = expand(env, cat, selection)
    changed = 0
    cache = {}
    seen = set()
    for u in units:
        if u.kind == "path":
            if u.key in seen:
                warn("{} is provided twice in this selection; keeping the first".format(u.key))
                continue
            seen.add(u.key)
            changed += install_path(env, state, u, legacy)
        elif u.kind == "hooks":
            changed += install_hooks(env, state, u)
        elif u.kind == "mcp":
            try:
                changed += install_mcp(env, state, u)
            except Abort as exc:
                warn(str(exc))
        else:
            try:
                changed += install_plugin(env, state, u, cache)
            except Abort as exc:
                warn(str(exc))
    sync_codex_config(env, state)
    refresh_homes(env, state, env.target_mode)
    finish_legacy(env, state)
    say("\nDone: {} change(s). State: {}".format(changed, state.path))
    write_graph(env, state, mode=env.target_mode)
    say("Undo with: python3 {} uninstall <package>   (or: uninstall --all)".format(REPO / "install.py"))


def cmd_uninstall(env, cat, state, tokens, everything):
    mode = env.target_mode = env.target_mode or "day"
    ensure_wiring(env, state)
    installed = sorted(state.packages(mode))
    if everything:
        tokens = installed
    if not tokens:
        if not installed:
            say("Nothing installed by agent-skills.")
            return
        say("Installed packages:")
        for i, pid in enumerate(installed, 1):
            say("  {:>2} {}".format(i, pid))
        say("Type numbers or ids to remove, `all`, or `q`.")
        tty = open_tty()
        line = (tty.readline() if tty else "").replace(",", " ").split()
        if not line or line == ["q"]:
            raise Abort("nothing selected")
        tokens = installed if line == ["all"] else [
            installed[int(t) - 1] if t.isdigit() and 1 <= int(t) <= len(installed) else t for t in line]
    targets = []
    for tok in tokens:
        pid, _, sub = tok.partition(":")
        if pid not in installed:
            warn(pid + " is not installed by agent-skills")
            continue
        targets.append((pid, sub or None))
    if not targets:
        return
    say("Removing: " + ", ".join(p + (":" + s if s else "") for p, s in targets))
    if not confirm(env, "Continue?"):
        raise Abort("cancelled")
    for pid, sub in targets:
        for key, rec in sorted(state.data["items"].items()):
            if rec["package"] == pid and rec.get("mode") == mode and (not sub or rec["dest"] == "skills/" + sub):
                uninstall_path(env, state, key)
        if sub or any(r["package"] == pid and r.get("mode") not in (None, mode) for r in state.data["items"].values()):
            continue  # still in another mode: keep its shared (home-level) parts
        for key, rec in sorted(state.data["items"].items()):
            if rec["package"] == pid and rec.get("mode") is None:
                uninstall_path(env, state, key)
        if not sub:
            for key, rec in sorted(state.data["plugins"].items()):
                if rec["package"] == pid:
                    uninstall_plugin(env, state, key)
            for key, rec in sorted(state.data["mcp"].items()):
                if rec["package"] == pid:
                    uninstall_mcp(env, state, key)
            uninstall_hooks(env, state, pid)
    sync_codex_config(env, state)
    refresh_homes(env, state, mode)
    if everything and not state.data["items"]:
        unwire(env)
    say("Done.")
    write_graph(env, state, mode=mode)


def finish_legacy(env, state):
    """Retire the previous ./setup journal once every link it made is owned here."""
    if env.dry or not env.legacy_state.exists():
        return
    try:
        data = json.loads(env.legacy_state.read_text(encoding="utf-8"))
    except ValueError:
        return
    if data.get("repo") != str(REPO):
        return
    home = Path.home()
    pending = [r["path"] for r in data.get("records", []) if r.get("kind") == "link"
               and points_into_repo(home / r["path"])
               and not any("." + rec["harness"] + "/" + rec["dest"] == r["path"]
                           for rec in state.data["items"].values())]
    if pending:
        say("  note: {} link(s) from the previous ./setup are not managed here yet: {}".format(
            len(pending), short(", ".join(pending), 200)))
        return
    retired = env.legacy_state.with_name("state.retired-{}.json".format(time.strftime("%Y%m%d-%H%M%S")))
    os.replace(env.legacy_state, retired)
    say("  previous ./setup journal retired -> {} (its backups stay in place)".format(retired))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd")

    def common(p):
        p.add_argument("--harness", help="claude,codex (default: whichever is present)")
        p.add_argument("--dry-run", action="store_true", help="show what would happen")
        p.add_argument("-y", "--yes", action="store_true", help="do not ask for confirmation")
        p.add_argument("--force", action="store_true", help="replace/remove items changed after install")

    p_list = sub.add_parser("list", help="show the catalog")
    p_list.add_argument("--installed", action="store_true")
    p_list.add_argument("--json", action="store_true")
    p_list.add_argument("--harness")
    p_list.add_argument("--mode", choices=MODES, default="day")
    p_in = sub.add_parser("install", help="install packages (interactive if none given)")
    p_in.add_argument("packages", nargs="*")
    p_in.add_argument("--preset")
    p_in.add_argument("--mode", choices=MODES, help="which skill set to install into (default: day, or the preset's name)")
    p_in.add_argument("--method", choices=["link", "copy"], help="link (default; copy on Windows) or copy")
    common(p_in)
    p_un = sub.add_parser("uninstall", help="remove installed packages (interactive if none given)")
    p_un.add_argument("packages", nargs="*")
    p_un.add_argument("--all", action="store_true", help="everything in this mode")
    p_un.add_argument("--mode", choices=MODES, default="day")
    common(p_un)
    p_home = sub.add_parser("home", help="print (and prepare) the home a session of MODE should use")
    p_home.add_argument("session_mode", choices=MODES)
    p_home.add_argument("tool", choices=["claude", "codex"])
    p_home.add_argument("--account", help="Codex account home suffix (~/.codex-<account>); omit or 'main' for ~/.codex")
    p_gr = sub.add_parser("graph", help="write an Obsidian-style dependency graph of what is installed")
    p_gr.add_argument("--mode", choices=MODES, default="day")
    p_gr.add_argument("--out", help="output HTML path (default: ~/.agent-skills/graph.html)")
    p_gr.add_argument("--open", action="store_true", help="open it in the browser")
    p_gr.add_argument("--json", action="store_true", help="print the graph data as JSON instead")
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or (argv[0].startswith("-") and argv[0] not in ("-h", "--help")):
        argv = ["install"] + argv  # bare `install.py [--flags]` opens the picker
    args = ap.parse_args(argv)
    try:
        env = Env(args)
        env.yes = getattr(args, "yes", False)
        cat = load_catalog()
        state = State(env)
        if args.cmd == "list":
            if args.json:
                print(json.dumps({"installed": sorted(state.packages()),
                                  "packages": [{k: p[k] for k in ("id", "group", "title", "description")}
                                               for p in cat["packages"]]}, ensure_ascii=False, indent=2))
            else:
                print_catalog(cat, state, args.installed, args.mode)
        elif args.cmd == "install":
            cmd_install(env, cat, state, args.packages, args.preset)
        elif args.cmd == "uninstall":
            cmd_uninstall(env, cat, state, args.packages, args.all)
        elif args.cmd == "home":
            out, sys.stdout = sys.stdout, sys.stderr  # only the path goes to stdout (shell captures it)
            try:
                ensure_wiring(env, state)
                home = ensure_home(env, state, args.session_mode, args.tool, args.account)
            finally:
                sys.stdout = out
            print(home)
        elif args.cmd == "graph":
            ensure_wiring(env, state)
            if args.json:
                print(json.dumps(build_graph(Inventory(env, state, mode_homes(env, state, args.mode), args.mode).scan()),
                                 ensure_ascii=False, indent=2))
            else:
                out, _ = write_graph(env, state, args.out, mode=args.mode)
                if args.open:
                    import webbrowser
                    webbrowser.open(out.resolve().as_uri())
        return 0
    except Abort as exc:
        print("agent-skills: " + str(exc), file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\ninterrupted", file=sys.stderr)
        return 130


if __name__ == "__main__":
    sys.exit(main())
