"""F11/F12 protocol/synthetic safety fixtures, not native CLI evidence."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from test_setup import ROOT, snapshot
import setup_symlinks as setup

class RegeneratedCacheTests(unittest.TestCase):
    def setUp(self):
        base=ROOT/'.test-tmp'; base.mkdir(exist_ok=True)
        self.tmp=tempfile.TemporaryDirectory(dir=base)
        self.base=Path(self.tmp.name); self.home=self.base/'home'; self.home.mkdir()
    def tearDown(self): self.tmp.cleanup()
    def runtime_repo(self):
        root=self.base/'repo'; root.mkdir()
        subprocess.run(['git','init','-q',str(root)],check=True)
        (root/'.gitignore').write_text('.venv/\n')
        skill=root/'sources/skills/paper-banana-claude'; (skill/'engine').mkdir(parents=True)
        (skill/'SKILL.md').write_text('synthetic original')
        return root,skill

    def cache(self,target='claude'):
        e=setup.Installer(self.home)
        p=self.home/('.'+target)/'plugins/cache/claude-plugins-official/superpowers'
        p.mkdir(parents=True); (p/'original').write_text('original private fixture')
        rel=str(p.relative_to(self.home))
        e.move(rel,cache_selector='superpowers@claude-plugins-official')
        backup=e.state_dir/e.record(rel)['backup']
        metadata='.claude-plugin' if target=='claude' else '.codex-plugin'
        m=p/'5bf4e7801107'/metadata/'plugin.json'; m.parent.mkdir(parents=True)
        m.write_text(json.dumps({'name':'superpowers','version':'6.4.1'}))
        (p/'5bf4e7801107/user-note').write_text('preserve user modifications')
        return e,p,backup,m

    def test_f11_both_harness_quarantine_original_restore_and_second_noop(self):
        for target in ('claude','codex'):
            with self.subTest(target=target):
                e,p,b,m=self.cache(target); original=snapshot(b); generated=snapshot(p)
                e=setup.Installer(self.home); e.quarantine_caches()
                self.assertEqual(snapshot(b),original)
                q=e.state_dir/e.state['quarantine'][-1]; self.assertEqual(snapshot(q),generated)
                self.assertFalse(p.exists())
                e.uninstall(); self.assertEqual(snapshot(p),original); self.assertEqual(snapshot(q),generated)
                before=snapshot(self.home); setup.Installer(self.home).uninstall()
                self.assertEqual(before,snapshot(self.home))

    def test_f11_dry_run_changes_neither_payload_nor_journal(self):
        e,p,b,m=self.cache(); before=snapshot(self.home)
        setup.Installer(self.home,True).quarantine_caches()
        setup.Installer(self.home,True).uninstall()
        self.assertEqual(before,snapshot(self.home))

    def test_f11_legacy_unproven_tombstone_keeps_fail_closed(self):
        e,p,b,m=self.cache(); del e.state['records'][0]['retired_cache']; e.save()
        before=snapshot(self.home)
        with self.assertRaisesRegex(ValueError,'changed by user'): setup.Installer(self.home)
        self.assertEqual(before,snapshot(self.home))

    def test_f11_unknown_leaf_or_wrong_metadata_refused_without_writes(self):
        e,p,b,m=self.cache()
        original=m.read_bytes()
        for bad in ({'name':'unrelated','version':'1'}, {'name':'superpowers'}, []):
            with self.subTest(payload=bad):
                m.write_text(json.dumps(bad)); before=snapshot(self.home)
                with self.assertRaises(ValueError): setup.Installer(self.home)
                self.assertEqual(before,snapshot(self.home))
        m.write_bytes(original); (p/'user-file').write_text('unrelated')
        before=snapshot(self.home)
        with self.assertRaises(ValueError): setup.Installer(self.home)
        self.assertEqual(before,snapshot(self.home))

    def test_f11_symlink_leaf_revision_manifest_or_parent_refused(self):
        for location in ('leaf','revision','manifest','parent'):
            with self.subTest(location=location):
                # Each scenario uses a fresh synthetic HOME; never real HOME.
                self.tearDown(); self.setUp()
                e,p,b,m=self.cache()
                q=p if location=='leaf' else p/'5bf4e7801107' if location=='revision' else m if location=='manifest' else p.parent
                q.rename(self.base/'saved'); q.symlink_to(self.base/'saved',target_is_directory=q!=m)
                before=snapshot(self.home)
                with self.assertRaises(ValueError): setup.Installer(self.home)
                self.assertEqual(before,snapshot(self.home))

    def test_f11_selector_mismatch_pin_and_missing_backup_refused(self):
        e,p,b,m=self.cache(); record=e.state['records'][0]
        for selector in ('other@claude-plugins-official','superpowers@ssot-pinned','superpowers@../escape','superpowers@different'):
            record['retired_cache']=selector; e.save(); before=snapshot(self.home)
            with self.assertRaises(ValueError): setup.Installer(self.home)
            self.assertEqual(before,snapshot(self.home))
        record['retired_cache']='superpowers@claude-plugins-official'; e.save()
        b.rename(self.base/'saved-backup'); before=snapshot(self.home)
        with self.assertRaisesRegex(ValueError,'missing original'): setup.Installer(self.home)
        self.assertEqual(before,snapshot(self.home))

    def test_f11_quarantine_collision_and_symlink_refused(self):
        e,p,b,m=self.cache(); q=e.state_dir/'quarantine/0'; q.mkdir(parents=True); (q/'user').write_text('keep')
        before=snapshot(self.home)
        with self.assertRaisesRegex(ValueError,'already exists'): e.quarantine_caches()
        self.assertEqual(before,snapshot(self.home))
        q.rename(self.base/'saved'); q.symlink_to(self.base/'saved'); before=snapshot(self.home)
        with self.assertRaisesRegex(ValueError,'symlink'): e.quarantine_caches()
        self.assertEqual(before,snapshot(self.home))

    def test_f11_quarantine_interruption_before_and_after_rename_resumes(self):
        for after in (False,True):
            with self.subTest(after_rename=after):
                self.tearDown(); self.setUp()
                e,p,b,m=self.cache(); generated=snapshot(p); original=snapshot(b); real=os.rename
                def interrupted(a,z):
                    if after: real(a,z)
                    raise OSError('synthetic interrupted quarantine')
                with patch('setup_symlinks.os.rename',side_effect=interrupted):
                    with self.assertRaises(OSError): e.quarantine_caches()
                self.assertIn('quarantining',e.state['records'][0])
                resumed=setup.Installer(self.home); resumed.uninstall()
                self.assertEqual(snapshot(p),original)
                self.assertEqual(snapshot(resumed.state_dir/resumed.state['quarantine'][-1]),generated)
                self.assertFalse(resumed.state['records'])

    def test_f11_pending_identity_edit_and_path_escape_refused(self):
        e,p,b,m=self.cache()
        with patch('setup_symlinks.os.rename',side_effect=OSError('synthetic')):
            with self.assertRaises(OSError): e.quarantine_caches()
        pending=e.state['records'][0]['quarantining']; pending['path']='../escape'; e.save(); before=snapshot(self.home)
        with self.assertRaisesRegex(ValueError,'unsafe quarantine'): setup.Installer(self.home)
        self.assertEqual(before,snapshot(self.home))
        pending['path']='quarantine/0'; e.save(); (p/'unexpected').write_text('keep'); before=snapshot(self.home)
        with self.assertRaisesRegex(ValueError,'changed by user'): setup.Installer(self.home)
        self.assertEqual(before,snapshot(self.home))

    def test_f11_original_backup_symlink_refused(self):
        e,p,b,m=self.cache(); b.rename(self.base/'saved-backup'); b.symlink_to(self.base/'saved-backup')
        before=snapshot(self.home)
        with self.assertRaisesRegex(ValueError,'symlink'): setup.Installer(self.home)
        self.assertEqual(before,snapshot(self.home))

    def test_f11_quarantined_cache_restore_interruption_resumes(self):
        for after in (False,True):
            with self.subTest(after_restore_rename=after):
                self.tearDown(); self.setUp()
                e,p,b,m=self.cache(); original=snapshot(b); generated=snapshot(p)
                e.quarantine_caches(); q=e.state_dir/e.state['quarantine'][-1]; real=os.rename
                def interrupted(a,z):
                    if after: real(a,z)
                    raise OSError('synthetic interrupted original restore')
                with patch('setup_symlinks.os.rename',side_effect=interrupted):
                    with self.assertRaises(OSError): e.uninstall()
                setup.Installer(self.home).uninstall()
                self.assertEqual(snapshot(p),original); self.assertEqual(snapshot(q),generated)

    def test_f11_pending_quarantine_reappeared_leaf_refused(self):
        e,p,b,m=self.cache(); real=os.rename
        def interrupted(a,z): real(a,z); raise OSError('synthetic after rename')
        with patch('setup_symlinks.os.rename',side_effect=interrupted):
            with self.assertRaises(OSError): e.quarantine_caches()
        p.mkdir(); (p/'user-edit').write_text('preserve'); before=snapshot(self.home)
        with self.assertRaisesRegex(ValueError,'changed by user'): setup.Installer(self.home)
        self.assertEqual(before,snapshot(self.home))

    def test_f11_modified_managed_config_blocks_before_quarantine(self):
        e,p,b,m=self.cache(); e.write('.claude/settings.json',b'{}'); (self.home/'.claude/settings.json').write_text('user edit')
        before=snapshot(self.home)
        with self.assertRaisesRegex(ValueError,'changed by user'): setup.Installer(self.home)
        self.assertEqual(before,snapshot(self.home))

    def test_f11_no_runtime_payload_read_for_preservation(self):
        e,p,b,m=self.cache()
        with patch.object(Path,'read_bytes',side_effect=AssertionError('payload read')):
            resumed=setup.Installer(self.home); resumed.quarantine_caches(); resumed.uninstall()
        self.assertTrue((p/'original').exists())

    def test_f12_all_exact_ignored_package_bytecode_is_opaque(self):
        root,skill=self.runtime_repo(); (root/'.gitignore').write_text('__pycache__/\n')
        for rel in setup.LOCAL_RUNTIMES-{setup.LOCAL_RUNTIME}:
            p=root/rel; p.mkdir(parents=True); (p/'opaque.pyc').write_bytes(b'synthetic private bytecode')
        with patch.object(setup,'ROOT',root),patch.object(Path,'read_bytes',side_effect=AssertionError('runtime read')):
            self.assertEqual(setup.source(str(skill.relative_to(root))),skill)
        for rel in setup.LOCAL_RUNTIMES:
            with self.assertRaises(ValueError): setup.relative(rel)

    def test_f12_forced_tracked_or_not_ignored_bytecode_refused(self):
        root,skill=self.runtime_repo(); (root/'.gitignore').write_text('__pycache__/\n')
        p=skill/'engine/mcp_server/__pycache__'; p.mkdir(parents=True); f=p/'test.pyc'; f.write_bytes(b'synthetic')
        subprocess.run(['git','-C',str(root),'add','-f',str(f)],check=True)
        with patch.object(setup,'ROOT',root),self.assertRaisesRegex(ValueError,'untracked'): setup.source(str(skill.relative_to(root)))
        subprocess.run(['git','-C',str(root),'rm','--cached','-f',str(f)],check=True,capture_output=True)
        (root/'.gitignore').write_text('')
        with patch.object(setup,'ROOT',root),self.assertRaisesRegex(ValueError,'ignored'): setup.source(str(skill.relative_to(root)))

    def test_f12_symlink_file_parent_and_other_private_paths_refused(self):
        root,skill=self.runtime_repo(); (root/'.gitignore').write_text('__pycache__/\n')
        package=skill/'engine/mcp_server'; package.mkdir(); p=package/'__pycache__'
        p.symlink_to(self.home)
        with patch.object(setup,'ROOT',root),self.assertRaises(ValueError): setup.source(str(skill.relative_to(root)))
        p.unlink(); p.write_text('not directory')
        with patch.object(setup,'ROOT',root),self.assertRaises(ValueError): setup.source(str(skill.relative_to(root)))
        p.unlink(); package.rmdir(); package.symlink_to(self.home)
        with patch.object(setup,'ROOT',root),self.assertRaises(ValueError): setup.source(str(skill.relative_to(root)))
        package.unlink()
        for rel in ('__pycache__','engine/unknown/__pycache__','engine/mcp_server/cache','engine/mcp_server/auth.json','engine/mcp_server/auto-code'):
            p=skill/rel; p.parent.mkdir(parents=True,exist_ok=True); p.write_text('rejected')
            with patch.object(setup,'ROOT',root),self.assertRaises(ValueError): setup.source(str(skill.relative_to(root)))
            p.unlink()

if __name__=='__main__': unittest.main(verbosity=2)
