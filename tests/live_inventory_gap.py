"""F13 actual native CLI refusal and successful no-op boundaries, fake HOME only."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

R=Path(__file__).resolve().parents[1]
W=R/'.test-tmp'; W.mkdir(exist_ok=True)
T=Path(tempfile.mkdtemp(prefix='inventory-gap-',dir=W))
commands=[]; results=[]

def metadata(root):
    result={}
    for base,dirs,files in os.walk(root,followlinks=False):
        for name in dirs+files:
            p=Path(base)/name; st=p.lstat()
            result[str(p.relative_to(root))]=[st.st_mode,st.st_mtime_ns,os.readlink(p) if p.is_symlink() else hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else None]
    return result

def environment(home):
    env={k:v for k,v in os.environ.items() if not any(x in k.upper() for x in ('TOKEN','API_KEY','CREDENTIAL','PASSWORD','SECRET'))}
    b=T/'bin'; b.mkdir(exist_ok=True)
    if not (b/'python3').exists(): (b/'python3').symlink_to(sys.executable)
    env.update(HOME=str(home),CODEX_HOME=str(home/'.codex'),CLAUDE_CONFIG_DIR=str(home/'.claude'),PATH=str(b)+':'+env['PATH'],PYTHONDONTWRITEBYTECODE='1',PYTHONPYCACHEPREFIX=str(T/'bytecode'),TMPDIR=str(T),CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC='1',DISABLE_AUTOUPDATER='1')
    return env

def run(label,home,cmd,expected=0):
    p=subprocess.run(cmd,cwd=R,env=environment(home),text=True,capture_output=True,timeout=240)
    log=T/(label+'.log'); log.write_text(p.stdout+p.stderr)
    commands.append({'label':label,'command':cmd,'exit_code':p.returncode,'expected_exit_code':expected,'log':log.name})
    (T/'commands.json').write_text(json.dumps(commands,indent=2)+'\n')
    assert p.returncode==expected,(label,p.returncode,p.stderr)
    return p

for market in ('unavailable-local','openai-curated-remote'):
    h=T/market; h.mkdir(); (h/'.codex').mkdir()
    selector='superpowers@'+market
    config=h/'.codex/config.toml'; config.write_text('[plugins."'+selector+'"]\nenabled = true\n'); config.chmod(0o640)
    cache=h/'.codex/plugins/cache'/market/'superpowers'
    manifest=cache/'1/.codex-plugin/plugin.json'; manifest.parent.mkdir(parents=True); manifest.write_text(json.dumps({'name':'superpowers','version':'1.0.0'}))
    (cache/'1/PRIVATE').mkdir(); (cache/'1/PRIVATE/synthetic-user-data').write_text('must stay untouched')
    (cache/'1/synthetic-link').symlink_to('PRIVATE/synthetic-user-data')
    original=(config.read_bytes(),config.stat().st_mode,config.stat().st_mtime_ns,metadata(cache))
    before=json.loads(run(market+'-before-list',h,['codex','plugin','list','--json']).stdout)
    assert before['installed']==[],before
    for n in range(2):
        p=run(market+'-refuse-'+str(n),h,[str(R/'setup')],2)
        assert p.stdout=='' and 'absent from native inventory; preserved config/cache' in p.stderr,(p.stdout,p.stderr)
        assert selector in p.stderr
        assert original==(config.read_bytes(),config.stat().st_mode,config.stat().st_mtime_ns,metadata(cache))
        assert not (h/'.claude').exists() and not (h/'.agent-skills-setup').exists()
        assert not (h/'.codex/agents').exists() and not (h/'.codex/skills').exists()
    after=json.loads(run(market+'-after-list',h,['codex','plugin','list','--json']).stdout); assert after['installed']==[]
    before_noop=metadata(h)
    for n in range(2):
        assert run(market+'-uninstall-'+str(n),h,[str(R/'setup'),'--uninstall']).stdout==''
        assert metadata(h)==before_noop
    results.append({'selector':selector,'fixture':'synthetic config/cache, actual CLI, no authentication','refused_before_installer_writes':True,'config_cache_private_symlink_metadata_preserved':True,'repeat_refusal':True,'two_uninstalls_exact_noop':True})

h=T/'healthy'; h.mkdir(); (h/'.codex').mkdir()
config=h/'.codex/config.toml'; config.write_text('model = "gpt-5"\n# synthetic user config\n'); config.chmod(0o640)
original=(config.read_bytes(),config.stat().st_mode,config.stat().st_mtime_ns)
run('healthy-install',h,[str(R/'setup')])
for target in ('claude','codex'):
    listed=json.loads(run('healthy-'+target+'-readback',h,[target,'plugin','list','--json']).stdout)
    records=listed if target=='claude' else listed['installed']
    assert len(records)==1 and (records[0].get('id') or records[0].get('pluginId'))=='superpowers@ssot-pinned'
    assert records[0]['enabled'] is True
# Discovery may populate native caches; validate idempotence after actual reads.
for label,argv in [('dry',['--dry-run']),('rerun',[]),('dry2',['--dry-run'])]:
    assert run('healthy-'+label,h,[str(R/'setup')]+argv).stdout==''
run('healthy-uninstall',h,[str(R/'setup'),'--uninstall'])
assert original==(config.read_bytes(),config.stat().st_mode,config.stat().st_mtime_ns)
before=metadata(h)
assert run('healthy-second-uninstall',h,[str(R/'setup'),'--uninstall']).stdout==''
assert before==metadata(h)
results.append({'fixture':'healthy actual CLI','successful_install':True,'both_native_readbacks':True,'dry_rerun_dry_noop':True,'original_config_restored':True,'second_uninstall_exact_noop':True})
report={'python':sys.version.split()[0],'exact_head':subprocess.check_output(['git','rev-parse','HEAD'],cwd=R,text=True).strip(),'workspace':str(T),'native_cli_mocked':False,'auth_db_copied':False,'results':results}
(T/'readback.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
