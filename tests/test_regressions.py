"""F1-F4 regressions. Protocol mocks are not native runtime evidence."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from test_setup import ROOT, snapshot
import setup_symlinks as setup
from setup_plugins import NativePlugins

class RegressionTests(unittest.TestCase):
    def setUp(self):
        temp_root=ROOT/'.test-tmp'; temp_root.mkdir(exist_ok=True)
        self.temp=tempfile.TemporaryDirectory(dir=temp_root)
        self.base=Path(self.temp.name); self.home=self.base/'home'; self.home.mkdir()
        self.manifest,self.lock,self.templates=setup.load_contract()
    def tearDown(self): self.temp.cleanup()
    def run_setup(self,*args,root=ROOT):
        return subprocess.run([sys.executable,str(root/'tools/setup_symlinks.py'),*args],env=dict(os.environ,HOME=str(self.home),CLAUDE_CONFIG_DIR=str(self.home/'.claude'),CODEX_HOME=str(self.home/'.codex'),PYTHONDONTWRITEBYTECODE='1'),capture_output=True,text=True)
    def config(self,text):
        p=self.home/'.codex/config.toml'; p.parent.mkdir(exist_ok=True); p.write_text(text); return p
    def oracle(self,p):
        python=shutil.which('python3.12')
        if not python: self.skipTest('independent tomllib oracle needs Python 3.12 on PATH')
        result=subprocess.run([python,str(ROOT/'tests/toml_oracle.py'),str(p)],capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)
        return json.loads(result.stdout)
    def test_single_quoted_managed_key_valid_and_reversible(self):
        p=self.config("[agents.'debugger']\n'config_file' = 'custom-local.toml' # user value\nkeep = 'untouched'\n")
        before=snapshot(self.home); self.oracle(p)
        result=self.run_setup('--assets-only'); self.assertEqual(result.returncode,0,result.stderr)
        parsed=self.oracle(p)
        self.assertEqual(parsed['agents']['debugger']['config_file'],str(self.home/'.codex/agents/debugger.toml'))
        self.assertEqual(parsed['agents']['debugger']['keep'],'untouched')
        after=snapshot(self.home); result=self.run_setup('--assets-only'); self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(result.stdout,''); self.assertEqual(after,snapshot(self.home))
        self.assertEqual(self.run_setup('--assets-only','--uninstall').returncode,0)
        self.assertEqual(before,snapshot(self.home,True))
    def test_unsupported_managed_forms_fail_before_all_writes(self):
        forms=[
            'agents.debugger.config_file = "custom-local.toml"\n',
            "'agents'.'debugger'.'config_file' = 'custom-local.toml'\n",
            'agents = { debugger = { config_file = "custom-local.toml" } }\n',
            '[agents]\ndebugger = { config_file = "custom-local.toml" }\n',
            '[agents]\ndebugger.config_file = "custom-local.toml"\n',
            '[[agents.debugger]]\nconfig_file = "custom-local.toml"\n',
        ]
        for text in forms:
            for mode in ([],['--assets-only'],['--dry-run']):
                with self.subTest(text=text,mode=mode):
                    p=self.config(text); self.oracle(p); before=snapshot(self.home)
                    result=self.run_setup(*mode)
                    self.assertEqual(result.returncode,2,result.stdout+result.stderr)
                    self.assertIn('manual review',result.stderr)
                    self.assertEqual(before,snapshot(self.home))
    def test_unmanaged_dotted_inline_tables_and_literal_key_preserved(self):
        text='local.value = "keep"\nother = { enabled = true }\n["agents.debugger"]\nconfig_file = "literal-dot-not-agent"\n'
        p=self.config(text); result=self.run_setup('--assets-only'); self.assertEqual(result.returncode,0,result.stderr)
        self.assertTrue(p.read_text().startswith(text)); self.oracle(p)
    def fake_contract(self,entries):
        fake=self.base/'repo'; (fake/'tools').mkdir(parents=True,exist_ok=True)
        for filename in ('setup_symlinks.py','setup_plugins.py'): shutil.copy2(ROOT/'tools'/filename,fake/'tools'/filename)
        (fake/'sources/a').mkdir(parents=True,exist_ok=True); (fake/'sources/a/SKILL.md').write_text('one')
        (fake/'sources/b').mkdir(parents=True,exist_ok=True); (fake/'sources/b/SKILL.md').write_text('different')
        (fake/'manifest.yaml').write_text(json.dumps({'schema_version':2,'contract':'item-symlink','links':entries}))
        return fake
    def test_case_unicode_alias_and_overlap_fail_home_unchanged(self):
        pairs=[('skills/aha','skills/Aha'),('skills/caf\u00e9','skills/cafe\u0301'),('skills/aha','skills/AHA/SKILL.md'),('skills/caf\u00e9','skills/cafe\u0301/SKILL.md')]
        for a,b in pairs:
            with self.subTest(pair=(a,b)):
                entries=[{'harness':'claude','destination':d,'source':s} for d,s in ((a,'sources/a'),(b,'sources/b'))]
                fake=self.fake_contract(entries); before=snapshot(self.home)
                result=self.run_setup(root=fake)
                self.assertEqual(result.returncode,2,result.stdout+result.stderr)
                self.assertRegex(result.stderr,'duplicate destination|overlapping')
                self.assertEqual(before,snapshot(self.home))
    def test_claude_native_names_unique_and_canonical_comparison(self):
        agents=[e for e in self.manifest['links'] if e['harness']=='claude' and e['destination'].startswith('agents/')]
        names=[json.loads((ROOT/e['source']).read_text().split('---',2)[1].split('name: ',1)[1].splitlines()[0]) for e in agents]
        self.assertEqual(len(agents),34); self.assertEqual(len(names),len(set(names)))
        self.assertIn('academic-reviewer',names); self.assertIn('dslab-academic-reviewer',names)
        for name in ('academic-planner','report-planner','report-reviewer'):
            a=(ROOT/'sources/agents'/f'{name}-claude.md').read_text().split('---',2)[2]
            b=(ROOT/'sources/agents'/f'claude-for-dslab-{name}-claude.md').read_text().split('---',2)[2]
            self.assertEqual(a,b)
            self.assertFalse(any(e['id']==f'claude-for-dslab-{name}-claude' for e in agents))
    def test_duplicate_claude_native_name_rejected(self):
        entries=[{'harness':'claude','destination':d,'source':'sources/agent.md'} for d in ('agents/a.md','agents/b.md')]
        fake=self.fake_contract(entries); (fake/'sources/agent.md').write_text('---\nname: "same"\n---\nPrompt\n')
        before=snapshot(self.home); result=self.run_setup(root=fake)
        self.assertEqual(result.returncode,2); self.assertIn('duplicate Claude native name',result.stderr)
        self.assertEqual(before,snapshot(self.home))
    def test_retired_agent_alias_copies_restored_and_modified_alias_refused(self):
        for e in self.manifest['retired_links']:
            p=self.home/'.claude'/e['destination']; p.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(ROOT/e['source'],p)
        before=snapshot(self.home); result=self.run_setup('--assets-only')
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertTrue(all(not (self.home/'.claude'/e['destination']).exists() for e in self.manifest['retired_links']))
        self.assertEqual(self.run_setup('--assets-only').stdout,'')
        self.assertEqual(self.run_setup('--assets-only','--uninstall').returncode,0)
        self.assertEqual(before,snapshot(self.home,True))
        p=self.home/'.claude'/self.manifest['retired_links'][0]['destination']; p.write_text('user modification')
        before=snapshot(self.home); result=self.run_setup('--assets-only')
        self.assertEqual(result.returncode,2); self.assertIn('differs from approved',result.stderr)
        self.assertEqual(before,snapshot(self.home))
    def test_retiring_previously_managed_link_keeps_original_backup(self):
        engine=setup.Installer(self.home); e=self.manifest['retired_links'][0]; rel='.claude/'+e['destination']
        p=self.home/rel; p.parent.mkdir(parents=True); p.write_text('original pre-setup user file')
        before=snapshot(self.home); engine.link(rel,ROOT/e['source']); engine.move(rel)
        self.assertFalse(p.exists()); self.assertEqual(engine.record(rel)['kind'],'moved')
        engine.uninstall(); self.assertEqual(before,snapshot(self.home,True))
    def test_obsolete_markets_keep_unrelated_plugins_and_mixed_catalogs(self):
        native=NativePlugins(setup.Installer(self.home),ROOT,self.lock)
        for target in ('claude','codex'):
            markets=[]; records=[]
            filename='.claude-plugin/marketplace.json' if target=='claude' else '.agents/plugins/marketplace.json'
            for name,plugins in [('dedicated',['superpowers']),('shared',['superpowers']),('mixed',['superpowers','other']),('unknown',['other'])]:
                p=self.base/target/name/filename; p.parent.mkdir(parents=True); p.write_text(json.dumps({'plugins':[{'name':n} for n in plugins]}))
                markets.append({'name':name,'root':str(self.base/target/name)})
                records.append({'_id':'superpowers@'+name})
            records.append({'_id':'other@shared'})
            self.assertEqual(native.obsolete_markets(target,records,markets),['dedicated'])
            # Stranded dedicated catalog remains eligible after its plugin is gone.
            self.assertEqual(native.obsolete_markets(target,[r for r in records if r['_id']!='superpowers@dedicated'],markets),['dedicated'])
    def test_marketplace_registry_and_native_catalog_cache_restore(self):
        # Mock commands mutate the same registry files the real CLI owns.
        engine=setup.Installer(self.home); native=NativePlugins(engine,ROOT,self.lock); native.spec={'claude':native.spec['claude']}
        registry=self.home/'.claude/plugins/known_marketplaces.json'; registry.parent.mkdir(parents=True)
        cache=self.home/'.claude/plugins/marketplaces/old-duplicate'; (cache/'.claude-plugin').mkdir(parents=True)
        (cache/'.claude-plugin/marketplace.json').write_text(json.dumps({'plugins':[{'name':'superpowers'}]}))
        plugin=self.home/'.claude/plugins/cache/old-duplicate/superpowers/1'; plugin.mkdir(parents=True); (plugin/'payload').write_text('original')
        registry.write_text(json.dumps({'old-duplicate':str(cache),'unrelated':'preserve'}))
        before=snapshot(self.home); current=['superpowers@old-duplicate','unrelated@unrelated']
        def run(target,args,cwd=None):
            if args[:2]==['plugin','list']: return [{'id':x,'version':'6.4.1','enabled':True} for x in current]
            markets=json.loads(registry.read_text())
            if args[:3]==['plugin','marketplace','list']: return [{'name':k,'installLocation':v} for k,v in markets.items()]
            if args[:3]==['plugin','marketplace','add']: markets['ssot-pinned']=str(native.spec['claude']['catalog']); registry.write_text(json.dumps(markets)); return {}
            if args[:3]==['plugin','marketplace','remove']: del markets[args[3]]; registry.write_text(json.dumps(markets)); return {}
            if args[:2]==['plugin','install']: current.append(args[2]); return {}
            if args[:2]==['plugin','uninstall']: current.remove(args[2]); return {}
            raise AssertionError(args)
        native.run=run; native.install(False)
        self.assertEqual(set(json.loads(registry.read_text())),{'unrelated','ssot-pinned'})
        self.assertIn('unrelated@unrelated',current); self.assertFalse(cache.exists())
        after=snapshot(self.home); native.install(False); self.assertEqual(after,snapshot(self.home))
        native.uninstall(False); engine.uninstall(); native.verify_restored()
        self.assertEqual(before,snapshot(self.home,True))

if __name__=='__main__': unittest.main(verbosity=2)
