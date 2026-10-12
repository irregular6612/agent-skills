"""F11/F12 isolated CLI evidence. No model turns or real HOME data."""
import argparse
import json
import os
from pathlib import Path
import py_compile
import subprocess
import sys
import tempfile

parser=argparse.ArgumentParser()
parser.add_argument('--repo',type=Path,default=Path(__file__).resolve().parents[1])
parser.add_argument('--baseline',action='store_true')
args=parser.parse_args(); R=args.repo.resolve()
(R/'.test-tmp').mkdir(exist_ok=True)
W=Path(tempfile.mkdtemp(prefix='f11-f12-',dir=R/'.test-tmp'))
H=W/'home'; H.mkdir()
env={k:v for k,v in os.environ.items() if not any(t in k.upper() for t in ('API_KEY','AUTH_TOKEN','ACCESS_TOKEN','OAUTH_TOKEN'))}
env.update(HOME=str(H),CLAUDE_CONFIG_DIR=str(H/'.claude'),CODEX_HOME=str(H/'.codex'),PYTHONDONTWRITEBYTECODE='1',CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC='1',DISABLE_AUTOUPDATER='1')
commands=[]
def run(cmd,code=0):
    p=subprocess.run(cmd,cwd=R,env=env,text=True,capture_output=True,timeout=240)
    name=str(len(commands))+'.log'; (W/name).write_text(p.stdout+p.stderr)
    commands.append({'command':cmd,'exit_code':p.returncode,'log':name})
    (W/'commands.json').write_text(json.dumps(commands,indent=2)+'\n')
    assert p.returncode==code,(cmd,p.returncode,p.stderr)
    return p.stdout

def identity(p):
    s=p.stat(); return p.read_bytes(),s.st_mode,s.st_mtime_ns

# Real native registration/retirement, followed by deterministic regeneration.
C=W/'catalog'; m=C/'.claude-plugin/marketplace.json'; m.parent.mkdir(parents=True)
f=C/'payload/.claude-plugin/plugin.json'; f.parent.mkdir(parents=True)
f.write_text(json.dumps({'name':'superpowers','version':'1.0.0','description':'synthetic original'}))
m.write_text(json.dumps({'name':'generated-local-cache','owner':{'name':'fixture'},'plugins':[{'name':'superpowers','version':'1.0.0','source':'./payload'}]}))
run(['claude','plugin','marketplace','add',str(C),'--scope','user','--json'])
run(['claude','plugin','install','superpowers@generated-local-cache','--scope','user','--json'])
configs={p:identity(H/p) for p in ('.claude/settings.json','.claude/plugins/known_marketplaces.json','.claude/plugins/installed_plugins.json')}
run([str(R/'setup')])
state=json.loads((H/'.agent-skills-setup/state.json').read_text())
rel='.claude/plugins/cache/generated-local-cache/superpowers'
r=next(r for r in state['records'] if r['path']==rel)
backup=H/'.agent-skills-setup'/r['backup']
original={str(p.relative_to(backup)):identity(p) for p in backup.rglob('*') if p.is_file()}
cache=H/rel; assert not cache.exists()
p=cache/'5bf4e7801107/.claude-plugin/plugin.json'; p.parent.mkdir(parents=True)
p.write_text(json.dumps({'name':'superpowers','version':'1.0.0','description':'synthetic regenerated'}))
(cache/'5bf4e7801107/user-note.txt').write_text('synthetic user note must be preserved')
regenerated={str(p.relative_to(cache)):identity(p) for p in cache.rglob('*') if p.is_file()}
if args.baseline:
    for flags in (['--dry-run'],[],['--uninstall','--dry-run']): run([str(R/'setup'),*flags],2)
    cache.rename(W/'manual-preservation')
    run([str(R/'setup'),'--uninstall'])
else:
    before=(H/'.agent-skills-setup/state.json').read_bytes()
    out=run([str(R/'setup'),'--dry-run']); assert 'QUARANTINE' in out
    assert (H/'.agent-skills-setup/state.json').read_bytes()==before and cache.is_dir()
    run([str(R/'setup'),'--validate'])
    run([str(R/'setup')]); assert not cache.exists()
    state=json.loads((H/'.agent-skills-setup/state.json').read_text())
    q=H/'.agent-skills-setup'/state['quarantine'][-1]
    assert {str(p.relative_to(q)):identity(p) for p in q.rglob('*') if p.is_file()}==regenerated
    assert {str(p.relative_to(backup)):identity(p) for p in backup.rglob('*') if p.is_file()}==original
    for target in ('claude','codex'):
        data=json.loads(run([target,'plugin','list','--json']))
        records=data if target=='claude' else data['installed']
        key='id' if target=='claude' else 'pluginId'
        assert len([r for r in records if r[key].startswith('superpowers@')])==1
        assert any(r[key]=='superpowers@ssot-pinned' and r['enabled'] for r in records)
    assert run([str(R/'setup'),'--dry-run'])==''
    assert run([str(R/'setup')])==''
    # Regeneration directly before uninstall follows the same preservation path.
    p.parent.mkdir(parents=True); p.write_text(json.dumps({'name':'superpowers','version':'1.0.0'}))
    run([str(R/'setup'),'--uninstall','--dry-run'])
    run([str(R/'setup'),'--uninstall'])
    assert run([str(R/'setup'),'--uninstall'])==''
for p,v in configs.items(): assert identity(H/p)==v,p
assert {str(p.relative_to(cache)):identity(p) for p in cache.rglob('*') if p.is_file()}==original

# Real Python bytecode generation, without importing/executing the engine.
H2=W/'runtime-home'; H2.mkdir(); env.update(HOME=str(H2),CLAUDE_CONFIG_DIR=str(H2/'.claude'),CODEX_HOME=str(H2/'.codex'))
run([str(R/'setup'),'--assets-only'])
source=R/'sources/skills/paper-banana-claude/engine/mcp_server/__init__.py'
runtime=source.parent/'__pycache__'; assert not runtime.exists()
py_compile.compile(str(source),doraise=True)
try:
    for flags in (['--validate'],['--assets-only','--dry-run'],['--assets-only']):
        out=run([str(R/'setup'),*flags],2 if args.baseline else 0)
        if not args.baseline and '--validate' not in flags: assert out==''
    run([str(R/'setup'),'--assets-only','--uninstall'])
    assert runtime.is_dir()
    assert run([str(R/'setup'),'--assets-only','--uninstall'])==''
finally:
    # Only bytecode produced by this fixture is removed.
    for p in runtime.iterdir(): p.unlink()
    runtime.rmdir()
report={'baseline':args.baseline,'F11':{'rerun_exit':2 if args.baseline else 0,'regenerated_payload_preserved':True,'original_backup_preserved':True,'original_configs_bytes_mode_mtime':True},'F12':{'actual_py_compile':True,'runtime_not_source':True,'validate_dry_rerun_exit':2 if args.baseline else 0},'model_turns_sent':0,'auth_copied':False,'concurrent_external_writers_verified':False}
(W/'readback.json').write_text(json.dumps(report,indent=2)+'\n')
print('PASS: F11/F12 '+('baseline failures reproduced' if args.baseline else 'preservation, runtime and actual native readback'),W)
