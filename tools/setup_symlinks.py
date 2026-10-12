#!/usr/bin/env python3
"""Safe item-symlink installer. Never imports assets from HOME."""
import argparse
import copy
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shlex
import stat
import sys

ROOT = Path(__file__).resolve().parents[1]
TARGETS = {'claude', 'codex'}
DENIED = {'matt-pocock', 'mattpocock-skills', 'matt-potcock', 'mattpocock', 'auto-code'}
PRIVATE = {'auth', 'credentials', 'credential', 'token', 'tokens', 'auth.json', 'credentials.json', 'tokens.json', 'history', 'history.jsonl', 'sessions', 'projects', 'memory', 'logs', 'cache', '.system', '.DS_Store', '.env', '.git', '__pycache__', '.venv'}

def encode(value):
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True)+'\n').encode()

def exists(path):
    return path.exists() or path.is_symlink()

def blocked(value):
    parts = PurePosixPath(value).parts
    return any(p in PRIVATE or p.startswith('._') or p.endswith(('.sqlite', '.sqlite3', '.db', '.pyc')) or any(d in p.lower() for d in DENIED) for p in parts)

def relative(value):
    if not isinstance(value, str) or not value or '\\' in value:
        raise ValueError('invalid relative path')
    p = PurePosixPath(value)
    if p.is_absolute() or '..' in p.parts or value != str(p) or blocked(value):
        raise ValueError('unsafe or denied path: '+value)
    return p

def no_symlink_parents(path, include_leaf=False):
    p = path if include_leaf else path.parent
    for part in [p]+list(p.parents):
        if part.is_symlink():
            trusted_aliases={Path('/var'):Path('/private/var'),Path('/tmp'):Path('/private/tmp')}
            if part in trusted_aliases and part.resolve()==trusted_aliases[part]: continue
            raise ValueError('symlink path component: '+str(part))
        if part.exists() and not part.is_dir():
            raise ValueError('non-directory path component: '+str(part))

def source(value):
    p = ROOT / str(relative(value))
    no_symlink_parents(p)
    if p.is_symlink() or not p.exists():
        raise ValueError('missing or symlink source: '+str(p))
    for q in ([p] if p.is_file() else p.rglob('*')):
        if q.is_symlink() or blocked(str(q.relative_to(ROOT))):
            raise ValueError('unsafe source entry: '+str(q))
        if not q.is_file() and not q.is_dir():
            raise ValueError('non-regular source entry: '+str(q))
    return p

def validate_destination(harness, value):
    if harness not in TARGETS: raise ValueError('unknown harness')
    p = relative(value)
    filename = 'CLAUDE.md' if harness=='claude' else 'AGENTS.md'
    if str(p) != filename and not (len(p.parts)>=2 and p.parts[0] in {'skills','agents','commands','prompts','hooks'}):
        raise ValueError('not an item-level destination: '+value)
    return p

def load_contract(check_sources=True):
    manifest = json.loads((ROOT/'manifest.yaml').read_text())
    if manifest.get('schema_version') != 2 or manifest.get('contract') != 'item-symlink':
        raise ValueError('unsupported manifest contract')
    seen=set()
    for entry in manifest['links']:
        validate_destination(entry['harness'],entry['destination'])
        key=(entry['harness'],entry['destination'])
        if key in seen: raise ValueError('duplicate destination: '+str(key))
        destination=PurePosixPath(entry['destination'])
        for harness,other in seen:
            if harness==entry['harness'] and (PurePosixPath(other) in destination.parents or destination in PurePosixPath(other).parents):
                raise ValueError('overlapping item destinations: '+entry['destination'])
        seen.add(key)
        if check_sources: source(entry['source'])
        else: relative(entry['source'])
    lock=json.loads(source(manifest['dependencies']).read_text())
    policy=json.loads(source(manifest['denylist']).read_text())
    if not DENIED.issubset(set(policy['ids'])): raise ValueError('denylist weakened')
    templates={h:json.loads(source(v).read_text()) for h,v in manifest['templates'].items()}
    if set(templates)!=TARGETS: raise ValueError('both harness templates required')
    if set(templates['claude'])-{'hooks','permissions','enabledPlugins','extraKnownMarketplaces'}: raise ValueError('non-shareable Claude template keys')
    if set(templates['codex'])-{'agents','plugins','permissions','hooks'}: raise ValueError('non-shareable Codex template keys')
    return manifest,lock,templates

def merge(old,new):
    if isinstance(old,dict) and isinstance(new,dict):
        result=copy.deepcopy(old)
        for key,value in new.items(): result[key]=merge(result[key],value) if key in result else copy.deepcopy(value)
        return result
    if isinstance(old,list) and isinstance(new,list):
        return old+[x for x in new if x not in old]
    return copy.deepcopy(new)

def render(value, home):
    # Quote paths inside shell commands, not in native config_file strings.
    if isinstance(value,dict):
        result = {}
        for k,v in value.items():
            if k=='command' and isinstance(v,str):
                v=re.sub(r'"\$\{REPO\}([^"\n]*)"',lambda m:shlex.quote(str(ROOT)+m[1]),v)
                v=v.replace('${REPO}',shlex.quote(str(ROOT)))
            result[k]=render(v,home)
        return result
    if isinstance(value,list): return [render(v,home) for v in value]
    if isinstance(value,str): return value.replace('${REPO}',str(ROOT)).replace('${HOME}',str(home))
    return value

def toml_key(key): return json.dumps(key,ensure_ascii=False)

def toml_scalar(value):
    if isinstance(value,bool): return 'true' if value else 'false'
    if isinstance(value,str): return json.dumps(value,ensure_ascii=False)
    if isinstance(value,(int,float)): return str(value)
    if isinstance(value,list): return '['+', '.join(toml_scalar(v) for v in value)+']'
    raise ValueError('unsupported TOML template value')

def split_keys(value):
    tokens=re.findall(r'"(?:[^"\\]|\\.)*"|\x27[^\x27]*\x27|[A-Za-z0-9_-]+',value)
    return [json.loads(k) if k.startswith('"') else k[1:-1] if k.startswith("'") else k for k in tokens]


def scalar_from_toml(rhs):
    match=re.match(r'^\s*("(?:[^"\\]|\\.)*"|\x27[^\x27]*\x27|true|false|[-+0-9.eE]+)\s*(?:#.*)?$',rhs)
    if not match: raise ValueError('unsupported target TOML scalar')
    text=match[1]
    if text.startswith("'"): return text[1:-1]
    return json.loads(text)


def toml_multiline_state(line,state):
    """Track multiline quoted strings so their contents are never table headers."""
    i=0
    while i<len(line):
        if state:
            end=line.find(state,i)
            if end<0: return state
            # Backslash escapes matter only in multiline basic strings.
            if state=='"""' and end>0 and line[end-1]=='\\': i=end+3; continue
            i=end+3; state=None; continue
        if line[i]=='#': break
        if line[i:i+3] in ('"""',"'''"):
            state=line[i:i+3]; i+=3; continue
        if line[i] in ('"',"'"):
            quote=line[i]; i+=1
            while i<len(line):
                if quote=='"' and line[i]=='\\': i+=2; continue
                if line[i]==quote: i+=1; break
                i+=1
            continue
        i+=1
    return state

def merge_toml(text, template):
    """Surgical table edits preserve unknown keys/comments and machine-specific trust.

    Python 3.11+ validates all TOML. Older Python supports the explicit simple
    table/assignment form here and rejects ambiguous target multiline values.
    """
    try:
        import tomllib
    except ImportError:
        tomllib=None
    if tomllib: tomllib.loads(text)
    desired={}
    def flatten(value,table=()):
        for k,v in value.items():
            if isinstance(v,dict): flatten(v,table+(k,))
            else: desired[(table,k)]=v
    flatten(template)
    lines=text.splitlines(keepends=True); table=(); found=set(); tables={():0}; insertions={}; multiline=None
    for i,line in enumerate(lines):
        inside_multiline=multiline is not None
        multiline=toml_multiline_state(line,multiline)
        if inside_multiline: continue
        header=re.match(r'^\s*\[([^\[\]]+)\]\s*(?:#.*)?$',line)
        if header:
            table=tuple(split_keys(header[1])); tables[table]=i+1
        assignment=re.match(r'^\s*("(?:[^"\\]|\\.)*"|[A-Za-z0-9_-]+)\s*=\s*(.*)',line)
        if assignment:
            key=split_keys(assignment[1])[0]; coordinate=(table,key)
            if coordinate in desired:
                # Do not misidentify multiline strings/arrays as a one-line value.
                rhs=assignment[2].strip()
                if rhs.startswith(('"""',"'''",'[' ,'{')): raise ValueError('target multiline/inline TOML value requires manual review: '+key)
                value=desired[coordinate]
                parsed=tomllib.loads('v = '+rhs)['v'] if tomllib else scalar_from_toml(rhs)
                if parsed==value: found.add(coordinate); continue
                canonical=toml_key(key)+' = '+toml_scalar(value)+'\n'
                if line==canonical: found.add(coordinate); continue
                lines[i]=canonical; found.add(coordinate)
    new_tables={}
    for (tab,key),v in desired.items():
        if (tab,key) in found: continue
        row=toml_key(key)+' = '+toml_scalar(v)+'\n'
        if tab in tables: insertions.setdefault(tables[tab],[]).append(row)
        else: new_tables.setdefault(tab,[]).append(row)
    for tab,rows in new_tables.items():
        insertions.setdefault(len(lines),[]).append('\n['+'.'.join(toml_key(x) for x in tab)+']\n'+''.join(rows))
    for index in sorted(insertions,reverse=True): lines[index:index]=insertions[index]
    result=''.join(lines)
    if tomllib: tomllib.loads(result)
    return result

class Installer:
    def __init__(self,home,dry=False):
        self.home=home; self.dry=dry; self.state_dir=home/'.agent-skills-setup'
        no_symlink_parents(self.state_dir,True)
        self.state_path=self.state_dir/'state.json'
        if self.state_path.is_symlink(): raise ValueError('symlink state')
        self.state=json.loads(self.state_path.read_text()) if self.state_path.exists() else {'version':1,'repo':str(ROOT),'records':[],'directories':[],'native':{}}
        if self.state.get('repo')!=str(ROOT) or self.state.get('version')!=1: raise ValueError('state belongs to another repo/version')
        for r in self.state['records']:
            path = self.path(r['path'])
            if r.get('backup') and not re.fullmatch(r'backups/[0-9]+',r['backup']): raise ValueError('unsafe state backup')
            if r.get('backup'): no_symlink_parents(self.state_dir/r['backup'])
            if not self.matches(path,r): raise ValueError('managed item changed by user: '+r['path'])
        for rel in self.state['directories']:
            p = PurePosixPath(rel)
            if not p.parts or p.parts[0] not in {'.claude','.codex'} or '..' in p.parts or p.is_absolute(): raise ValueError('unsafe state directory')
            no_symlink_parents(self.home/rel,True)
        self.changed=False

    def path(self, rel):
        p=PurePosixPath(rel)
        cache_retirement = bool(re.fullmatch(r'\.(claude|codex)/plugins/cache/[a-z0-9._-]+/(superpowers|bagjuhyeon-agent-ssot)', rel))
        forbidden = blocked('/'.join(p.parts[1:])) and not cache_retirement
        if p.is_absolute() or '..' in p.parts or str(p)!=rel or p.parts[0] not in {'.claude','.codex'} or forbidden:
            raise ValueError('unsafe state destination: '+rel)
        if not cache_retirement and rel not in {'.claude/settings.json','.codex/config.toml','.claude/plugins/installed_plugins.json','.claude/plugins/known_marketplaces.json'}:
            validate_destination(p.parts[0][1:], '/'.join(p.parts[1:]))
        path=self.home/rel; no_symlink_parents(path)
        return path

    def save(self):
        if self.dry: return
        self.state_dir.mkdir(mode=0o700,exist_ok=True)
        temp=self.state_dir/'state.new'
        if temp.is_symlink(): raise ValueError('symlink journal temp')
        with temp.open('wb') as f: f.write(encode(self.state)); f.flush(); os.fsync(f.fileno())
        os.replace(temp,self.state_path)

    def mkdir(self,path):
        if path.exists(): return
        self.mkdir(path.parent)
        path.mkdir()
        if path!=self.home and self.state_dir not in [path]+list(path.parents):
            self.state['directories'].append(str(path.relative_to(self.home))); self.save()

    def record(self,rel): return next((r for r in self.state['records'] if r['path']==rel),None)

    def backup(self,rel,kind,installed):
        path=self.path(rel)
        old=self.record(rel)
        if old:
            if not self.matches(path,old): raise ValueError('managed item changed by user: '+rel)
            return old
        r={'path':rel,'kind':kind,'installed':installed,'backup':None}
        if exists(path):
            if path.is_symlink() and kind=='file': raise ValueError('config symlink refused: '+rel)
            if kind=='file' and not path.is_file(): raise ValueError('config is not a regular file: '+rel)
            r['backup']='backups/'+str(len(self.state['records']))
        self.state['records'].append(r); self.save()
        if r['backup']:
            b=self.state_dir/r['backup']; no_symlink_parents(b)
            if exists(b): raise ValueError('refusing to overwrite existing backup: '+str(b))
            b.parent.mkdir(mode=0o700,exist_ok=True); os.rename(path,b)
            print('BACKUP '+str(path)+' -> '+str(b))
        return r

    def matches(self,path,record):
        if record['kind']=='link': return path.is_symlink() and os.readlink(path)==record['installed']
        if record['kind']=='moved': return not exists(path)
        return path.is_file() and not path.is_symlink() and hashlib.sha256(path.read_bytes()).hexdigest()==record['installed']

    def link(self,rel,src):
        path=self.path(rel)
        if path.is_symlink() and os.readlink(path)==str(src): return
        print('LINK '+str(path)+' -> '+str(src)); self.changed=True
        if self.dry: return
        r=self.backup(rel,'link',str(src)); self.mkdir(path.parent)
        if exists(path): path.unlink()  # only a previously owned verified symlink
        path.symlink_to(src); r.update(kind='link',installed=str(src)); self.save()

    def write(self,rel,data):
        path=self.path(rel)
        if path.is_symlink() or (path.exists() and not path.is_file()): raise ValueError('config must be a regular file: '+rel)
        if path.exists() and path.read_bytes()==data: return
        print('MERGE '+str(path)); self.changed=True
        if self.dry: return
        digest=hashlib.sha256(data).hexdigest()
        r=self.backup(rel,'file',digest); self.mkdir(path.parent)
        temp=path.with_name(path.name+'.ssot-new')
        if exists(temp): raise ValueError('temporary config path already exists: '+str(temp))
        mode=0o600
        if r['backup']: mode=stat.S_IMODE((self.state_dir/r['backup']).stat().st_mode)
        with temp.open('xb') as f: f.write(data)
        temp.chmod(mode); os.replace(temp,path); r.update(kind='file',installed=digest); self.save()

    def move(self,rel):
        path=self.path(rel)
        if not exists(path): return
        print('RETIRE '+str(path)); self.changed=True
        if self.dry: return
        self.backup(rel,'moved',None)

    def uninstall(self):
        for r in self.state['records']:
            path=self.path(r['path'])
            if not self.matches(path,r): raise ValueError('uninstall refuses modified item: '+r['path'])
            if r['backup'] and not exists(self.state_dir/r['backup']): raise ValueError('missing backup: '+r['backup'])
        for r in reversed(self.state['records'][:]):
            path=self.path(r['path']); print('RESTORE '+str(path)); self.changed=True
            if self.dry: continue
            if exists(path): path.unlink()  # verified owned symlinks/configs only, never recursive delete
            if r['backup']: os.rename(self.state_dir/r['backup'],path)
            self.state['records'].remove(r); self.save()
        if not self.dry:
            for rel in reversed(self.state['directories']):
                path=self.home/rel; no_symlink_parents(path,True)
                try: path.rmdir()
                except OSError: pass  # unknown user's files are preserved
            self.state['directories']=[]; self.save()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dry-run',action='store_true')
    parser.add_argument('--uninstall',action='store_true')
    parser.add_argument('--assets-only',action='store_true',help='explicit offline mode: no native plugin changes; not full setup')
    parser.add_argument('--validate',action='store_true',help='validate repository contract without HOME writes')
    args=parser.parse_args()
    manifest,lock,templates=load_contract(not args.uninstall)
    if args.validate:
        print('VALID: '+str(len(manifest['links']))+' item symlinks; JSON-compatible YAML; stdlib only'); return 0
    raw=os.environ.get('HOME')
    if not raw or not Path(raw).is_absolute(): raise ValueError('HOME must be an absolute existing directory')
    home=Path(raw); no_symlink_parents(home,True)
    home=home.resolve()  # only trusted OS aliases survived the check above
    if not home.is_dir(): raise ValueError('HOME must exist')
    # Lock the existing entrypoint read-only: no lockfile writes during preflight,
    # and install/uninstall share the same lock before reading the journal.
    import fcntl
    guard=(ROOT/'setup').open('rb')
    fcntl.flock(guard,fcntl.LOCK_EX|fcntl.LOCK_NB)
    engine=Installer(home,args.dry_run)
    # Validate every HOME destination and template/config before any changes.
    for entry in manifest['links']: engine.path('.'+entry['harness']+'/'+entry['destination'])
    from setup_plugins import NativePlugins
    native=NativePlugins(engine,ROOT,lock)
    if args.uninstall:
        native.uninstall(args.assets_only)
        engine.uninstall()
    else:
        pending=[]
        for target in ('claude','codex'):
            template=render(templates[target],home)
            rel='.'+target+('/settings.json' if target=='claude' else '/config.toml')
            path=engine.path(rel)
            if path.is_symlink() or (path.exists() and not path.is_file()): raise ValueError('config must be a regular file: '+str(path))
            text=path.read_text() if path.exists() else ''
            if target=='claude':
                old=json.loads(text) if text else {}
                if not isinstance(old,dict): raise ValueError('settings must be an object')
                if args.assets_only: template.pop('enabledPlugins',None)
                new=merge(old,template)
                data=path.read_bytes() if new==old and path.exists() else encode(new)
            else:
                if args.assets_only: template.pop('plugins',None)
                data=merge_toml(text,template).encode()
            pending.append((rel,data))
        native.preflight(args.assets_only)
        for entry in manifest['links']:
            engine.link('.'+entry['harness']+'/'+entry['destination'],source(entry['source']))
        for rel,data in pending: engine.write(rel,data)
        native.install(args.assets_only)
    if engine.changed:
        print('Backups/state: '+str(engine.state_dir))
        print('Restore: cd '+shlex.quote(str(ROOT))+' && ./setup --uninstall'+(' --assets-only' if args.assets_only else ''))
    return 0

if __name__=='__main__':
    try: sys.exit(main())
    except (ValueError,OSError,KeyError,TypeError) as exc:
        print('ERROR: '+str(exc),file=sys.stderr); sys.exit(2)
