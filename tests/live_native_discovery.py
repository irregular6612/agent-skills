"""Isolated native discovery, no user/model turn; assertions fail nonzero."""
from collections import Counter
import json
import os
from pathlib import Path
import queue
import re
import subprocess
import threading
import time

R=Path(__file__).resolve().parents[1]
W=R/'.test-tmp'/'native-discovery'; W.mkdir(parents=True,exist_ok=True)
H=W/'home'; H.mkdir(exist_ok=True)
E=W/'evidence'; E.mkdir(exist_ok=True)
env={k:v for k,v in os.environ.items() if not any(x in k.upper() for x in ('API_KEY','AUTH_TOKEN','ACCESS_TOKEN','OAUTH_TOKEN'))}
env.update(HOME=str(H),CLAUDE_CONFIG_DIR=str(H/'.claude'),CODEX_HOME=str(H/'.codex'),PYTHONDONTWRITEBYTECODE='1',CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC='1',DISABLE_AUTOUPDATER='1',TMPDIR=str(W/'tmp'))
Path(env['TMPDIR']).mkdir(exist_ok=True)

def run(args,name):
    p=subprocess.run(args,cwd=R,env=env,capture_output=True,text=True,timeout=240)
    (E/(name+'.log')).write_text(p.stdout+p.stderr)
    assert p.returncode==0,(args,p.returncode,p.stderr)
    return p.stdout

def redact(value):
    if isinstance(value,list): return [redact(x) for x in value]
    if isinstance(value,dict): return {k:({'redacted':True} if k=='account' else redact(v)) for k,v in value.items()}
    return value

class Wire:
    def __init__(self,name,args):
        self.name=name; self.frames=[]; self.q=queue.Queue()
        self.err=(E/(name+'-stderr.log')).open('w')
        self.p=subprocess.Popen(args,cwd=R,env=env,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=self.err,text=True,bufsize=1)
        def reader():
            for line in self.p.stdout:
                try: value=json.loads(line)
                except ValueError: value={'raw':line}
                self.q.put(value)
        threading.Thread(target=reader,daemon=True).start()
    def send(self,value):
        self.frames.append({'sent':value}); self.p.stdin.write(json.dumps(value)+'\n'); self.p.stdin.flush()
    def receive(self,predicate):
        end=time.monotonic()+90
        while time.monotonic()<end:
            try: value=self.q.get(timeout=1)
            except queue.Empty:
                if self.p.poll() is not None: raise RuntimeError(self.name+' exited')
                continue
            self.frames.append({'received':redact(value)})
            if predicate(value): return value
        raise TimeoutError(self.name)
    def close(self):
        if self.p.poll() is None: self.p.terminate()
        try: self.p.wait(timeout=15)
        except subprocess.TimeoutExpired: self.p.kill(); self.p.wait()
        self.err.close(); self.p.stdin.close(); self.p.stdout.close()
        (E/(self.name+'-wire.json')).write_text(json.dumps(self.frames,ensure_ascii=False,indent=2)+'\n')

run([str(R/'setup')],'install')
manifest=json.loads((R/'manifest.yaml').read_text())
for e in manifest['links']:
    p=H/('.'+e['harness'])/e['destination']
    assert p.is_symlink() and os.readlink(p)==str(R/e['source']) and p.exists(),str(p)
assert run([str(R/'setup')],'rerun')==''
wire=Wire('claude',['claude','-p','--input-format','stream-json','--output-format','stream-json','--verbose','--no-session-persistence','--strict-mcp-config','--mcp-config','{"mcpServers":{}}'])
try:
    wire.send({'type':'control_request','request_id':'discovery-init','request':{'subtype':'initialize'}})
    response=wire.receive(lambda o:o.get('type')=='control_response' and o.get('response',{}).get('request_id')=='discovery-init')
    claude=response['response']['response']
finally: wire.close()
commands={c['name'] for c in claude['commands']}|{a for c in claude['commands'] for a in c.get('aliases',[])}
native_agents=claude['agents']; definitions=[]
for e in manifest['links']:
    if e['harness']!='claude': continue
    category=e['destination'].split('/')[0]
    if category in {'skills','commands'}:
        name=Path(e['destination']).name if category=='skills' else Path(e['destination']).stem
        assert name in commands,(category,name)
    if category=='agents':
        front=(R/e['source']).read_text().split('---',2)[1]
        name=json.loads(re.search(r'^name:\s*(.*?)\s*$',front,re.M)[1])
        description=json.loads(re.search(r'^description:\s*(.*?)\s*$',front,re.M)[1])
        matches=[a for a in native_agents if a['name']==name]
        assert len(matches)==1,(name,matches)
        # Claude expands literal backslash-n sequences in descriptions.
        assert matches[0]['description']==description.replace('\\n','\n'),(name,matches[0])
        definitions.append({'destination':e['destination'],'name':name,'description':description,'recognized':True})
assert len(definitions)==len({d['name'] for d in definitions})
wire=Wire('codex',['codex','app-server','--stdio','--strict-config'])
try:
    wire.send({'id':1,'method':'initialize','params':{'clientInfo':{'name':'engineer-discovery','version':'1.0'},'capabilities':{'experimentalApi':True}}})
    wire.receive(lambda o:o.get('id')==1); wire.send({'method':'initialized','params':{}})
    wire.send({'id':2,'method':'skills/list','params':{'cwds':[str(R)],'forceReload':True}})
    skills=wire.receive(lambda o:o.get('id')==2)['result']['data'][0]
    wire.send({'id':3,'method':'config/read','params':{'cwd':str(R),'includeLayers':True}})
    config=wire.receive(lambda o:o.get('id')==3)['result']['config']
finally: wire.close()
assert not skills['errors'],skills['errors']
paths={str(Path(s['path']).resolve()) for s in skills['skills']}
for e in manifest['links']:
    if e['harness']=='codex' and e['destination'].startswith('skills/'):
        assert str((R/e['source']/'SKILL.md').resolve()) in paths,e
roles=json.loads((R/'templates/codex-config.json').read_text())['agents']
for name,role in roles.items():
    assert name in config['agents'],name
    assert config['agents'][name]['config_file']==role['config_file'].replace('${HOME}',str(H)),name
result={'managed_links':len(manifest['links']),'claude_agent_definitions':definitions,'claude_native_name_collisions':{n:c for n,c in Counter(a['name'] for a in native_agents).items() if c>1},'claude_skills':sum(e['harness']=='claude' and e['destination'].startswith('skills/') for e in manifest['links']),'codex_skills':sum(e['harness']=='codex' and e['destination'].startswith('skills/') for e in manifest['links']),'codex_roles':len(roles),'model_turns_sent':0}
assert not result['claude_native_name_collisions']
(E/'discovery.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
run([str(R/'setup'),'--uninstall'],'uninstall')
state=json.loads((H/'.agent-skills-setup/state.json').read_text())
assert not state['records'] and not state['native']
assert all(not (H/('.'+e['harness'])/e['destination']).is_symlink() for e in manifest['links'])
print('PASS:',len(definitions),'Claude definitions with matching runtime descriptions, zero duplicates;',result['claude_skills'],'Claude skills;',result['codex_skills'],'Codex skills;',len(roles),'effective Codex roles;',len(manifest['links']),'exact links; uninstall clean controlled records; zero model turns')
