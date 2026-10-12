"""Entry-scoped ownership for Claude's shared marketplace registry.

Only source identity and installLocation are expectations. Runtime metadata and
unrelated registrations are never used as permission to overwrite their bytes.
Legacy migration needs an exact historical SHA-256 witness, not just a parse.
"""
import copy
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat

REL = '.claude/plugins/known_marketplaces.json'
SOURCE_KEYS = ('source', 'path', 'url', 'repo', 'ref', 'sha', 'subdir')


def digest(data):
    return hashlib.sha256(data).hexdigest()


def parse(data):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result: raise ValueError('duplicate marketplace JSON key')
            result[key] = value
        return result
    value = json.loads(data, object_pairs_hook=pairs)
    if not isinstance(value, dict) or any(not isinstance(v, dict) for v in value.values()):
        raise ValueError('marketplace registry must contain entry objects')
    return value


def read(path):
    if path.is_symlink() or (path.exists() and not path.is_file()):
        raise ValueError('unsafe shared marketplace registry')
    return parse(path.read_bytes()) if path.exists() else {}


def identity(entry):
    if entry is None: return None
    result = {}
    if 'source' in entry:
        source = entry['source']
        if not isinstance(source, dict): raise ValueError('unknown marketplace source shape')
        result['source'] = {key: copy.deepcopy(source[key]) for key in SOURCE_KEYS if key in source}
    if 'installLocation' in entry:
        if not isinstance(entry['installLocation'], str): raise ValueError('unknown marketplace installLocation')
        result['installLocation'] = entry['installLocation']
    return result


def projection(data, names):
    return {name: identity(data.get(name)) for name in names}


def string_spans(text):
    """Locate string values by JSON path without changing formatting or ordering."""
    decoder = json.JSONDecoder(); spans = {}; i = 0
    def space():
        nonlocal i
        while i < len(text) and text[i].isspace(): i += 1
    def value(path):
        nonlocal i
        space(); start = i
        if text[i] == '{':
            i += 1; space()
            if text[i] == '}': i += 1; return
            while True:
                space(); key, end = decoder.raw_decode(text, i); i = end
                space(); assert text[i] == ':'; i += 1
                value(path+(key,)); space()
                char = text[i]; i += 1
                if char == '}': return
                assert char == ','
        elif text[i] == '[':
            i += 1; space(); index = 0
            if text[i] == ']': i += 1; return
            while True:
                value(path+(index,)); index += 1; space()
                char = text[i]; i += 1
                if char == ']': return
                assert char == ','
        else:
            item, i = decoder.raw_decode(text, i)
            if isinstance(item, str): spans[path] = (start, i)
    value(())
    return spans


def historical_witness(data, original, expected):
    parsed = parse(data)
    if digest(data) == expected: return parsed, []
    # Only values present in the original backup can be candidate timestamps.
    # No canonicalization, invented timestamps, or arbitrary value adoption.
    text = data.decode('utf-8'); spans = string_spans(text); changes = []
    for name, entry in original.items():
        old = entry.get('lastUpdated'); current = parsed.get(name, {}).get('lastUpdated')
        if not isinstance(old, str) or not isinstance(current, str) or old == current: continue
        start, end = spans[(name, 'lastUpdated')]
        changes.append((start, end, json.dumps(old), name))
    candidate = text
    for start, end, replacement, name in sorted(changes, reverse=True):
        candidate = candidate[:start]+replacement+candidate[end:]
    if digest(candidate.encode('utf-8')) != expected:
        raise ValueError('legacy marketplace journal lacks exact historical hash witness')
    return parse(candidate), [name+'.lastUpdated' for _, _, _, name in changes]


def backup_data(engine, record):
    from setup_symlinks import no_symlink_parents
    if not record.get('backup'): return {}
    backup = engine.state_dir / record['backup']; no_symlink_parents(backup)
    if backup.is_symlink() or not backup.is_file(): raise ValueError('missing/unsafe original marketplace backup')
    data = backup.read_bytes()
    if record.get('original_digest') and digest(data) != record['original_digest']:
        raise ValueError('original marketplace backup changed')
    return parse(data)


def migrate(engine, record):
    if record.get('marketplaces') or record['path'] != REL: return
    flags = engine.state['native'].get('claude')
    if not flags or flags.get('removed') or record.get('restoring'):
        # A generic Installer.write fixture is not evidence of native ownership.
        return
    if record['kind'] != 'file': raise ValueError('legacy marketplace journal cannot migrate this phase')
    original = backup_data(engine, record)
    path = engine.path(REL)
    if path.is_symlink() or not path.is_file(): raise ValueError('legacy marketplace registry missing/unsafe')
    installed, changed = historical_witness(path.read_bytes(), original, record['installed'])
    names = ['ssot-pinned']+list(flags.get('retired_marketplaces', []))
    if len(set(names)) != len(names) or any(not re.fullmatch(r'[a-z0-9._-]+',n) for n in names):
        raise ValueError('unsafe legacy marketplace ownership names')
    if flags.get('created_marketplace'):
        expected = {'source': {'source': 'directory', 'path': str(engine_root(engine))}, 'installLocation': str(engine_root(engine))}
        if 'ssot-pinned' in original or identity(installed.get('ssot-pinned')) != expected:
            raise ValueError('legacy pinned marketplace ownership cannot be proven')
    elif identity(installed.get('ssot-pinned')) != identity(original.get('ssot-pinned')):
        raise ValueError('legacy preexisting pinned marketplace changed')
    for name in names[1:]:
        if name not in original or name in installed: raise ValueError('legacy retired marketplace ownership cannot be proven')
    legacy = copy.deepcopy(record)
    record.update(kind='marketplaces', marketplaces=1, installed=projection(installed,names), original={n:copy.deepcopy(original.get(n)) for n in names}, legacy=legacy, witness={'sha256':legacy['installed'],'changed_paths':changed})
    record['original_digest'] = digest((engine.state_dir/record['backup']).read_bytes()) if record.get('backup') else None
    flags['marketplace_original'] = projection(original,names)
    engine.marketplace_migrated = True


def engine_root(engine):
    return Path(engine.state['repo'])/'dependencies/marketplaces/claude'


def capture(engine, retired, catalog, created):
    record = engine.record(REL)
    if record:
        if not record.get('marketplaces'): raise ValueError('unmigrated shared marketplace record')
        if record.get('pending') or record.get('rollback'): raise ValueError('marketplace rollback pending; resume --uninstall')
        if not set(retired).issubset(record['original']): raise ValueError('new retirement requires a separate ownership review')
        return record
    path = engine.path(REL); original = read(path)
    names = ['ssot-pinned']+list(retired)
    desired = projection(original,names)
    if created:
        if 'ssot-pinned' in original: raise ValueError('pinned marketplace name already occupied')
        desired['ssot-pinned'] = {'source': {'source':'directory','path':str(catalog)}, 'installLocation':str(catalog)}
    for name in retired:
        if name not in original: raise ValueError('retired marketplace missing from shared registry')
        desired[name] = None
    backup = None; original_digest = None
    if path.exists():
        backup = engine.next_backup()
        target = engine.state_dir/backup
        from setup_symlinks import no_symlink_parents
        no_symlink_parents(target)
        if target.exists() or target.is_symlink(): raise ValueError('refusing to overwrite marketplace backup')
        target.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
        shutil.copy2(path,target); original_digest = digest(target.read_bytes())
    record = dict(path=REL,kind='marketplaces',marketplaces=1,installed=desired,backup=backup,original={n:copy.deepcopy(original.get(n)) for n in names},original_digest=original_digest,pending=projection(original,names))
    engine.state['records'].append(record); engine.save()
    return record


def matches(engine, path, record):
    if record.get('marketplaces') != 1 or record['path'] != REL or record['kind'] != 'marketplaces':
        raise ValueError('unsafe marketplace record')
    original = backup_data(engine, record)
    if {n:original.get(n) for n in record['original']} != record['original']:
        raise ValueError('marketplace original entries differ from backup')
    data = read(path)
    if record.get('native_overlay'):
        overlay_entries(data,record['native_overlay'],record['installed'])
    observed = projection(data, record['installed'])
    allowed = [record['installed']]
    if record.get('rollback'): allowed.append(projection(record['original'],record['installed']))
    if record.get('rollback') and observed == allowed[-1]: return True
    if record.get('pending'):
        return all(observed[n] in [record['installed'][n],record['pending'][n]] for n in observed)
    return any(observed == expected for expected in allowed)


def finalize(engine):
    record = engine.record(REL)
    if not record or not record.get('marketplaces'): return
    if projection(read(engine.path(REL)),record['installed']) != record['installed']:
        raise ValueError('native marketplace semantic readback failed; rollback required')
    record.pop('pending',None); engine.save()


def overlay_entries(current, before, managed):
    """Native add/remove can drop unknown fields of unrelated entries.

    Restore missing metadata, not harness timestamps or a changed source. A
    durably saved pre-command snapshot is evidence, not a new ownership claim.
    """
    result=copy.deepcopy(current)
    for name,entry in before.items():
        if name in managed and managed[name] is None and name not in result: continue
        if name not in result: raise ValueError('native command removed unrelated marketplace; snapshot preserved')
        if name not in managed and identity(result[name])!=identity(entry):
            raise ValueError('native command changed unrelated marketplace source; snapshot preserved')
        for key,value in entry.items():
            if key in {'lastUpdated','autoUpdate'}: continue
            if key=='source' and isinstance(value,dict) and isinstance(result[name].get(key),dict):
                for field,item in value.items():
                    if field not in SOURCE_KEYS: result[name][key].setdefault(field,copy.deepcopy(item))
            elif key not in {'source','installLocation'}:
                result[name].setdefault(key,copy.deepcopy(value))
    return result


def replace_shared(engine,record,data,expected_bytes):
    path=engine.path(REL); temp=path.with_name(path.name+'.ssot-new')
    if temp.exists() or temp.is_symlink():
        known={record.get('write_pending'),record.get('overlay_write_pending')}
        if temp.is_symlink() or not temp.is_file() or digest(temp.read_bytes()) not in known:
            raise ValueError('unrecognized marketplace temporary file')
        temp.unlink()
    record['overlay_write_pending']=digest(data); engine.save()
    engine.restore_parent(path)
    mode=stat.S_IMODE(path.stat().st_mode) if path.exists() else 0o600
    with temp.open('xb') as stream:
        stream.write(data); stream.flush(); os.fsync(stream.fileno())
    temp.chmod(mode)
    latest=path.read_bytes() if path.exists() else None
    if latest!=expected_bytes: raise ValueError('marketplace changed concurrently; preserved current registry')
    os.replace(temp,path)


def recover_overlay(engine,record):
    if 'native_overlay' not in record: return
    path=engine.path(REL); before=path.read_bytes() if path.exists() else None
    current=read(path); result=overlay_entries(current,record['native_overlay'],record['installed'])
    if result!=current:
        from setup_symlinks import encode
        replace_shared(engine,record,encode(result),before)
    record.pop('native_overlay',None); record.pop('overlay_write_pending',None); engine.save()


def restore(engine, record):
    path = engine.path(REL)
    if not matches(engine,path,record): raise ValueError('shared marketplace changed before rollback')
    recover_overlay(engine,record)
    current_bytes = path.read_bytes() if path.exists() else None
    current = read(path); restored = copy.deepcopy(current)
    for name, original in record['original'].items():
        if original is None:
            # Removing the setup-created registration removes its runtime fields
            # too. Archive the observed entry in the journal before removal.
            if name in restored:
                record.setdefault('removed_entries',{})[name] = copy.deepcopy(restored[name])
                del restored[name]
        elif name not in restored:
            restored[name] = copy.deepcopy(original)
        else:
            entry = restored[name]
            for key in ('source','installLocation'):
                if key == 'source' and key in entry and key in original:
                    for field in SOURCE_KEYS:
                        if field in original[key]: entry[key][field] = copy.deepcopy(original[key][field])
                        else: entry[key].pop(field,None)
                elif key in original: entry[key] = copy.deepcopy(original[key])
                else: entry.pop(key,None)
    record['rollback'] = True; engine.save()
    if restored != current:
        from setup_symlinks import encode
        data = encode(restored); temp = path.with_name(path.name+'.ssot-new')
        if temp.exists() or temp.is_symlink():
            if temp.is_symlink() or not temp.is_file() or digest(temp.read_bytes()) not in {record.get('write_pending'),record.get('overlay_write_pending')}:
                raise ValueError('unrecognized marketplace temporary file')
            temp.unlink()
        record['write_pending'] = digest(data); engine.save()
        engine.restore_parent(path)
        mode = stat.S_IMODE(path.stat().st_mode) if path.exists() else 0o600
        with temp.open('xb') as stream:
            stream.write(data); stream.flush(); os.fsync(stream.fileno())
        temp.chmod(mode)
        # Detect external writer drift immediately before replacing. The native
        # harness does not honor setup's flock; there remains a narrow race.
        latest = path.read_bytes() if path.exists() else None
        if latest != current_bytes: raise ValueError('marketplace changed concurrently; preserved current registry')
        os.replace(temp,path)
    if projection(read(path),record['original']) != projection(record['original'],record['original']):
        raise ValueError('marketplace rollback readback failed')
    # Keep original backup and removed-entry archive for audit, not blind restore.
    if record.get('removed_entries'):
        engine.state.setdefault('marketplace_archive',[]).append(record['removed_entries'])
    engine.state.setdefault('marketplace_journal_archive',[]).append(copy.deepcopy(record))
    engine.state['records'].remove(record); engine.save()
