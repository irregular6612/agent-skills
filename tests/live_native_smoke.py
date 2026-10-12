from pathlib import Path
import json
import os
import subprocess
R=Path(__file__).resolve().parents[1]
W=R/'.test-tmp'/'live-fresh'; W.mkdir(parents=True,exist_ok=True)
H=W/'native-home'; H.mkdir(exist_ok=True)
env=dict(os.environ,HOME=str(H),CLAUDE_CONFIG_DIR=str(H/'.claude'),CODEX_HOME=str(H/'.codex'),PYTHONDONTWRITEBYTECODE='1')
results=[]
commands=[[str(R/'setup')],[str(R/'setup')],['claude','plugin','list','--json'],['codex','plugin','list','--json'],[str(R/'setup'),'--uninstall']]
for i,command in enumerate(commands):
    p=subprocess.run(command,cwd=R,env=env,text=True,capture_output=True,timeout=240)
    (W/('native-'+str(i)+'.log')).write_text(p.stdout+p.stderr)
    print('command',command,'exit',p.returncode,'stdout_chars',len(p.stdout),'stderr',p.stderr[:800])
    result={'command':command,'exit_code':p.returncode,'log':str(W/('native-'+str(i)+'.log'))}
    if 'list' in command and p.returncode==0:
        data=json.loads(p.stdout); records=data if isinstance(data,list) else data.get('installed',[])
        result['plugins']=[{k:r.get(k) for k in ('id','pluginId','version','enabled')} for r in records]
        print('readback',result['plugins'])
    results.append(result)
    (W/'NATIVE-SMOKE.json').write_text(json.dumps(results,indent=2)+'\n')
    if p.returncode: break
