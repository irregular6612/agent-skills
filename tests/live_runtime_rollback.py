"""F8/F9/F10 actual supported CLI fixtures, never auth/internal DB access.

--baseline runs the same fault injections against the approved F7 bundle clone
and asserts the known failures. No model/user turns are submitted.
"""
import argparse
import importlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from unittest.mock import patch

parser=argparse.ArgumentParser()
parser.add_argument('--repo',type=Path,default=Path(__file__).resolve().parents[1])
parser.add_argument('--baseline',action='store_true')
args=parser.parse_args(); R=args.repo.resolve()
(R/'.test-tmp').mkdir(exist_ok=True)
W=Path(tempfile.mkdtemp(prefix='f8-f10-'+('baseline-' if args.baseline else 'candidate-'),dir=R/'.test-tmp'))
sys.path.insert(0,str(R/'tools'))
import setup_symlinks as setup
from setup_plugins import NativePlugins
lock=json.loads((R/'dependencies/lock.yaml').read_text())
commands=[]; report={'baseline':args.baseline,'model_turns_sent':0,'remote_auth_used':False,'workspace':str(W)}
native_calls=[]
env={k:v for k,v in os.environ.items() if not any(t in k.upper() for t in ('API_KEY','AUTH_TOKEN','ACCESS_TOKEN','OAUTH_TOKEN'))}
env.update(PYTHONDONTWRITEBYTECODE='1',CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC='1',DISABLE_AUTOUPDATER='1')
def home(name):
    h=W/name; h.mkdir(); (h/'.claude').mkdir(); (h/'.codex').mkdir(); return h

def run(h,cmd,code=0):
    e=dict(env,HOME=str(h),CLAUDE_CONFIG_DIR=str(h/'.claude'),CODEX_HOME=str(h/'.codex'))
    p=subprocess.run(cmd,cwd=R,env=e,capture_output=True,text=True,timeout=240)
    name=str(len(commands))+'.log'; (W/name).write_text(p.stdout+p.stderr)
    commands.append({'command':cmd,'exit_code':p.returncode,'log':name})
    (W/'commands.json').write_text(json.dumps(commands,indent=2)+'\n')
    assert p.returncode==code,(cmd,p.returncode,p.stderr)
    return p.stdout

def listed(h,target):
    data=json.loads(run(h,[target,'plugin','list','--json']))
    return data if target=='claude' else data['installed']
def file_identity(p):
    s=p.stat(); return p.read_bytes(),s.st_mode,s.st_mtime_ns
def observe(native):
    original=native.run
    def call(target,argv,cwd=None):
        value=original(target,argv,cwd)
        native_calls.append({'target':target,'args':argv,'exit_code':0})
        (W/'native-calls.json').write_text(json.dumps(native_calls,indent=2)+'\n')
        return value
    native.run=call
    return native

# F8 has its own HOME. Empty synthetic runtime; source originals never changed.
h=home('f8-home'); run(h,[str(R/'setup'),'--assets-only'])
v=R/'sources/skills/paper-banana/engine/.venv'; assert not v.exists() and not v.is_symlink()
v.mkdir()
try:
    for flags in (['--validate'],['--assets-only','--dry-run'],['--assets-only']):
        output=run(h,[str(R/'setup'),*flags],2 if args.baseline else 0)
        if not args.baseline and '--validate' not in flags: assert output==''
    run(h,[str(R/'setup'),'--assets-only','--uninstall'])
    assert v.is_dir()
finally: v.rmdir()
report['F8']={'runtime_preserved':True,'validate_dry_run_rerun_exit':2 if args.baseline else 0,'uninstall_exit':0}

# F9 uses real native cleanup plus a deterministic rename interruption.
h=home('f9-home'); c=W/'f9-catalog'; manifest=c/'.claude-plugin/marketplace.json'; manifest.parent.mkdir(parents=True)
payload=c/'payload/.claude-plugin/plugin.json'; payload.parent.mkdir(parents=True)
payload.write_text(json.dumps({'name':'superpowers','version':'1.0.0','description':'synthetic original'}))
manifest.write_text(json.dumps({'name':'generated-local-cache','owner':{'name':'fixture'},'plugins':[{'name':'superpowers','version':'1.0.0','source':'./payload'}]}))
run(h,['claude','plugin','marketplace','add',str(c),'--scope','user','--json'])
run(h,['claude','plugin','install','superpowers@generated-local-cache','--scope','user','--json'])
configs={p:file_identity(h/p) for p in ('.claude/settings.json','.claude/plugins/known_marketplaces.json','.claude/plugins/installed_plugins.json')}
run(h,[str(R/'setup')])
parent=h/'.claude/plugins/cache/generated-local-cache'
native_removed_parent=not parent.exists()
if parent.exists(): parent.rmdir()  # deterministic empty-parent fault, not payload removal
if args.baseline:
    run(h,[str(R/'setup'),'--uninstall'],2)
    state=json.loads((h/'.agent-skills-setup/state.json').read_text())
    assert state['records'] and not state['native']  # old code lost expectations
    parent.mkdir(); run(h,[str(R/'setup'),'--uninstall'])
else:
    engine=setup.Installer(h); native=observe(NativePlugins(engine,R,lock)); native.uninstall(False)
    original_rename=os.rename; injected=[False]
    def rename(a,b):
        if Path(b)==parent/'superpowers' and not injected[0]:
            injected[0]=True; raise OSError('synthetic F9 interrupted rename')
        return original_rename(a,b)
    with patch('setup_symlinks.os.rename',side_effect=rename):
        try: engine.uninstall()
        except OSError: pass
        else: raise AssertionError('fault did not fire')
    state=json.loads((h/'.agent-skills-setup/state.json').read_text())
    assert state['native']['claude']['original_marketplaces']
    assert state['native']['claude']['removed']
    run(h,[str(R/'setup'),'--uninstall'])
    assert run(h,[str(R/'setup'),'--uninstall'])==''
for p,identity in configs.items(): assert file_identity(h/p)==identity,p
assert any(r['id']=='superpowers@generated-local-cache' for r in listed(h,'claude'))
report['F9']={'native_removed_empty_parent':native_removed_parent,'interrupted_resume':not args.baseline,'original_registry_bytes_mode_mtime':True,'original_plugin_restored':True}

# F10 uses an immutable local marketplace through the actual CLI. The exact
# reserved curated selector is covered separately by protocol unit tests:
# an isolated HOME cannot use its remote catalog without authentication.
h=home('f10-home'); c=W/'f10-catalog'; manifest=c/'.agents/plugins/marketplace.json'; manifest.parent.mkdir(parents=True)
value=json.loads((R/'dependencies/marketplaces/codex/.agents/plugins/marketplace.json').read_text())
value['name']='original-immutable-fixture'
manifest.write_text(json.dumps(value))
run(h,['codex','plugin','marketplace','add',str(c),'--json'])
run(h,['codex','plugin','add','superpowers@original-immutable-fixture','--json'])
originals=listed(h,'codex'); assert len(originals)==1
config=h/'.codex/config.toml'; before=file_identity(config)
run(h,[str(R/'setup')])
engine=setup.Installer(h); native=observe(NativePlugins(engine,R,lock))
native.uninstall(False); engine.uninstall()
# Supported CLI injects missing native install; put only the synthetic original
# config back. This is exactly the observable F10 precondition, not a DB reset.
run(h,['codex','plugin','remove','superpowers@original-immutable-fixture','--json'])
config.write_bytes(before[0]); config.chmod(before[1]); os.utime(config,ns=(config.stat().st_atime_ns,before[2]))
assert not listed(h,'codex')
if args.baseline:
    native.verify_restored(); assert not listed(h,'codex')
    report['F10']={'old_verify_missed_missing_plugin':True,'original_selector':originals[0]['pluginId']}
else:
    # Fresh instance forces expectations to come from durable journal, not RAM.
    resumed=observe(NativePlugins(setup.Installer(h),R,lock))
    resumed.uninstall(False); resumed.e.uninstall(); resumed.verify_restored()
    restored=listed(h,'codex')
    assert len(restored)==1
    for key in ('pluginId','version','enabled','source'): assert restored[0].get(key)==originals[0].get(key),(key,restored,originals)
    assert file_identity(config)==before
    assert run(h,[str(R/'setup'),'--uninstall'])==''
    report['F10']={'original':native.plugin_metadata(dict(originals[0],_id=originals[0]['pluginId'])),'restored':native.plugin_metadata(dict(restored[0],_id=restored[0]['pluginId'])),'supported_cli_reinstall':True,'config_bytes_mode_mtime':True,'cache_byte_identity_guaranteed':False,'catalog_kind':'local immutable fixture; curated exact selector only protocol-tested','remote_curated_actual_cli_verified':False}
(W/'readback.json').write_text(json.dumps(report,indent=2)+'\n')
print('PASS: F8/F9/F10 baseline reproductions' if args.baseline else 'PASS: F8/F9/F10 runtime, missing-parent interrupted resume, immutable-local CLI reinstallation; curated remote unverified; zero model turns',W)
