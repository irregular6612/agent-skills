import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import setup_symlinks as setup
from setup_plugins import NativePlugins

def snapshot(root, ignore_state=False):
    result={}
    for p in sorted(root.rglob('*')):
        rel=str(p.relative_to(root))
        if ignore_state and rel.startswith('.agent-skills-setup'): continue
        result[rel]=('link',os.readlink(p)) if p.is_symlink() else ('dir',) if p.is_dir() else ('file',p.read_bytes(),p.stat().st_mode)
    return result

class SetupTests(unittest.TestCase):
    def setUp(self):
        temp_root = ROOT/'.test-tmp'
        temp_root.mkdir(exist_ok=True)
        self.temp=tempfile.TemporaryDirectory(dir=temp_root)
        self.base=Path(self.temp.name); self.home=self.base/'home with spaces'; self.home.mkdir()
        self.manifest,self.lock,self.templates=setup.load_contract()
    def tearDown(self): self.temp.cleanup()
    def run_setup(self,*args,code=0):
        result=subprocess.run([sys.executable,str(ROOT/'tools/setup_symlinks.py'),'--assets-only',*args],env=dict(os.environ,HOME=str(self.home),PYTHONDONTWRITEBYTECODE='1'),capture_output=True,text=True)
        self.assertEqual(result.returncode,code,result.stdout+result.stderr); return result
    def test_fresh_install_shared_readthrough_idempotence_uninstall(self):
        before=snapshot(self.home)
        self.run_setup()
        for item in self.manifest['links']:
            p=self.home/('.'+item['harness'])/item['destination']
            self.assertTrue(p.is_symlink(),str(p)); self.assertEqual(p.resolve(),(ROOT/item['source']).resolve())
            if item['destination'].endswith(('.md','.toml')):
                self.assertTrue(p.is_file(),str(p))
                if item['harness']=='claude' and item['destination'].startswith('agents/'):
                    text=p.read_text(); self.assertTrue(text.startswith('---\n'),str(p)); self.assertIn('name:',text.split('---',2)[1])
        for category in ('skills','agents','commands'):
            p=self.home/'.claude'/category
            if p.exists(): self.assertFalse(p.is_symlink())
        for name in ('scientific-writing','scientific-slides','scientific-schematics'):
            self.assertEqual((self.home/'.claude/skills'/name).resolve(),(self.home/'.codex/skills'/name).resolve())
        installed=snapshot(self.home)
        result=self.run_setup(); self.assertEqual(result.stdout,''); self.assertEqual(installed,snapshot(self.home))
        self.run_setup('--uninstall'); self.assertEqual(before,snapshot(self.home,True))
        self.assertEqual(self.run_setup('--uninstall').stdout,'')
    def test_dry_run_no_writes_and_uninstall_dry_run(self):
        before=snapshot(self.home); result=self.run_setup('--dry-run')
        self.assertIn('LINK',result.stdout); self.assertEqual(before,snapshot(self.home))
        self.run_setup(); before=snapshot(self.home); self.run_setup('--uninstall','--dry-run'); self.assertEqual(before,snapshot(self.home))
    def test_backups_real_dirs_files_and_dangling_symlink(self):
        item=self.home/'.claude/skills/aha'; item.mkdir(parents=True); (item/'local.txt').write_text('do not delete')
        link=self.home/'.claude/agents/debugger.md'; link.parent.mkdir(); link.symlink_to('../../missing')
        before=snapshot(self.home); result=self.run_setup(); self.assertIn('BACKUP',result.stdout)
        self.run_setup('--uninstall'); self.assertEqual(before,snapshot(self.home,True))
    def test_config_preserves_machine_values_comments_mode_and_restores(self):
        (self.home/'.claude').mkdir(); c=self.home/'.claude/settings.json'
        c.write_text('{"env":{"EXAMPLE_PRIVATE":"local-only"},"permissions":{"allow":["Read"],"deny":["Bash(rm:*)"]},"theme":"dark"}\n'); c.chmod(0o640)
        (self.home/'.codex').mkdir(); t=self.home/'.codex/config.toml'
        t.write_text('# machine settings\nmodel = "local-model"\n[projects."/local/project"]\ntrust_level = "trusted"\n')
        before=snapshot(self.home); self.run_setup()
        data=json.loads(c.read_text()); self.assertEqual(data['env'],{'EXAMPLE_PRIVATE':'local-only'}); self.assertEqual(data['permissions']['allow'],['Read'])
        self.assertIn('# machine settings',t.read_text()); self.assertIn('trust_level = "trusted"',t.read_text())
        self.run_setup('--uninstall'); self.assertEqual(before,snapshot(self.home,True))
    def test_unmanaged_native_and_unknown_assets_preserved(self):
        for value in ('.codex/skills/.system/builtin/SKILL.md','.claude/skills/auto-code/SKILL.md','.claude/skills/unknown/SKILL.md','.claude/plugins/cache/unrelated/a/payload'):
            p=self.home/value; p.parent.mkdir(parents=True,exist_ok=True); p.write_text('preserve')
        external=self.base/'external'; external.mkdir(); (external/'SKILL.md').write_text('external')
        (self.home/'.claude/skills/agentcat-usage').symlink_to(external)
        before=snapshot(self.home); self.run_setup(); self.run_setup('--uninstall'); self.assertEqual(before,snapshot(self.home,True))
    def test_parent_symlink_escape_rejected_before_any_writes(self):
        (self.home/'.claude').mkdir(); external=self.base/'external'; external.mkdir(); (self.home/'.claude/skills').symlink_to(external)
        before=snapshot(self.base); self.run_setup(code=2); self.assertEqual(before,snapshot(self.base))
    def test_config_symlink_escape_rejected_before_any_writes(self):
        (self.home/'.codex').mkdir(); external=self.base/'config'; external.write_text('model="local"\n'); (self.home/'.codex/config.toml').symlink_to(external)
        before=snapshot(self.base); self.run_setup(code=2); self.assertEqual(before,snapshot(self.base))
    def test_malformed_config_preflight(self):
        (self.home/'.claude').mkdir(); (self.home/'.claude/settings.json').write_text('{not JSON')
        before=snapshot(self.home); self.run_setup(code=2); self.assertEqual(before,snapshot(self.home))
    def test_modified_owned_config_fails_without_touching_other_items(self):
        self.run_setup(); c=self.home/'.claude/settings.json'; c.write_text('{}')
        before=snapshot(self.home); self.run_setup('--uninstall',code=2); self.assertEqual(before,snapshot(self.home))
        self.run_setup(code=2); self.assertEqual(before,snapshot(self.home))
    def test_paths_denylist_source_and_destination(self):
        for name in ('../escape','/absolute','skills/.system/x','skills/auto-code','skills/matt-pocock','skills/x/.env','skills/x/cache','skills/x/foo.sqlite','skills/x/.DS_Store'):
            with self.subTest(name=name),self.assertRaises(ValueError): setup.relative(name)
        for path in ('skills','settings.json','plugins/cache/superpowers'):
            with self.assertRaises(ValueError): setup.validate_destination('claude',path)
    def test_nested_source_symlink_refused(self):
        source=self.base/'repo/sources/a'; source.mkdir(parents=True); (source/'bad').symlink_to(self.home)
        with patch.object(setup,'ROOT',self.base/'repo'),self.assertRaises(ValueError): setup.source('sources/a')
    def test_duplicate_destination_contract_rejected(self):
        fake=self.base/'repo'; (fake/'sources/a').mkdir(parents=True); (fake/'sources/a/SKILL.md').write_text('asset')
        entry={'harness':'claude','source':'sources/a','destination':'skills/a'}
        (fake/'manifest.yaml').write_text(json.dumps({'schema_version':2,'contract':'item-symlink','links':[entry,entry]}))
        with patch.object(setup,'ROOT',fake),self.assertRaisesRegex(ValueError,'duplicate'): setup.load_contract()
    def test_toml_merge_updates_only_target_table(self):
        original='model="local"\n[plugins."superpowers@ssot-pinned"]\nenabled = false\nother = "keep"\n[projects."/private"]\ntrust_level="trusted"\n'
        template={'plugins':{'superpowers@ssot-pinned':{'enabled':True}}}
        new=setup.merge_toml(original,template); self.assertIn('other = "keep"',new); self.assertIn('trust_level="trusted"',new)
        self.assertEqual(new,setup.merge_toml(new,template))
    def test_toml_multiline_strings_not_interpreted_as_tables(self):
        try:
            import tomllib
        except ImportError:
            tomllib=None
        original='note = """\n[plugins."superpowers@ssot-pinned"]\nenabled = false\n"""\n'
        template={'plugins':{'superpowers@ssot-pinned':{'enabled':True,'label':'keep'}}}
        new=setup.merge_toml(original,template)
        self.assertTrue(new.startswith(original))
        if tomllib:
            self.assertEqual(tomllib.loads(original)['note'],tomllib.loads(new)['note'])
            self.assertTrue(tomllib.loads(new)['plugins']['superpowers@ssot-pinned']['enabled'])
        self.assertEqual(new,setup.merge_toml(new,template))
    def test_preexisting_correct_link_is_not_claimed_or_removed(self):
        item=self.manifest['links'][0]
        path=self.home/('.'+item['harness'])/item['destination']; path.parent.mkdir(parents=True); path.symlink_to(ROOT/item['source'])
        before=snapshot(self.home); self.run_setup(); self.run_setup('--uninstall'); self.assertEqual(before,snapshot(self.home,True))
    def test_hook_commands_quote_repository_shell_metacharacters(self):
        import shlex
        root=Path("/path with spaces/$(do-not-run)/quote'part")
        value={'command':'bash "${REPO}/sources/hooks/a.sh"'}
        with patch.object(setup,'ROOT',root): rendered=setup.render(value,self.home)
        self.assertEqual(shlex.split(rendered['command']),['bash',str(root)+'/sources/hooks/a.sh'])
    def test_missing_native_cli_does_not_start_asset_install(self):
        engine=setup.Installer(self.home); native=NativePlugins(engine,ROOT,self.lock)
        before=snapshot(self.home)
        with patch('setup_plugins.shutil.which',return_value=None),self.assertRaisesRegex(ValueError,'missing'): native.preflight(False)
        self.assertEqual(before,snapshot(self.home))
    def test_tampered_state_escape_rejected(self):
        state=self.home/'.agent-skills-setup'; state.mkdir(); (state/'state.json').write_text(json.dumps({'version':1,'repo':str(ROOT),'records':[{'path':'.claude/skills/x','backup':'../../escape','kind':'link','installed':'x'}],'directories':[],'native':{}}))
        before=snapshot(self.home); self.run_setup('--uninstall',code=2); self.assertEqual(before,snapshot(self.home))
    def test_plugin_catalog_lock_rejects_nonimmutable_commit(self):
        self.lock['dependencies'][0]['commits']['claude']='main'
        with self.assertRaises(ValueError): NativePlugins(setup.Installer(self.home),ROOT,self.lock)
    def test_plugin_duplicate_cleanup_restores_registration_and_cache(self):
        # Explicit protocol mock: verifies installer mechanics, NOT a live native CLI claim.
        engine=setup.Installer(self.home); native=NativePlugins(engine,ROOT,self.lock)
        selectors=['superpowers@old-official','superpowers@generated-local-cache']
        registry=self.home/'.claude/plugins/installed_plugins.json'; registry.parent.mkdir(parents=True); registry.write_text(json.dumps(selectors))
        market_registry=registry.with_name('known_marketplaces.json'); market_registry.write_bytes(setup.encode({}))
        for selector in selectors:
            name,market=selector.split('@'); p=self.home/'.claude/plugins/cache'/market/name/'1/payload'; p.parent.mkdir(parents=True); p.write_text(selector)
        before=snapshot(self.home)
        current=list(selectors); markets=[]
        def run(target,args,cwd=None):
            if args[:3]==['plugin','list','--json']:
                return [{'id':x,'version':'6.4.1','enabled':True} for x in current]
            if args[:3]==['plugin','marketplace','list']: return [{'name':x} for x in markets]
            if args[:3]==['plugin','marketplace','add']:
                markets.append('ssot-pinned')
                market_registry.write_bytes(setup.encode({'ssot-pinned':{'source':{'source':'directory','path':args[3]},'installLocation':args[3]}})); return {}
            if args[:2]==['plugin','install']: current.append(args[2]); registry.write_text(json.dumps(current)); return {}
            if args[:2]==['plugin','uninstall']: current.remove(args[2]); registry.write_text(json.dumps(current)); return {}
            if args[:3]==['plugin','marketplace','remove']: markets.remove('ssot-pinned'); return {}
            raise AssertionError(args)
        native.spec={'claude':native.spec['claude']}
        native.run=run; native.install(False)
        self.assertEqual(current,['superpowers@ssot-pinned']); self.assertFalse((self.home/'.claude/plugins/cache/old-official/superpowers').exists())
        installed=snapshot(self.home); native.install(False); self.assertEqual(installed,snapshot(self.home))
        native.uninstall(False); engine.uninstall(); self.assertEqual(before,snapshot(self.home,True))
    def test_native_markdown_destination_rejects_directory_source(self):
        fake=self.base/'repo'; (fake/'sources/agent').mkdir(parents=True); (fake/'sources/agent/prompt.md').write_text('body')
        entry={'harness':'claude','source':'sources/agent','destination':'agents/a.md'}
        (fake/'manifest.yaml').write_text(json.dumps({'schema_version':2,'contract':'item-symlink','links':[entry]}))
        with patch.object(setup,'ROOT',fake),self.assertRaisesRegex(ValueError,'file entrypoint'): setup.load_contract()
    def test_overlapping_manifest_items_rejected(self):
        fake=self.base/'repo'; (fake/'sources/a').mkdir(parents=True); (fake/'sources/a/SKILL.md').write_text('asset')
        entries=[{'harness':'claude','source':'sources/a','destination':d} for d in ('skills/a','skills/a/SKILL.md')]
        (fake/'manifest.yaml').write_text(json.dumps({'schema_version':2,'contract':'item-symlink','links':entries}))
        with patch.object(setup,'ROOT',fake),self.assertRaisesRegex(ValueError,'overlapping'): setup.load_contract()
    def test_codex_pin_readback_requires_locked_commit(self):
        native=NativePlugins(setup.Installer(self.home),ROOT,self.lock)
        spec=native.spec['codex']
        records=[{'_id':spec['id'],'version':spec['version'],'enabled':True,'source':{'sha':spec['commit'],'url':spec['repository']}}]
        self.assertTrue(native.exact('codex',records))
        records[0]['source']['sha']='0'*40; self.assertFalse(native.exact('codex',records))
    def test_plugin_cache_escape_refused(self):
        native=NativePlugins(setup.Installer(self.home),ROOT,self.lock)
        with self.assertRaises(ValueError): native.cache_path('claude',{'_id':'superpowers@old','installPath':str(self.base/'outside')})

if __name__=='__main__': unittest.main(verbosity=2)
