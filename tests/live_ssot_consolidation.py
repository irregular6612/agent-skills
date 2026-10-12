"""Consolidated skills: real native install, shared edit, rerun, restore. Fake HOME only."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

R=Path(__file__).resolve().parents[1]
(R/'.test-tmp').mkdir(exist_ok=True)
W=Path(tempfile.mkdtemp(prefix='ssot-consolidation-',dir=R/'.test-tmp'))
H=W/'home'; H.mkdir()
E=W/'evidence'; E.mkdir()
env={k:v for k,v in os.environ.items() if not any(x in k.upper() for x in ('TOKEN','API_KEY','CREDENTIAL','PASSWORD','SECRET'))}
env.update(HOME=str(H),CODEX_HOME=str(H/'.codex'),CLAUDE_CONFIG_DIR=str(H/'.claude'),PYTHONDONTWRITEBYTECODE='1',CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC='1',DISABLE_AUTOUPDATER='1',TMPDIR=str(W))
commands=[]
def run(command,label):
    p=subprocess.run(command,cwd=R,env=env,capture_output=True,text=True,timeout=240)
    (E/(label+'.log')).write_text(p.stdout+p.stderr)
    commands.append({'command':command,'exit_code':p.returncode,'log':label+'.log'})
    (E/'commands.json').write_text(json.dumps(commands,indent=2)+'\n')
    assert p.returncode==0,(label,p.returncode,p.stderr)
    return p.stdout

def identity(p):
    s=p.lstat()
    return ('link',os.readlink(p),s.st_mode,s.st_mtime_ns) if p.is_symlink() else ('file',p.read_bytes(),s.st_mode,s.st_mtime_ns)

common=json.loads((R/'docs/SYMLINK-INVENTORY.json').read_text())['shared_skill_names']
pack=json.loads((R/'dependencies/lock.yaml').read_text())['external_skills'][0]
original={}
# Reproduce legacy external payloads without using a real HOME.
for skill in pack['skills']:
    target=H/'.agents/skills'/skill['name']; shutil.copytree(R/skill['canonical'],target)
    for harness in ('claude','codex'):
        p=H/('.'+harness)/'skills'/skill['name']; p.parent.mkdir(parents=True,exist_ok=True); p.symlink_to(target)
        original[str(p.relative_to(H))]=identity(p)
    original[str((target/'SKILL.md').relative_to(H))]=identity(target/'SKILL.md')
for rel in ('.claude/skills/agentcat-usage/LOCAL.md','.codex/skills/lost-me/LOCAL.md','.claude/hooks/paper-frontmatter-hook.py','.claude/hooks/unknown-hook.sh'):
    p=H/rel; p.parent.mkdir(parents=True,exist_ok=True); p.write_bytes(b'unmanaged fixture, preserve\n'); p.chmod(0o640); os.utime(p,ns=(1650000000000000000,1650000000000000000)); original[rel]=identity(p)
for rel,data in (('.claude/settings.json','{"theme":"local","permissions":{"deny":["Bash(rm:*)"]}}\n'),('.codex/config.toml','# local machine\nmodel="local"\n')):
    p=H/rel; p.parent.mkdir(parents=True,exist_ok=True); p.write_text(data); p.chmod(0o640); original[rel]=identity(p)

assert 'LINK' in run([str(R/'setup'),'--dry-run'],'initial-dry')
assert all(identity(H/rel)==old for rel,old in original.items())
run([str(R/'setup')],'install')
manifest=json.loads((R/'manifest.yaml').read_text())
for e in manifest['links']:
    dest=H/('.'+e['harness'])/e['destination']; assert dest.is_symlink() and dest.resolve()==(R/e['source']).resolve(),e
saved={}
try:
    for name in common:
        p=R/'sources/skills'/name/'SKILL.md'; saved[p]=(p.read_bytes(),p.stat().st_atime_ns,p.stat().st_mtime_ns)
        p.write_bytes(saved[p][0]+b'\n<!-- isolated shared-edit propagation probe -->\n')
        for harness in ('claude','codex'):
            assert (H/('.'+harness)/'skills'/name/'SKILL.md').read_bytes()==p.read_bytes(),(name,harness)
    assert run([str(R/'setup'),'--dry-run'],'edited-dry')==''
    assert run([str(R/'setup')],'edited-rerun')==''
finally:
    for p,(data,atime,mtime) in saved.items(): p.write_bytes(data); os.utime(p,ns=(atime,mtime))
assert run([str(R/'setup')],'restored-source-rerun')==''
for harness in ('claude','codex'):
    values=json.loads(run([harness,'plugin','list','--json'],harness+'-plugins'))
    rows=values if isinstance(values,list) else values['installed']
    superpowers=[v for v in rows if (v.get('id') or v.get('pluginId','')).startswith('superpowers@')]
    assert len(superpowers)==1 and (superpowers[0].get('id') or superpowers[0].get('pluginId'))=='superpowers@ssot-pinned'
run([str(R/'setup'),'--uninstall'],'uninstall')
assert all(identity(H/rel)==old for rel,old in original.items())
assert run([str(R/'setup'),'--uninstall'],'second-uninstall')==''
state=json.loads((H/'.agent-skills-setup/state.json').read_text()); assert not state['records'] and not state['native']
report={'manifest_links':len(manifest['links']),'shared_edit_skills':len(common),'harnesses':2,'restored_original_records':len(original),'unknown_assets_preserved':4,'existing_taste_payload_and_links_restored':True,'native_single_pins':True,'empty_reruns':True,'empty_second_uninstall':True,'model_turns_sent':0,'real_home_modified':False,'commands':commands}
# Validate documented registration argv only, not MCP server/model execution.
MH=W/'mcp-home'; MH.mkdir(); env.update(HOME=str(MH),CODEX_HOME=str(MH/'.codex'),CLAUDE_CONFIG_DIR=str(MH/'.claude'))
(MH/'.codex').mkdir()
engine=str(R/'sources/skills/paper-banana/engine'); argv=['uv','--directory',engine,'run','paperbanana-mcp']
run(['claude','mcp','add','--scope','user','--transport','stdio','paperbanana','--',*argv],'claude-mcp-add')
cl=run(['claude','mcp','get','paperbanana'],'claude-mcp-get'); assert engine in cl and 'paperbanana-mcp' in cl
run(['codex','mcp','add','paperbanana','--',*argv],'codex-mcp-add')
co=json.loads(run(['codex','mcp','get','paperbanana','--json'],'codex-mcp-get'))
assert co['transport']['command']=='uv' and co['transport']['args']==argv[1:],co
run(['claude','mcp','remove','--scope','user','paperbanana'],'claude-mcp-remove')
run(['codex','mcp','remove','paperbanana'],'codex-mcp-remove')
report.update(mcp_registration_metadata_readback=True,mcp_connection_or_model_execution=False,commands=commands)
(E/'SSOT-LIVE.json').write_text(json.dumps(report,indent=2)+'\n')
print('PASS shared25/both HOME readthrough, native install/rerun/restore, existing taste/unknown preservation, MCP argv readback only:',E)
