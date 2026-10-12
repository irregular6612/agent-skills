"""Native plugin operations; pinned metadata catalogs, never vendored payloads."""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess

REGISTRY={
    'claude':['.claude/settings.json','.claude/plugins/installed_plugins.json','.claude/plugins/known_marketplaces.json'],
    'codex':['.codex/config.toml'],
}
class NativePlugins:
    def __init__(self,engine,root,lock):
        self.e=engine; self.root=root; self.spec={}; self.before={}; self.restore_markets={}
        deps=lock['dependencies']
        if len(deps)!=1 or deps[0]['id']!='superpowers': raise ValueError('exactly one superpowers dependency required')
        d=deps[0]
        if d['repository']!='https://github.com/obra/superpowers.git': raise ValueError('unapproved upstream')
        for target in ('claude','codex'):
            g=d['harness_install'][target]
            if g['mode']!='native-cli' or g['marketplace']!='ssot-pinned' or g['executable']!=target: raise ValueError('unsupported native adapter')
            if not re.fullmatch(r'[0-9a-f]{40}',d['commits'][target]): raise ValueError('non-immutable plugin lock')
            catalog=root/'dependencies/marketplaces'/target
            filename='.claude-plugin/marketplace.json' if target=='claude' else '.agents/plugins/marketplace.json'
            from setup_symlinks import source
            catalog_file=source(str((catalog/filename).relative_to(root)))
            payload=json.loads(catalog_file.read_text())
            item=payload['plugins'][0]
            if len(payload['plugins'])!=1 or payload['name']!=g['marketplace'] or item['name']!='superpowers' or item['source']!={'source':'url','url':d['repository'],'sha':d['commits'][target]} or item['version']!=d['refs'][target].lstrip('v'):
                raise ValueError('catalog differs from immutable lock')
            self.spec[target]={'id':'superpowers@ssot-pinned','catalog':catalog,'version':d['refs'][target].lstrip('v'),'commit':d['commits'][target],'repository':d['repository']}
    def run(self,target,args,cwd=None):
        env=dict(os.environ,HOME=str(self.e.home),CLAUDE_CONFIG_DIR=str(self.e.home/'.claude'),CODEX_HOME=str(self.e.home/'.codex'))
        result=subprocess.run([target]+args,cwd=cwd or self.root,env=env,text=True,capture_output=True,timeout=180)
        if result.returncode: raise ValueError('native command failed (exit '+str(result.returncode)+'): '+target+' '+' '.join(args)+'; '+result.stderr[:400])
        try: return json.loads(result.stdout)
        except json.JSONDecodeError: raise ValueError('native command did not return JSON: '+target)
    def plugins(self,target):
        data=self.run(target,['plugin','list','--json'])
        records=data if target=='claude' else data.get('installed')
        if not isinstance(records,list): raise ValueError('unknown native plugin list shape')
        for r in records:
            r['_id']=r.get('id') if target=='claude' else r.get('pluginId')
            if not isinstance(r['_id'],str): raise ValueError('unknown native plugin id')
        return records
    def marketplaces(self,target):
        data=self.run(target,['plugin','marketplace','list','--json'])
        if isinstance(data,dict): data=data.get('marketplaces')
        if not isinstance(data,list): raise ValueError('unknown marketplace list shape')
        return data
    def preflight(self,skip):
        if skip: return
        for target,spec in self.spec.items():
            if not shutil.which(target): raise ValueError('native CLI missing: '+target+' (use --assets-only only for explicit offline asset tests)')
            for rel in REGISTRY[target]:
                p=self.e.path(rel)
                if p.is_symlink() or (p.exists() and not p.is_file()): raise ValueError('unsafe native registry: '+rel)
            # Dry run does not invoke native CLIs, which can populate caches on read.
            if self.e.dry: continue
            harness_root = self.e.home/('.'+target)
            if not harness_root.exists():
                print('MKDIR '+str(harness_root)); self.e.changed=True
                self.e.mkdir(harness_root)
            self.before[target]=self.plugins(target)
            for r in self.retired(target,self.before[target]):
                self.cache_path(target,r)  # fail before any writes for unexpected paths
            for r in self.marketplaces(target):
                if r.get('name')=='ssot-pinned':
                    location=r.get('installLocation') or r.get('path') or r.get('root') or r.get('source_path')
                    if not location and isinstance(r.get('marketplaceSource'),dict): location=r['marketplaceSource'].get('source')
                    # Existing marketplace must still reference this repo's metadata.
                    if not location or Path(location).resolve()!=spec['catalog'].resolve(): raise ValueError('pinned marketplace points elsewhere: '+str(location))
    def retired(self,target,records):
        selector=self.spec[target]['id']
        return [r for r in records if (r['_id'].split('@')[0]=='superpowers' and r['_id']!=selector) or r['_id']=='bagjuhyeon-agent-ssot@generated-local-cache']
    def obsolete_markets(self,target,records,markets):
        """Only dedicated catalogs of retired plugins, never mixed marketplaces."""
        result=[]
        for market in markets:
            name=market.get('name')
            if name=='ssot-pinned': continue
            if not isinstance(name,str) or not re.fullmatch(r'[a-z0-9._-]+',name): continue  # unknown names stay untouched
            if any(r['_id'].endswith('@'+name) and r not in self.retired(target,records) for r in records): continue
            location=market.get('installLocation') or market.get('root') or market.get('path')
            if not location: continue  # unknown catalog ownership: preserve
            catalog=Path(location)
            filename='.claude-plugin/marketplace.json' if target=='claude' else '.agents/plugins/marketplace.json'
            path=catalog/filename
            from setup_symlinks import no_symlink_parents
            no_symlink_parents(path)
            if path.is_symlink() or not path.is_file(): continue
            payload=json.loads(path.read_text())
            plugins=payload.get('plugins',[])
            if not plugins or any(p.get('name') not in {'superpowers','bagjuhyeon-agent-ssot'} for p in plugins): continue
            result.append(name)
        return result
    def remove_market(self,target,name):
        self.run(target,['plugin','marketplace','remove',name,'--json']+(['--scope','user'] if target=='claude' else []))
        if any(r.get('name')==name for r in self.marketplaces(target)): raise ValueError('marketplace removal readback failed: '+name)
    def cache_path(self,target,record):
        selector=record['_id']
        if not re.fullmatch(r'[a-z0-9._-]+@[a-z0-9._-]+',selector): raise ValueError('unsafe plugin selector')
        plugin,market=selector.split('@')
        # Do not follow arbitrary CLI-provided install paths outside the native cache.
        expected=self.e.home/('.'+target)/'plugins/cache'/market/plugin
        location=record.get('installPath')
        if location:
            p=Path(location)
            if not p.is_absolute() or '..' in p.parts or expected not in p.parents: raise ValueError('unexpected plugin cache path: '+location)
        self.e.path(str(expected.relative_to(self.e.home)))
        from setup_symlinks import no_symlink_parents
        no_symlink_parents(expected,True)
        return expected
    def capture_registries(self,target):
        from setup_symlinks import exists
        for rel in REGISTRY[target]:
            path=self.e.path(rel)
            if self.e.record(rel): continue
            data=path.read_bytes() if path.exists() else None
            r=self.e.backup(rel,'file',hashlib.sha256(data).hexdigest() if data is not None else None)
            if data is not None:
                shutil.copy2(self.e.state_dir/r['backup'],path)
    def update_registry_hashes(self,target):
        for rel in REGISTRY[target]:
            path=self.e.path(rel); r=self.e.record(rel)
            if r:
                if path.is_symlink(): raise ValueError('native CLI created registry symlink')
                r['installed']=hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None
                if not path.exists(): r['kind']='moved'
        self.e.save()
    def remove(self,target,selector):
        args=['plugin','uninstall',selector,'--scope','user','--json'] if target=='claude' else ['plugin','remove',selector,'--json']
        self.run(target,args)
        if any(r['_id']==selector for r in self.plugins(target)): raise ValueError('plugin removal readback failed: '+selector)
    def exact(self,target,records):
        spec=self.spec[target]; matches=[r for r in records if r['_id'].split('@')[0]=='superpowers']
        valid=len(matches)==1 and matches[0]['_id']==spec['id'] and matches[0].get('version')==spec['version'] and matches[0].get('enabled') is True
        if valid and target=='codex' and not self.e.dry:
            upstream=matches[0].get('source',{})
            valid=upstream.get('sha')==spec['commit'] and upstream.get('url')==spec['repository']
        return valid
    def local_plugins(self,target):
        """Read metadata only, avoiding native CLI cache/bootstrap writes in dry-run."""
        spec=self.spec[target]
        if target=='claude':
            p=self.e.path('.claude/plugins/installed_plugins.json')
            if not p.exists(): return []
            data=json.loads(p.read_text())
            settings=self.e.path('.claude/settings.json')
            enabled=json.loads(settings.read_text()).get('enabledPlugins',{}) if settings.exists() else {}
            records=[]
            for selector,items in data.get('plugins',{}).items():
                for item in items:
                    if item.get('scope','user')!='user': continue
                    records.append({'_id':selector,'version':item.get('version'),'enabled':enabled.get(selector,False)})
            return records
        data=self.local_codex_config()
        records=[]
        for selector,details in data.get('plugins',{}).items():
            if '@' not in selector: continue
            plugin,market=selector.split('@',1)
            if not re.fullmatch(r'[a-z0-9._-]+',market): raise ValueError('unsafe plugin marketplace')
            if plugin!='superpowers':
                records.append({'_id':selector,'enabled':details.get('enabled',False)})
                continue
            cache=self.e.home/'.codex/plugins/cache'/market/plugin
            from setup_symlinks import no_symlink_parents
            no_symlink_parents(cache,True)
            manifests=list(cache.glob('*/.codex-plugin/plugin.json')) if cache.exists() else []
            for manifest in manifests:
                no_symlink_parents(manifest)
                if manifest.is_symlink(): raise ValueError('symlink native plugin manifest')
                item=json.loads(manifest.read_text())
                records.append({'_id':selector,'version':item.get('version'),'enabled':details.get('enabled',False)})
        return records
    def local_codex_config(self):
        config=self.e.path('.codex/config.toml')
        if not config.exists(): return {}
        try:
            import tomllib
        except ImportError:
            from setup_symlinks import split_keys,toml_multiline_state,scalar_from_toml
            data={'plugins':{},'marketplaces':{}}; table=(); multiline=None
            for line in config.read_text().splitlines():
                inside=multiline is not None; multiline=toml_multiline_state(line,multiline)
                if inside: continue
                header=re.match(r'^\s*\[([^\[\]]+)\]\s*(?:#.*)?$',line)
                if header: table=tuple(split_keys(header[1])); continue
                assignment=re.match(r'^\s*("(?:[^"\\]|\\.)*"|\x27[^\x27]*\x27|[A-Za-z0-9_-]+)\s*=\s*(.*)',line)
                if len(table)==2 and table[0] in data and assignment:
                    key=split_keys(assignment[1])[0]
                    if key in {'enabled','source','source_type'}:
                        data[table[0]].setdefault(table[1],{})[key]=scalar_from_toml(assignment[2])
        else:
            data=tomllib.loads(config.read_text())
        return data
    def local_marketplaces(self,target):
        if target=='claude':
            path=self.e.path('.claude/plugins/known_marketplaces.json')
            data=json.loads(path.read_text()) if path.exists() else {}
            return [dict(value,name=name) for name,value in data.items()]
        return [{'name':name,'root':value.get('source')} for name,value in self.local_codex_config().get('marketplaces',{}).items() if value.get('source_type')=='local']
    def install(self,skip):
        if skip: return
        for target,spec in self.spec.items():
            if self.e.dry:
                records=self.local_plugins(target)
                obsolete=self.obsolete_markets(target,records,self.local_marketplaces(target))
                if self.exact(target,records) and not self.retired(target,records) and not obsolete: continue
                for record in self.retired(target,records):
                    print('NATIVE RETIRE '+target+' '+record['_id']+' (backup cache, unregister)')
                for name in obsolete: print('NATIVE RETIRE MARKETPLACE '+target+' '+name+' (backup registry/catalog, unregister)')
                if not any(r['_id']==spec['id'] and r.get('version')==spec['version'] and r.get('enabled') for r in records):
                    print('NATIVE INSTALL '+target+' '+spec['id']+' version='+spec['version'])
                self.e.changed=True; continue
            records=self.plugins(target); markets=self.marketplaces(target)
            obsolete=self.obsolete_markets(target,records,markets)
            if self.exact(target,records) and not self.retired(target,records) and not obsolete: continue
            self.e.changed=True
            self.capture_registries(target)
            self.e.state['native'].setdefault(target,{'created_plugin':False,'created_marketplace':False})
            flags=self.e.state['native'][target]
            flags.setdefault('original_marketplaces',[{'name':r['name'],'location':r.get('installLocation') or r.get('root') or r.get('path')} for r in markets])
            if target=='codex':
                flags.setdefault('original_plugins',[self.plugin_metadata(r) for r in self.before.get(target,records)])
            if 'original_registry' not in flags:
                flags['original_registry']={}
                for rel in REGISTRY[target]:
                    record=self.e.record(rel)
                    original=self.e.state_dir/record['backup'] if record.get('backup') else None
                    flags['original_registry'][rel]=self.registry_identity(original) if original else None
            flags.setdefault('retired_marketplaces',[])
            self.e.save()
            try:
                # Install/read back the pin before retiring other registrations.
                if not any(x.get('name')=='ssot-pinned' for x in markets):
                    args=['plugin','marketplace','add',str(spec['catalog']),'--json']
                    if target=='claude': args+=['--scope','user']
                    self.e.state['native'][target]['created_marketplace']=True; self.e.save()
                    self.run(target,args,cwd=spec['catalog'])
                    if not any(x.get('name')=='ssot-pinned' for x in self.marketplaces(target)): raise ValueError('marketplace add readback failed')
                selected=next((x for x in records if x['_id']==spec['id']),None)
                if selected and (selected.get('version')!=spec['version'] or not selected.get('enabled')):
                    raise ValueError('existing lock-target plugin differs; refusing destructive update')
                if not selected:
                    self.e.state['native'][target]['created_plugin']=True; self.e.save()
                    args=['plugin','install',spec['id'],'--scope','user','--json'] if target=='claude' else ['plugin','add',spec['id'],'--json']
                    self.run(target,args)
                selected=next((x for x in self.plugins(target) if x['_id']==spec['id']),None)
                if not selected or selected.get('version')!=spec['version'] or selected.get('enabled') is not True: raise ValueError('native lock version/enabled readback failed')
                for r in self.retired(target,self.plugins(target)):
                    cache=self.cache_path(target,r)
                    self.e.move(str(cache.relative_to(self.e.home)),cache_selector=r['_id'])
                    self.remove(target,r['_id'])
                    # Claude may rehydrate a missing installed cache while uninstalling
                    # and leave it orphaned. Preserve that generated copy too, but do
                    # not restore it over the original backup on uninstall.
                    self.e.quarantine_caches()
                for name in obsolete:
                    # Original registry bytes restore the registration; move native
                    # catalog caches out of reach of the CLI's recursive deletion.
                    rel='.'+target+'/plugins/marketplaces/'+name
                    self.e.move(rel)
                    if name not in flags['retired_marketplaces']: flags['retired_marketplaces'].append(name)
                    self.e.save()
                    self.remove_market(target,name)
                    print('NATIVE RETIRE MARKETPLACE '+target+' '+name)
                if not self.exact(target,self.plugins(target)): raise ValueError('superpowers uniqueness readback failed')
            finally:
                self.update_registry_hashes(target)
    def uninstall(self,skip):
        if skip:
            if self.e.state['native']: raise ValueError('native plugins are managed; omit --assets-only to restore them')
            return
        self.e.quarantine_caches()
        for target,flags in list(self.e.state['native'].items()):
            if self.e.dry:
                print('NATIVE RESTORE '+target); self.e.changed=True; continue
            if not shutil.which(target): raise ValueError('native CLI missing for uninstall: '+target)
            if flags.get('removed'): continue  # rollback resumes after file restore
            for r in self.e.state['records']:
                if not self.e.matches(self.e.path(r['path']),r): raise ValueError('uninstall refuses modified item: '+r['path'])
            try:
                selector=self.spec[target]['id']
                if flags['created_plugin'] and any(r['_id']==selector for r in self.plugins(target)): self.remove(target,selector)
                if flags['created_marketplace'] and any(r.get('name')=='ssot-pinned' for r in self.marketplaces(target)):
                    self.run(target,['plugin','marketplace','remove','ssot-pinned','--json']+(['--scope','user'] if target=='claude' else []))
                    if any(r.get('name')=='ssot-pinned' for r in self.marketplaces(target)): raise ValueError('marketplace removal readback failed')
            finally: self.update_registry_hashes(target)
            # Keep expectations durable until files AND native readback succeed.
            flags['removed']=True; self.e.save()

    def plugin_metadata(self,record):
        result={'_id':record['_id']}
        for key in ('version','enabled','gitCommitSha'):
            if key in record: result[key]=record[key]
        if isinstance(record.get('source'),dict):
            result['source']={k:v for k,v in record['source'].items() if k in {'source','url','sha','path','ref','repo','subdir'}}
        return result

    def restoration_registries(self,target,flags):
        from setup_symlinks import exists, no_symlink_parents
        saved=flags.setdefault('restore_registry',{})
        for i,rel in enumerate(REGISTRY[target]):
            path=self.e.path(rel)
            if path.is_symlink() or (exists(path) and not path.is_file()): raise ValueError('unsafe restoration registry: '+rel)
            if rel in flags.get('original_registry',{}):
                actual=self.registry_identity(path) if exists(path) else None
                if actual!=flags['original_registry'][rel]: raise ValueError('original restoration registry changed by user: '+rel)
            name='native-restore/'+target+'-'+str(i)
            if rel in saved:
                if saved[rel].get('backup')!=name: raise ValueError('unsafe restoration snapshot path')
                expected=saved[rel]['digest']
                actual=hashlib.sha256(path.read_bytes()).hexdigest() if exists(path) else None
                if expected!=actual: raise ValueError('restoration registry changed by user: '+rel)
                continue
            backup=self.e.state_dir/name; no_symlink_parents(backup)
            if exists(backup): raise ValueError('restoration registry snapshot already exists')
            if exists(path):
                backup.parent.mkdir(mode=0o700,exist_ok=True); shutil.copy2(path,backup)
                digest=hashlib.sha256(path.read_bytes()).hexdigest()
            else: digest=None
            saved[rel]={'backup':name,'digest':digest}; self.e.save()
        return saved

    def registry_identity(self,path):
        metadata=path.stat()
        return {'digest':hashlib.sha256(path.read_bytes()).hexdigest(),'mode':metadata.st_mode,'mtime_ns':metadata.st_mtime_ns}

    def put_registries(self,saved):
        from setup_symlinks import exists, no_symlink_parents
        for rel,record in saved.items():
            path=self.e.path(rel)
            if path.is_symlink() or (exists(path) and not path.is_file()): raise ValueError('unsafe native restoration registry: '+rel)
            if record['digest'] is None:
                if exists(path): path.unlink()
            else:
                backup=self.e.state_dir/record['backup']; no_symlink_parents(backup)
                if backup.is_symlink() or not backup.is_file(): raise ValueError('unsafe restoration snapshot')
                if hashlib.sha256(backup.read_bytes()).hexdigest()!=record['digest']: raise ValueError('restoration snapshot changed')
                self.e.restore_parent(path); shutil.copy2(backup,path)

    def restore_plugins(self,target,flags,saved):
        originals=flags.get('original_plugins')
        if originals is None:
            if target=='codex': raise ValueError('old Codex journal lacks original plugin metadata; native restoration cannot be verified')
            return
        actual={r['_id']:r for r in self.plugins(target)}
        for original in originals:
            selector=original['_id']
            if not re.fullmatch(r'[a-z0-9._-]+@[a-z0-9._-]+',selector): raise ValueError('unsafe original plugin selector')
            if selector not in actual:
                # Only registrations retired by this installer may be recreated.
                if selector.split('@')[0] not in {'superpowers','bagjuhyeon-agent-ssot'}: raise ValueError('unrelated original plugin disappeared: '+selector)
                self.run(target,['plugin','add',selector,'--json'])
                self.put_registries(saved)  # CLI add enables; preserve original enabled state
                print('NATIVE RESTORE PLUGIN '+target+' '+selector)
        actual={r['_id']:self.plugin_metadata(r) for r in self.plugins(target)}
        if set(actual)!={r['_id'] for r in originals}: raise ValueError('original plugin selector restoration readback failed: '+target)
        for original in originals:
            observed=actual[original['_id']]
            if any(observed.get(k)!=v for k,v in original.items()):
                raise ValueError('original plugin version/enabled/source restoration readback failed: '+original['_id'])

    def verify_restored(self):
        if self.e.dry: return
        for target,flags in list(self.e.state['native'].items()):
            if not flags.get('removed'): raise ValueError('native rollback removal not complete')
            saved=self.restoration_registries(target,flags)
            try:
                originals=flags.get('original_marketplaces',[])
                actual={r['name']:r for r in self.marketplaces(target)}
                names={r if isinstance(r,str) else r['name'] for r in originals}
                if set(actual)!=names: raise ValueError('original marketplace restoration readback failed: '+target)
                for r in originals:
                    if isinstance(r,str) or not r.get('location'): continue
                    item=actual[r['name']]
                    location=item.get('installLocation') or item.get('root') or item.get('path')
                    if location!=r['location']: raise ValueError('original marketplace source restoration readback failed: '+target+' '+r['name'])
                self.restore_plugins(target,flags,saved)
            finally:
                self.put_registries(saved)
            del self.e.state['native'][target]; self.e.save()
            for record in saved.values():
                backup=self.e.state_dir/record['backup']
                if backup.exists(): backup.unlink()
