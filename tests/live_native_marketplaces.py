"""Real native marketplace cleanup with unrelated local plugins preserved."""
from pathlib import Path
import json
import os
import subprocess
import tempfile
R=Path(__file__).resolve().parents[1]
base=R/'.test-tmp'; base.mkdir(exist_ok=True)
W=Path(tempfile.mkdtemp(prefix='marketplace-preservation-',dir=base))
H=W/'home'; H.mkdir()
(H/'.claude').mkdir(); (H/'.codex').mkdir()
env=dict(os.environ,HOME=str(H),CLAUDE_CONFIG_DIR=str(H/'.claude'),CODEX_HOME=str(H/'.codex'),PYTHONDONTWRITEBYTECODE='1')
results=[]
def run(args):
    p=subprocess.run(args,cwd=R,env=env,text=True,capture_output=True,timeout=240)
    log=W/(str(len(results))+'.log'); log.write_text(p.stdout+p.stderr)
    results.append({'command':args,'exit_code':p.returncode,'log':str(log)})
    (W/'commands.json').write_text(json.dumps(results,indent=2)+'\n')
    print(args,'exit',p.returncode)
    assert p.returncode==0,(args,p.stderr,p.stdout)
    return p.stdout

def markets(target):
    v=json.loads(run([target,'plugin','marketplace','list','--json']))
    return v if isinstance(v,list) else v['marketplaces']
def plugins(target):
    v=json.loads(run([target,'plugin','list','--json']))
    return v if isinstance(v,list) else v['installed']
def snapshot(root):
    return {str(p.relative_to(root)):(p.lstat().st_mode,p.lstat().st_size,p.lstat().st_mtime_ns,os.readlink(p) if p.is_symlink() else p.read_bytes() if p.is_file() else None) for p in root.rglob('*')}

before={}
for target in ('claude','codex'):
    filename='.claude-plugin/marketplace.json' if target=='claude' else '.agents/plugins/marketplace.json'
    locked=json.loads((R/'dependencies/marketplaces'/target/filename).read_text())
    for name in ('old-dedicated','mixed-market','unrelated-market','generated-local-cache'):
        catalog=W/'catalogs'/target/name
        owned=locked['plugins'][0]
        managed=name=='generated-local-cache'
        plugin_name='bagjuhyeon-agent-ssot' if managed else 'local-unrelated'
        entries=[] if name=='unrelated-market' or managed else [owned]
        if name!='old-dedicated':
            payload=catalog/'payload'; manifest=payload/('.claude-plugin' if target=='claude' else '.codex-plugin')/'plugin.json'

            manifest.parent.mkdir(parents=True); manifest.write_text(json.dumps({'name':plugin_name,'version':'1.0.0','description':'isolated fixture'}))
            entries.append({'name':plugin_name,'version':'1.0.0','source':'./payload'})
        data=dict(locked,name=name,plugins=entries)
        path=catalog/filename; path.parent.mkdir(parents=True,exist_ok=True); path.write_text(json.dumps(data))
        run([target,'plugin','marketplace','add',str(catalog),'--json']+(['--scope','user'] if target=='claude' else []))
        selectors=[]
        if name!='unrelated-market' and not managed: selectors.append('superpowers@'+name)
        if name!='old-dedicated': selectors.append(plugin_name+'@'+name)
        for selector in selectors:
            run([target,'plugin','install' if target=='claude' else 'add',selector,'--json']+(['--scope','user'] if target=='claude' else []))
    before[target]={'markets':markets(target),'plugins':plugins(target)}
configs={rel:(H/rel).read_bytes() for rel in ('.claude/settings.json','.codex/config.toml','.claude/plugins/known_marketplaces.json','.claude/plugins/installed_plugins.json') if (H/rel).exists()}
source_before=snapshot(W/'catalogs')
home_before=snapshot(H); run([str(R/'setup'),'--dry-run']); assert snapshot(H)==home_before
run([str(R/'setup')])
after={}
for target in ('claude','codex'):
    ms=markets(target); ps=plugins(target)
    assert {m['name'] for m in ms}=={'mixed-market','unrelated-market','ssot-pinned'},ms
    selectors={p.get('id') or p.get('pluginId') for p in ps}
    assert selectors=={'superpowers@ssot-pinned','local-unrelated@mixed-market','local-unrelated@unrelated-market'},ps
    after[target]={'markets':ms,'plugins':ps}
home_before=snapshot(H); assert run([str(R/'setup'),'--dry-run'])==''; assert snapshot(H)==home_before
assert run([str(R/'setup')])==''
home_before=snapshot(H); run([str(R/'setup'),'--uninstall','--dry-run']); assert snapshot(H)==home_before
run([str(R/'setup'),'--uninstall'])
for rel,data in configs.items(): assert (H/rel).read_bytes()==data,rel
restored={}
for target in ('claude','codex'):
    ms=markets(target); ps=plugins(target)
    assert {m['name'] for m in ms}=={m['name'] for m in before[target]['markets']}
    assert {p.get('id') or p.get('pluginId') for p in ps}=={p.get('id') or p.get('pluginId') for p in before[target]['plugins']}
    restored[target]={'markets':ms,'plugins':ps}
assert snapshot(W/'catalogs')==source_before,'local catalog source changed'
(W/'readback.json').write_text(json.dumps({'before':before,'after':after,'restored':restored},indent=2)+'\n')
print('PASS: both native CLIs remove dedicated duplicates, preserve unrelated plugins/mixed marketplaces, restore original registries and native registrations;',W)
