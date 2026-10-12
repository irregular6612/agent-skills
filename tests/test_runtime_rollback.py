"""F8-F10 synthetic fixtures; mocks here are not actual CLI evidence."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from test_setup import ROOT, snapshot
import setup_symlinks as setup
from setup_plugins import NativePlugins

class RuntimeRollbackTests(unittest.TestCase):
    def setUp(self):
        base=ROOT/'.test-tmp'; base.mkdir(exist_ok=True)
        self.tmp=tempfile.TemporaryDirectory(dir=base)
        self.base=Path(self.tmp.name); self.home=self.base/'home'; self.home.mkdir()
        self.lock=json.loads((ROOT/'dependencies/lock.yaml').read_text())
    def tearDown(self): self.tmp.cleanup()
    def runtime_repo(self):
        root=self.base/'repo'; root.mkdir()
        subprocess.run(['git','init','-q',str(root)],check=True)
        (root/'.gitignore').write_text('.venv/\n')
        skill=root/'sources/skills/paper-banana'; (skill/'engine').mkdir(parents=True)
        (skill/'SKILL.md').write_text('synthetic original')
        return root,skill
    def test_f8_exact_ignored_runtime_opaque_and_original_unchanged(self):
        root,skill=self.runtime_repo(); venv=skill/'engine/.venv'; venv.mkdir()
        # Legitimate interpreter links are runtime, not shareable source links.
        (venv/'bin').mkdir(); (venv/'bin/python').symlink_to('/synthetic/interpreter')
        original=(skill/'SKILL.md').read_bytes()
        with patch.object(setup,'ROOT',root), patch.object(Path,'read_bytes',side_effect=AssertionError('payload read')):
            self.assertEqual(setup.source(str(skill.relative_to(root))),skill)
        self.assertEqual((skill/'SKILL.md').read_bytes(),original)
        with self.assertRaises(ValueError): setup.relative(setup.LOCAL_RUNTIME)
    def test_f8_runtime_root_symlink_and_file_refused(self):
        root,skill=self.runtime_repo(); venv=skill/'engine/.venv'
        venv.symlink_to(self.home)
        with patch.object(setup,'ROOT',root),self.assertRaises(ValueError): setup.source(str(skill.relative_to(root)))
        venv.unlink(); venv.write_text('not a directory')
        with patch.object(setup,'ROOT',root),self.assertRaises(ValueError): setup.source(str(skill.relative_to(root)))
    def test_f8_forced_tracked_runtime_refused(self):
        root,skill=self.runtime_repo(); venv=skill/'engine/.venv'; venv.mkdir(); (venv/'fake').write_text('fixture')
        subprocess.run(['git','-C',str(root),'add','-f',str(venv)],check=True)
        with patch.object(setup,'ROOT',root),self.assertRaisesRegex(ValueError,'untracked'): setup.source(str(skill.relative_to(root)))
    def test_f8_no_ignore_rule_refused(self):
        root,skill=self.runtime_repo(); (root/'.gitignore').write_text(''); (skill/'engine/.venv').mkdir()
        with patch.object(setup,'ROOT',root),self.assertRaisesRegex(ValueError,'ignored'): setup.source(str(skill.relative_to(root)))
    def test_f8_other_private_paths_and_source_symlinks_still_refused(self):
        root,skill=self.runtime_repo()
        for name in ('cache','.env','auth.json','auto-code','bad.sqlite','other/.venv','bad-link'):
            p=skill/name; p.parent.mkdir(parents=True,exist_ok=True)
            if name=='bad-link': p.symlink_to(self.home)
            else: p.write_text('synthetic rejected')
            with patch.object(setup,'ROOT',root),self.assertRaises(ValueError): setup.source(str(skill.relative_to(root)))
            p.unlink()
    def moved_cache(self):
        engine=setup.Installer(self.home)
        p=self.home/'.claude/plugins/cache/generated-local-cache/superpowers'
        p.mkdir(parents=True); (p/'fixture').write_text('original cache')
        engine.move(str(p.relative_to(self.home))); p.parent.rmdir()
        return engine,p
    def test_f9_missing_original_parent_recreated(self):
        engine,p=self.moved_cache(); engine.uninstall()
        self.assertEqual((p/'fixture').read_text(),'original cache')
        self.assertFalse(engine.state['records']); self.assertFalse(engine.state['directories'])
    def test_f9_missing_parent_dry_run_is_read_only(self):
        engine,p=self.moved_cache(); before=snapshot(self.home)
        setup.Installer(self.home,True).uninstall(); self.assertEqual(before,snapshot(self.home))
    def test_f9_symlink_parent_refused_without_any_writes(self):
        engine,p=self.moved_cache(); p.parent.symlink_to(self.base)
        before=snapshot(self.home)
        with self.assertRaisesRegex(ValueError,'symlink'): setup.Installer(self.home).uninstall()
        self.assertEqual(before,snapshot(self.home))
    def test_f9_file_parent_refused_without_any_writes(self):
        engine,p=self.moved_cache(); p.parent.write_text('unrelated')
        before=snapshot(self.home)
        with self.assertRaisesRegex(ValueError,'non-directory'): setup.Installer(self.home).uninstall()
        self.assertEqual(before,snapshot(self.home))
    def test_f9_unrelated_destination_refused(self):
        engine,p=self.moved_cache(); p.mkdir(parents=True); (p/'user').write_text('keep')
        before=snapshot(self.home)
        with self.assertRaisesRegex(ValueError,'changed by user'): setup.Installer(self.home).uninstall()
        self.assertEqual(before,snapshot(self.home))
    def test_f9_rename_interruption_before_move_resumes(self):
        engine,p=self.moved_cache()
        with patch('setup_symlinks.os.rename',side_effect=OSError('synthetic interruption')):
            with self.assertRaises(OSError): engine.uninstall()
        self.assertTrue(engine.state['records'][0]['restoring'])
        setup.Installer(self.home).uninstall(); self.assertEqual((p/'fixture').read_text(),'original cache')
    def test_f9_rename_interruption_after_move_resumes(self):
        engine,p=self.moved_cache(); real=os.rename
        def rename(a,b): real(a,b); raise OSError('synthetic after rename')
        with patch('setup_symlinks.os.rename',side_effect=rename):
            with self.assertRaises(OSError): engine.uninstall()
        setup.Installer(self.home).uninstall(); self.assertEqual((p/'fixture').read_text(),'original cache')
    def test_f9_file_unlinked_then_rename_failure_resumes(self):
        engine=setup.Installer(self.home); p=self.home/'.codex/config.toml'; p.parent.mkdir(); p.write_text('original')
        engine.write('.codex/config.toml',b'installed')
        with patch('setup_symlinks.os.rename',side_effect=OSError('synthetic before rename')):
            with self.assertRaises(OSError): engine.uninstall()
        self.assertFalse(p.exists()); setup.Installer(self.home).uninstall(); self.assertEqual(p.read_text(),'original')
    def codex_restore(self,enabled=True):
        engine=setup.Installer(self.home); p=self.home/'.codex/config.toml'; p.parent.mkdir(exist_ok=True)
        p.write_text('# synthetic original\n[plugins."superpowers@openai-curated-remote"]\nenabled = '+str(enabled).lower()+'\n'); p.chmod(0o640)
        original={'_id':'superpowers@openai-curated-remote','version':'6.4.2','enabled':enabled,'source':{'source':'url','url':'https://github.com/obra/superpowers.git','sha':'1'*40}}
        flags={'created_plugin':False,'created_marketplace':False,'removed':True,'original_marketplaces':[],'original_plugins':[original]}
        engine.state['native']['codex']=flags; engine.save()
        native=NativePlugins(engine,ROOT,self.lock); current=[]; calls=[]
        flags['original_registry']={'.codex/config.toml':native.registry_identity(p)}; engine.save()
        def run(target,args,cwd=None):
            calls.append(args)
            if args[:3]==['plugin','marketplace','list']: return {'marketplaces':[]}
            if args[:2]==['plugin','list']:
                return {'installed':[dict(r,pluginId=r['_id'],enabled='enabled = true' in p.read_text()) for r in current]}
            if args[:2]==['plugin','add']:
                current.append(dict(original)); p.write_text('enabled = true\n'); return {}
            raise AssertionError(args)
        native.run=run
        return engine,native,p,original,current,calls
    def test_f10_missing_curated_registration_cli_add_and_exact_config_metadata(self):
        engine,native,p,original,current,calls=self.codex_restore(); before=(p.read_bytes(),p.stat().st_mode,p.stat().st_mtime_ns)
        native.verify_restored()
        self.assertIn(['plugin','add',original['_id'],'--json'],calls)
        self.assertEqual(before,(p.read_bytes(),p.stat().st_mode,p.stat().st_mtime_ns)); self.assertFalse(engine.state['native'])
    def test_f10_original_disabled_state_preserved_after_add(self):
        engine,native,p,original,current,calls=self.codex_restore(False); native.verify_restored()
        self.assertIn('enabled = false',p.read_text()); self.assertFalse(engine.state['native'])
    def test_f10_wrong_version_or_commit_retains_journal_without_replacing(self):
        for key in ('version','source'):
            with self.subTest(key=key):
                # Reset only this synthetic HOME.
                p=self.home/'.codex/config.toml'
                if p.exists(): p.unlink()
                state=self.home/'.agent-skills-setup/state.json'
                if state.exists(): state.unlink()
                engine,native,p,original,current,calls=self.codex_restore()
                observed=dict(original); observed[key]='changed' if key=='version' else dict(original['source'],sha='2'*40)
                current.append(observed); before=p.read_bytes()
                with self.assertRaisesRegex(ValueError,'version/enabled/source'): native.verify_restored()
                self.assertEqual(p.read_bytes(),before); self.assertTrue(engine.state['native']['codex']['original_plugins'])
                self.assertFalse(any(c[:2]==['plugin','add'] for c in calls))
                for q in (engine.state_dir/'native-restore').glob('*'): q.unlink()
    def test_f10_failed_cli_restore_then_new_process_resume(self):
        engine,native,p,original,current,calls=self.codex_restore(); run=native.run
        def fail(target,args,cwd=None):
            if args[:2]==['plugin','add']: p.write_text('partial CLI config'); raise ValueError('synthetic native failure')
            return run(target,args,cwd)
        native.run=fail; before=p.read_bytes()
        with self.assertRaisesRegex(ValueError,'synthetic'): native.verify_restored()
        self.assertEqual(p.read_bytes(),before)
        resumed=NativePlugins(setup.Installer(self.home),ROOT,self.lock); resumed.run=run
        resumed.uninstall(False); resumed.e.uninstall(); resumed.verify_restored()
        self.assertFalse(resumed.e.state['native'])
    def test_f10_modified_user_config_on_resume_refused(self):
        engine,native,p,original,current,calls=self.codex_restore(); native.restoration_registries('codex',engine.state['native']['codex'])
        p.write_text('user modification'); before=snapshot(self.home)
        with self.assertRaisesRegex(ValueError,'changed by user'): native.verify_restored()
        self.assertEqual(before,snapshot(self.home)); self.assertFalse(calls)
    def test_f10_user_config_edit_before_first_snapshot_refused(self):
        engine,native,p,original,current,calls=self.codex_restore()
        p.write_text('user change after file rollback'); before=snapshot(self.home)
        with self.assertRaisesRegex(ValueError,'changed by user'): native.verify_restored()
        self.assertEqual(before,snapshot(self.home)); self.assertFalse(calls)
    def test_f10_user_config_mode_edit_before_first_snapshot_refused(self):
        engine,native,p,original,current,calls=self.codex_restore()
        p.chmod(0o600); before=snapshot(self.home)
        with self.assertRaisesRegex(ValueError,'changed by user'): native.verify_restored()
        self.assertEqual(before,snapshot(self.home)); self.assertFalse(calls)
    def test_f10_old_journal_without_plugin_expectations_fails_closed(self):
        engine,native,p,original,current,calls=self.codex_restore()
        del engine.state['native']['codex']['original_plugins']; engine.save()
        with self.assertRaisesRegex(ValueError,'old Codex journal'): native.verify_restored()
        self.assertTrue(engine.state['native']['codex']); self.assertFalse(any(c[:2]==['plugin','add'] for c in calls))
    def test_f9_marketplace_expectations_survive_file_restore_failure(self):
        engine,p=self.moved_cache(); engine.state['native']['claude']={'created_plugin':False,'created_marketplace':False,'original_marketplaces':[{'name':'original','location':'fixture'}]}; engine.save()
        native=NativePlugins(engine,ROOT,self.lock); native.run=lambda target,args,cwd=None: []
        native.uninstall(False)
        with patch('setup_symlinks.os.rename',side_effect=OSError('synthetic')):
            with self.assertRaises(OSError): engine.uninstall()
        resumed=setup.Installer(self.home)
        self.assertEqual(resumed.state['native']['claude']['original_marketplaces'],[{'name':'original','location':'fixture'}])
        self.assertTrue(resumed.state['native']['claude']['removed'])

if __name__=='__main__': unittest.main(verbosity=2)
