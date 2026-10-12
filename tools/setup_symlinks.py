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
import unicodedata

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

# Execution state is opaque, never a selectable manifest asset. Bytecode is
# allowed only in the enumerated engine packages, not arbitrary PRIVATE paths.
LOCAL_RUNTIME = 'sources/skills/paper-banana/engine/.venv'
BYTECODE_PACKAGES = ('mcp_server', 'paperbanana', 'paperbanana/agents',
    'paperbanana/data', 'paperbanana/evaluation', 'paperbanana/guidelines',
    'paperbanana/providers', 'paperbanana/providers/image_gen',
    'paperbanana/providers/vlm', 'paperbanana/reference', 'paperbanana/core')
LOCAL_RUNTIMES = {LOCAL_RUNTIME} | {
    'sources/skills/paper-banana/engine/'+p+'/__pycache__'
    for p in BYTECODE_PACKAGES}

def local_runtime(path):
    rel = str(path.relative_to(ROOT))
    if rel not in LOCAL_RUNTIMES: return False
    no_symlink_parents(path, True)
    if not path.is_dir(): raise ValueError('runtime boundary must be a real directory')
    # Inspect the index/ignore rule, never the runtime payload. A forced git add
    # must not turn the local exception into a distributable source exception.
    import subprocess
    env = dict(os.environ, GIT_OPTIONAL_LOCKS='0')
    tracked = subprocess.run(['git','ls-files','--',rel], cwd=ROOT, env=env, capture_output=True)
    ignored = subprocess.run(['git','check-ignore','-q','--',rel+'/'], cwd=ROOT, env=env, capture_output=True)
    if tracked.returncode or tracked.stdout or ignored.returncode:
        raise ValueError('local runtime must be ignored and untracked: '+rel)
    return True

def source(value):
    p = ROOT / str(relative(value))
    no_symlink_parents(p)
    if p.is_symlink() or not p.exists():
        raise ValueError('missing or symlink source: '+str(p))
    def entries():
        yield p
        if p.is_dir():
            def walk_error(error): raise error
            for base, dirs, files in os.walk(p, followlinks=False, onerror=walk_error):
                for name in dirs[:]:
                    q = Path(base)/name
                    if local_runtime(q):
                        dirs.remove(name)
                    else: yield q
                for name in files: yield Path(base)/name
    for q in entries():
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
    seen=set(); agent_names=set(); command_names=set()
    for entry in manifest['links']:
        validate_destination(entry['harness'],entry['destination'])
        # Portable fail-closed policy: reject aliases even on case-sensitive disks.
        # No filesystem probe is needed, so a bad contract makes zero HOME writes.
        normalized=unicodedata.normalize('NFD',entry['destination']).casefold()
        key=(entry['harness'],normalized)
        if key in seen: raise ValueError('duplicate destination (case/Unicode alias): '+str(key))
        destination=PurePosixPath(entry['destination'])
        normalized_path=PurePosixPath(normalized)
        for harness,other in seen:
            if harness==entry['harness'] and (PurePosixPath(other) in normalized_path.parents or normalized_path in PurePosixPath(other).parents):
                raise ValueError('overlapping item destinations: '+entry['destination'])
        seen.add(key)
        if check_sources:
            entrypoint=source(entry['source'])
            category=destination.parts[0]
            if category=='skills' and (not entrypoint.is_dir() or not (entrypoint/'SKILL.md').is_file()):
                raise ValueError('skill requires a directory containing SKILL.md: '+entry['source'])
            if category in {'agents','commands','prompts','CLAUDE.md','AGENTS.md'} and not entrypoint.is_file():
                raise ValueError('native file entrypoint cannot be a directory: '+entry['destination'])
            if entry['harness']=='claude' and category in {'skills','commands'}:
                # Skills and slash-command wrappers share Claude's command namespace.
                # Use the skill frontmatter name (not only its directory name).
                name=destination.name if category=='skills' else destination.stem
                if category=='skills':
                    text=(entrypoint/'SKILL.md').read_text()
                    if text.startswith('---\n'):
                        names=re.findall(r'^name:[ \t]*(.*?)[ \t]*$',text.split('---',2)[1],re.M)
                        if len(names)>1: raise ValueError('Claude skill requires at most one native name')
                        if names:
                            name=names[0]
                            if name.startswith('"'): name=json.loads(name)
                            elif name.startswith("'") and name.endswith("'"): name=name[1:-1].replace("''", "'")
                if not isinstance(name,str) or not name or any(c in name for c in '/\\\r\n\t '): raise ValueError('unsafe Claude native command name')
                key=unicodedata.normalize('NFD',name).casefold()
                if key in command_names: raise ValueError('duplicate Claude skill/command native namespace: '+name)
                command_names.add(key)
            if category=='agents' and entry['harness']=='claude':
                text=entrypoint.read_text()
                if not text.startswith('---\n'): raise ValueError('Claude agent requires frontmatter')
                names=re.findall(r'^name:\s*(.*?)\s*$',text.split('---',2)[1],re.M)
                if len(names)!=1: raise ValueError('Claude agent requires one native name')
                name=json.loads(names[0])  # approved originals use JSON-quoted YAML scalars
                if not isinstance(name,str) or not re.fullmatch(r'[a-z0-9-]+',name): raise ValueError('unsafe Claude native name')
                if name in agent_names: raise ValueError('duplicate Claude native name: '+name)
                if entry.get('native_name',name)!=name: raise ValueError('manifest/native agent name mismatch')
                agent_names.add(name)
        else: relative(entry['source'])
    lock=json.loads(source(manifest['dependencies']).read_text())
    for entry in manifest.get('retired_links',[]):
        validate_destination(entry['harness'],entry['destination'])
        key=(entry['harness'],unicodedata.normalize('NFD',entry['destination']).casefold())
        if key in seen: raise ValueError('retired destination still active')
        if not source(entry['source']).is_file(): raise ValueError('retired alias requires approved original')
        if not any(e['harness']==entry['harness'] and e['destination']==entry['canonical'] for e in manifest['links']): raise ValueError('retired alias has no canonical definition')
        for approved in entry.get('approved_link_sources',[]): source(approved)
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

KEY_TOKEN=r'"(?:[^"\\]|\\.)*"|\x27[^\x27]*\x27|[A-Za-z0-9_-]+'
KEY_PATH=r'(?:'+KEY_TOKEN+r')(?:\s*\.\s*(?:'+KEY_TOKEN+r'))*'

def split_keys(value):
    if not re.fullmatch(r'\s*'+KEY_PATH+r'\s*',value):
        raise ValueError('unsupported TOML key: '+value)
    tokens=re.findall(KEY_TOKEN,value)
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

def validate_managed_toml(text, desired, tomllib):
    """Check effective managed values, not merely syntactically valid output."""
    if tomllib:
        parsed=tomllib.loads(text)
        for (table,key),value in desired.items():
            node=parsed
            for part in table:
                node=node.get(part,{}) if isinstance(node,dict) else {}
            if not isinstance(node,dict) or key not in node or node[key]!=value:
                raise ValueError('managed TOML value readback failed: '+'.'.join(table+(key,)))
        return
    # Python 3.9: read back the supported explicit table/scalar subset only.
    actual={}; table=(); multiline=None
    for line in text.splitlines():
        inside_multiline=multiline is not None
        multiline=toml_multiline_state(line,multiline)
        if inside_multiline: continue
        array_header=re.match(r'^\s*\[\[(.*?)\]\]\s*(?:#.*)?$',line)
        if array_header:
            table=tuple(split_keys(array_header[1])); continue
        header=re.match(r'^\s*\[(.*?)\]\s*(?:#.*)?$',line)
        if header:
            table=tuple(split_keys(header[1])); continue
        assignment=re.match(r'^\s*('+KEY_PATH+r')\s*=\s*(.*)',line)
        if not assignment: continue
        keys=split_keys(assignment[1])
        coordinate=(table,keys[0])
        if len(keys)==1 and coordinate in desired:
            if coordinate in actual: raise ValueError('duplicate managed TOML value')
            actual[coordinate]=scalar_from_toml(assignment[2])
    if actual!=desired: raise ValueError('managed TOML value readback failed')


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
    coordinates=[tab+(key,) for tab,key in desired]
    def touches_managed(path):
        return any(path[:len(c)]==c or c[:len(path)]==path for c in coordinates)
    lines=text.splitlines(keepends=True); table=(); found=set(); tables={():0}; insertions={}; multiline=None
    for i,line in enumerate(lines):
        inside_multiline=multiline is not None
        multiline=toml_multiline_state(line,multiline)
        if inside_multiline: continue
        array_header=re.match(r'^\s*\[\[(.*?)\]\]\s*(?:#.*)?$',line)
        if array_header:
            table=tuple(split_keys(array_header[1]))
            if touches_managed(table): raise ValueError('managed TOML array table requires manual review')
            continue
        header=re.match(r'^\s*\[(.*?)\]\s*(?:#.*)?$',line)
        if header:
            table=tuple(split_keys(header[1])); tables[table]=i+1
            if any(table[:len(c)]==c for c in coordinates):
                raise ValueError('managed TOML scalar declared as table requires manual review')
        assignment=re.match(r'^\s*('+KEY_PATH+r')\s*=\s*(.*)',line)
        if assignment:
            keys=split_keys(assignment[1]); path=table+tuple(keys)
            if touches_managed(path) and (len(keys)>1 or any(c[:len(path)]==path and c!=path for c in coordinates)):
                raise ValueError('managed dotted/inline TOML assignment requires manual review: '+assignment[1])
            key=keys[0]; coordinate=(table,key)
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
    for index in sorted(insertions,reverse=True):
        rows=insertions[index]
        # A final header/comment may not end in a newline. Never concatenate
        # the new assignment onto that statement (or bury it in its comment).
        if index and not lines[index-1].endswith('\n'): rows=['\n']+rows
        lines[index:index]=rows
    result=''.join(lines)
    validate_managed_toml(result,desired,tomllib)
    return result

class Installer:
    def __init__(self,home,dry=False):
        self.home=home; self.dry=dry; self.state_dir=home/'.agent-skills-setup'
        no_symlink_parents(self.state_dir,True)
        self.state_path=self.state_dir/'state.json'
        if self.state_path.is_symlink(): raise ValueError('symlink state')
        self.state=json.loads(self.state_path.read_text()) if self.state_path.exists() else {'version':1,'repo':str(ROOT),'records':[],'directories':[],'native':{}}
        if self.state.get('repo')!=str(ROOT) or self.state.get('version')!=1: raise ValueError('state belongs to another repo/version')
        self.marketplace_migrated=False
        for r in self.state['records']:
            path = self.path(r['path'])
            if r.get('backup') and not re.fullmatch(r'backups/[0-9]+',r['backup']): raise ValueError('unsafe state backup')
            if r.get('backup'): no_symlink_parents(self.state_dir/r['backup'])
            from setup_marketplaces import migrate
            migrate(self,r)
            if not self.matches(path,r): raise ValueError('managed item changed by user: '+r['path'])
        for rel in self.state['directories']:
            p = PurePosixPath(rel)
            if not p.parts or p.parts[0] not in {'.claude','.codex'} or '..' in p.parts or p.is_absolute(): raise ValueError('unsafe state directory')
            no_symlink_parents(self.home/rel,True)
        self.changed=False

    def path(self, rel):
        p=PurePosixPath(rel)
        cache_retirement = bool(re.fullmatch(r'\.(claude|codex)/plugins/cache/[a-z0-9._-]+/(superpowers|bagjuhyeon-agent-ssot)', rel))
        market_retirement = bool(re.fullmatch(r'\.(claude|codex)/plugins/marketplaces/[a-z0-9._-]+', rel))
        forbidden = blocked('/'.join(p.parts[1:])) and not cache_retirement
        if p.is_absolute() or '..' in p.parts or str(p)!=rel or p.parts[0] not in {'.claude','.codex'} or forbidden:
            raise ValueError('unsafe state destination: '+rel)
        if not cache_retirement and not market_retirement and rel not in {'.claude/settings.json','.codex/config.toml','.claude/plugins/installed_plugins.json','.claude/plugins/known_marketplaces.json'}:
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

    def next_backup(self):
        # Shared-registry audit backups survive rollback; never reuse their slot.
        index=len(self.state['records'])
        while exists(self.state_dir/('backups/'+str(index))): index+=1
        return 'backups/'+str(index)

    def backup(self,rel,kind,installed,cache_selector=None):
        path=self.path(rel)
        old=self.record(rel)
        if old:
            if not self.matches(path,old): raise ValueError('managed item changed by user: '+rel)
            return old
        r={'path':rel,'kind':kind,'installed':installed,'backup':None}
        if cache_selector is not None: r['retired_cache']=cache_selector
        if exists(path):
            if path.is_symlink() and kind=='file': raise ValueError('config symlink refused: '+rel)
            if kind=='file' and not path.is_file(): raise ValueError('config is not a regular file: '+rel)
            r['backup']=self.next_backup()
        self.state['records'].append(r); self.save()
        if r['backup']:
            b=self.state_dir/r['backup']; no_symlink_parents(b)
            if exists(b): raise ValueError('refusing to overwrite existing backup: '+str(b))
            b.parent.mkdir(mode=0o700,exist_ok=True); os.rename(path,b)
            print('BACKUP '+str(path)+' -> '+str(b))
        return r

    def matches(self,path,record):
        if record.get('marketplaces'):
            from setup_marketplaces import matches
            return matches(self,path,record)
        if record.get('restoring'):
            backup=self.state_dir/record['backup']
            if not exists(backup): return exists(path) and self.restore_identity(path)==record['restoring']
            if not exists(path): return self.restore_identity(backup)==record['restoring']
        if record['kind']=='link': return path.is_symlink() and os.readlink(path)==record['installed']
        if record['kind']=='moved':
            if record.get('retired_cache'):
                self.cache_retirement(record)
                backup=self.state_dir/record['backup'] if record.get('backup') else None
                if not backup or not exists(backup): raise ValueError('missing original cache backup')
                no_symlink_parents(backup,True)
                if record.get('quarantining'):
                    pending=record['quarantining']; destination=self.quarantine_path(pending['path'])
                    present=path if exists(path) else destination
                    if exists(path) and exists(destination): return False
                    return exists(present) and self.restore_identity(present)==pending['identity']
                if exists(path): self.regenerated_cache(path,record)
                return True
            return not exists(path)
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

    def move(self,rel,cache_selector=None):
        path=self.path(rel)
        if not exists(path): return
        old=self.record(rel)
        if old and old.get('retired_cache'):
            self.quarantine_caches(); return
        print('RETIRE '+str(path)); self.changed=True
        if self.dry: return
        if old:
            if old['kind']!='link' or not self.matches(path,old): raise ValueError('refusing to retire modified/non-link managed item: '+rel)
            path.unlink(); old.update(kind='moved',installed=None); self.save()
        else:
            if cache_selector is not None:
                self.cache_retirement({'path':rel,'retired_cache':cache_selector,'kind':'moved','installed':None})
                no_symlink_parents(path,True)
            self.backup(rel,'moved',None,cache_selector)

    def cache_retirement(self,record):
        selector=record['retired_cache']
        if not isinstance(selector,str) or not re.fullmatch(r'[a-z0-9._-]+@[a-z0-9._-]+',selector):
            raise ValueError('unsafe retired cache selector')
        plugin,market=selector.split('@')
        harness=PurePosixPath(record['path']).parts[0]
        if (plugin not in {'superpowers','bagjuhyeon-agent-ssot'} or market=='ssot-pinned' or
                (plugin=='bagjuhyeon-agent-ssot' and market!='generated-local-cache') or
                harness not in {'.claude','.codex'} or
                record['path']!=harness+'/plugins/cache/'+market+'/'+plugin or
                record['kind']!='moved' or record['installed'] is not None):
            raise ValueError('retired cache selector/path mismatch')

    def regenerated_cache(self,path,record):
        self.cache_retirement(record)
        no_symlink_parents(path,True)
        plugin=record['retired_cache'].split('@')[0]
        metadata='.claude-plugin' if record['path'].startswith('.claude/') else '.codex-plugin'
        children=list(path.iterdir())
        if not children: raise ValueError('unrecognized regenerated cache: '+record['path'])
        for child in children:
            if not re.fullmatch(r'[a-zA-Z0-9._-]+',child.name): raise ValueError('unsafe regenerated cache revision')
            manifest=child/metadata/'plugin.json'; no_symlink_parents(manifest)
            if manifest.is_symlink() or not manifest.is_file(): raise ValueError('unrecognized regenerated cache manifest')
            payload=json.loads(manifest.read_text())
            if not isinstance(payload,dict) or payload.get('name')!=plugin or not isinstance(payload.get('version'),str) or not payload['version']:
                raise ValueError('regenerated cache plugin mismatch')
        # Only plugin metadata is inspected. All payload, including user edits,
        # is preserved by rename, never merged with or restored over the backup.

    def quarantine_path(self,rel):
        if not isinstance(rel,str) or not re.fullmatch(r'quarantine/[0-9]+',rel): raise ValueError('unsafe quarantine path')
        path=self.state_dir/rel; no_symlink_parents(path,True)
        return path

    def quarantine_caches(self):
        for record in self.state['records']:
            if not record.get('retired_cache') or record.get('restoring'): continue
            path=self.path(record['path'])
            if not self.matches(path,record): raise ValueError('retired cache changed during quarantine')
            pending=record.get('quarantining')
            if not pending and not exists(path): continue
            print('QUARANTINE '+str(path)); self.changed=True
            if self.dry: continue
            if not pending:
                rel='quarantine/'+str(len(self.state.get('quarantine',[])))
                destination=self.quarantine_path(rel)
                if exists(destination): raise ValueError('native orphan backup already exists')
                pending={'path':rel,'identity':self.restore_identity(path)}
                record['quarantining']=pending
                self.state.setdefault('quarantine',[]).append(rel); self.save()
            destination=self.quarantine_path(pending['path'])
            if exists(path):
                if exists(destination): raise ValueError('refusing to overwrite quarantine')
                destination.parent.mkdir(mode=0o700,exist_ok=True)
                os.rename(path,destination)
            del record['quarantining']; self.save()

    def restore_identity(self,path):
        s=path.lstat()
        return [s.st_dev,s.st_ino,s.st_mode,s.st_size,s.st_mtime_ns]

    def restore_parent(self,path):
        # Recreate only ancestors of a verified journal destination. Unlike
        # mkdir(), these are original parents and are not installer-owned.
        no_symlink_parents(path)
        if path.parent==self.home or path.parent.exists(): return
        self.restore_parent(path.parent)
        no_symlink_parents(path)
        path.parent.mkdir()

    def uninstall(self):
        for r in self.state['records']:
            path=self.path(r['path'])
            if not self.matches(path,r): raise ValueError('uninstall refuses modified item: '+r['path'])
            if r['backup'] and not exists(self.state_dir/r['backup']) and not r.get('restoring'): raise ValueError('missing backup: '+r['backup'])
        self.quarantine_caches()
        for r in reversed(self.state['records'][:]):
            path=self.path(r['path']); print('RESTORE '+str(path)); self.changed=True
            if self.dry: continue
            if r.get('marketplaces'):
                from setup_marketplaces import restore
                restore(self,r); continue
            backup=self.state_dir/r['backup'] if r['backup'] else None
            if backup and not exists(backup) and r.get('restoring'):
                # Rename completed before the journal checkpoint. The inode
                # identity was checked at preflight; do not unlink the original.
                self.state['records'].remove(r); self.save(); continue
            if backup:
                self.restore_parent(path)
                r['restoring']=self.restore_identity(backup); self.save()
            if exists(path): path.unlink()  # verified owned symlinks/configs only, never recursive delete
            if backup: os.rename(backup,path)
            self.state['records'].remove(r); self.save()
        if not self.dry and self.state['directories']:
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
    if not args.uninstall and (any(f.get('removed') for f in engine.state['native'].values()) or any(r.get('pending') or r.get('rollback') or r.get('native_overlay') for r in engine.state['records'] if r.get('marketplaces'))):
        raise ValueError('rollback is pending; resume with --uninstall before setup')
    # Validate every HOME destination and template/config before any changes.
    for entry in manifest['links']: engine.path('.'+entry['harness']+'/'+entry['destination'])
    retirees=[]
    if not args.uninstall:
        for entry in manifest.get('retired_links',[]):
            rel='.'+entry['harness']+'/'+entry['destination']; path=engine.path(rel)
            if exists(path):
                approved=source(entry['source'])
                allowed_links=[source(s) for s in entry.get('approved_link_sources',[entry['source']])]
                if (not path.is_file() or path.read_bytes()!=approved.read_bytes() or
                        (path.is_symlink() and 'approved_link_sources' in entry and path.resolve() not in allowed_links)):
                    raise ValueError('retired alias differs from approved original; review locally before setup: '+rel)
                retirees.append(rel)
    from setup_plugins import NativePlugins
    native=NativePlugins(engine,ROOT,lock)
    if args.uninstall:
        if engine.marketplace_migrated: engine.save()
        native.uninstall(args.assets_only)
        engine.uninstall()
        native.verify_restored()
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
        if engine.marketplace_migrated: engine.save()
        engine.quarantine_caches()
        for rel in retirees: engine.move(rel)
        for entry in manifest['links']:
            engine.link('.'+entry['harness']+'/'+entry['destination'],source(entry['source']))
        for rel,data in pending: engine.write(rel,data)
        native.install(args.assets_only)
        engine.quarantine_caches()
    if engine.changed:
        print('Backups/state: '+str(engine.state_dir))
        print('Restore: cd '+shlex.quote(str(ROOT))+' && ./setup --uninstall'+(' --assets-only' if args.assets_only else ''))
    return 0

if __name__=='__main__':
    try: sys.exit(main())
    except (ValueError,OSError,KeyError,TypeError) as exc:
        print('ERROR: '+str(exc),file=sys.stderr); sys.exit(2)
