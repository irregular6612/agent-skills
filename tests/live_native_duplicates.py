"""Live native duplicate migration smoke test, isolated HOME only."""
from pathlib import Path
import hashlib
import json
import os
import subprocess
R=Path(__file__).resolve().parents[1]
W=R/'.test-tmp'/'live-duplicates'; W.mkdir(parents=True,exist_ok=True)
H=W/'duplicate-native-home-v2'; H.mkdir(exist_ok=True)
(H/'.claude').mkdir(exist_ok=True); (H/'.codex').mkdir(exist_ok=True)
env=dict(os.environ,HOME=str(H),CLAUDE_CONFIG_DIR=str(H/'.claude'),CODEX_HOME=str(H/'.codex'),PYTHONDONTWRITEBYTECODE='1')
results=[]
def run(command):
    p=subprocess.run(command,cwd=R,env=env,text=True,capture_output=True,timeout=240)
    log=W/('duplicate-native-'+str(len(results))+'.log'); log.write_text(p.stdout+p.stderr)
    entry={'command':command,'exit_code':p.returncode,'log':str(log)}
    results.append(entry); (W/'DUPLICATE-NATIVE-SMOKE.json').write_text(json.dumps(results,indent=2)+'\n')
    print('command',command,'exit',p.returncode,'stdout_chars',len(p.stdout),'stderr',p.stderr[:500])
    if p.returncode: raise RuntimeError(str(command))
    return p.stdout

def metadata():
    # Exact file metadata, not payload export. No real HOME or auth reads.
    return {str(p.relative_to(H)):(p.lstat().st_size,p.lstat().st_mtime_ns,os.readlink(p) if p.is_symlink() else None) for p in H.rglob('*')}

lock=json.loads((R/'dependencies/lock.yaml').read_text())['dependencies'][0]
for target in ('claude','codex'):
    catalog=W/'duplicate-marketplaces'/target
    filename='.claude-plugin/marketplace.json' if target=='claude' else '.agents/plugins/marketplace.json'
    value=json.loads((R/'dependencies/marketplaces'/target/filename).read_text()); value['name']='old-duplicate'
    p=catalog/filename; p.parent.mkdir(parents=True,exist_ok=True); p.write_text(json.dumps(value))
    run([target,'plugin','marketplace','add',str(catalog),'--json']+(['--scope','user'] if target=='claude' else []))
    run([target,'plugin','install' if target=='claude' else 'add','superpowers@old-duplicate','--json']+(['--scope','user'] if target=='claude' else []))
configs={rel:(H/rel).read_bytes() for rel in ('.claude/settings.json','.codex/config.toml') if (H/rel).exists()}
before=metadata(); run([str(R/'setup'),'--dry-run']); assert before==metadata(),'dry-run wrote files'
run([str(R/'setup')])
for target in ('claude','codex'):
    data=json.loads(run([target,'plugin','list','--json'])); records=data if target=='claude' else data['installed']
    superpowers=[r for r in records if (r.get('id') or r.get('pluginId','')).split('@')[0]=='superpowers']
    assert len(superpowers)==1 and (superpowers[0].get('id') or superpowers[0].get('pluginId'))=='superpowers@ssot-pinned',superpowers
    print('unique native pin',target,superpowers[0]['version'])
before=metadata(); assert run([str(R/'setup'),'--dry-run'])=='','second dry-run reported changes'; assert before==metadata(),'second dry-run wrote files'
before=metadata(); assert run([str(R/'setup')])=='','second setup reported changes'
# Native CLIs may update bootstrap metadata on list, but controlled records must not change.
for rel,old in before.items():
    if rel.startswith('.agent-skills-setup') or rel in ('.claude/settings.json','.codex/config.toml'):
        assert metadata().get(rel)==old,(rel,old,metadata().get(rel))
run([str(R/'setup'),'--uninstall'])
for rel,data in configs.items(): assert (H/rel).read_bytes()==data,rel
for target in ('claude','codex'):
    data=json.loads(run([target,'plugin','list','--json'])); records=data if target=='claude' else data['installed']
    selectors=[r.get('id') or r.get('pluginId') for r in records]
    assert selectors==['superpowers@old-duplicate'],selectors
    print('original plugin restored',target,selectors)
print('PASS: live duplicate cleanup, pin uniqueness, idempotence, read-only dry run, config/cache restore')
