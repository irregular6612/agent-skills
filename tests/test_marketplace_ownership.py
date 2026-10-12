"""Shared-registry fixtures. Native protocol mocks are not live CLI evidence."""
import copy
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from test_setup import ROOT, snapshot
import setup_symlinks as setup
import setup_marketplaces as markets
from setup_plugins import NativePlugins


class MarketplaceOwnershipTests(unittest.TestCase):
    def setUp(self):
        base=ROOT/'.test-tmp'; base.mkdir(exist_ok=True)
        self.tmp=tempfile.TemporaryDirectory(dir=base)
        self.home=__import__('pathlib').Path(self.tmp.name)/'home'; self.home.mkdir()
        self.path=self.home/markets.REL; self.path.parent.mkdir(parents=True)
        self.user={'source':{'source':'github','repo':'example/user'},'installLocation':'/fixture/user','lastUpdated':'old','extra':{'keep':1}}
        self.old={'source':{'source':'directory','path':'/fixture/old'},'installLocation':'/fixture/old','lastUpdated':'original','autoUpdate':False,'unknown':{'keep':2}}
        self.original={'user':copy.deepcopy(self.user),'retired':copy.deepcopy(self.old)}
        self.put(self.original)
    def tearDown(self): self.tmp.cleanup()
    def put(self, data): self.path.write_bytes(setup.encode(data))
    def get(self): return markets.read(self.path)
    def installed(self, preexisting=False, retired=True):
        if preexisting:
            data=self.get(); data['ssot-pinned']=dict(self.old); self.put(data)
        e=setup.Installer(self.home)
        r=markets.capture(e,['retired'] if retired else [],ROOT/'dependencies/marketplaces/claude',not preexisting)
        data=self.get()
        if not preexisting: data['ssot-pinned']=dict(r['installed']['ssot-pinned'],lastUpdated='native',autoUpdate=True)
        if retired: del data['retired']
        self.put(data); markets.finalize(e)
        return e,r
    def command(self,*args,code=0):
        result=subprocess.run([sys.executable,str(ROOT/'tools/setup_symlinks.py'),*args],env=dict(os.environ,HOME=str(self.home),CLAUDE_CONFIG_DIR=str(self.home/'.claude'),CODEX_HOME=str(self.home/'.codex'),PYTHONDONTWRITEBYTECODE='1'),text=True,capture_output=True)
        self.assertEqual(result.returncode,code,result.stdout+result.stderr)
        return result
    def test_timestamp_only_passes_and_is_preserved(self):
        self.installed(); data=self.get(); data['ssot-pinned']['lastUpdated']='new'; data['user']['lastUpdated']='newer'; self.put(data)
        before=snapshot(self.home); self.command('--assets-only','--dry-run'); self.assertEqual(before,snapshot(self.home))
        e=setup.Installer(self.home); e.uninstall()
        self.assertEqual(self.get()['user'],data['user']); self.assertEqual(self.get()['retired'],self.old)
    def test_whitespace_only_passes_without_rewriting(self):
        self.installed(); self.path.write_text(json.dumps(self.get(),separators=(',',':')))
        before=snapshot(self.home); self.command('--assets-only','--dry-run'); self.assertEqual(before,snapshot(self.home))
    def test_owned_source_change_refuses_install_and_uninstall_without_writes(self):
        self.installed(); data=self.get(); data['ssot-pinned']['source']['path']='/user/changed'; self.put(data)
        before=snapshot(self.home)
        for args in [('--assets-only','--dry-run'),('--assets-only',),('--uninstall','--assets-only')]:
            self.command(*args,code=2); self.assertEqual(before,snapshot(self.home))
    def test_user_added_registration_survives_install_and_uninstall(self):
        self.installed(); data=self.get(); data['new-user']=dict(self.user,unknown='new'); self.put(data)
        self.command('--assets-only'); self.command('--assets-only'); self.command('--assets-only','--uninstall')
        result=self.get(); self.assertEqual(result['new-user'],data['new-user']); self.assertEqual(result['user'],data['user']); self.assertNotIn('ssot-pinned',result)
    def test_unknown_and_runtime_fields_on_preexisting_entry_survive(self):
        self.installed(preexisting=True); data=self.get(); data['ssot-pinned'].update(lastUpdated='new',autoUpdate=True,newField={'payload':[1,2]}); data['ssot-pinned']['source']['future']='keep'; self.put(data)
        e=setup.Installer(self.home); e.uninstall(); self.assertEqual(self.get()['ssot-pinned'],data['ssot-pinned'])
    def test_removed_created_entry_runtime_metadata_is_archived(self):
        self.installed(); data=self.get(); data['ssot-pinned']['future']='retain-in-archive'; self.put(data)
        e=setup.Installer(self.home); e.uninstall()
        self.assertEqual(e.state['marketplace_archive'][0]['ssot-pinned'],data['ssot-pinned'])
    def test_retired_name_re_registered_refuses(self):
        self.installed(); data=self.get(); data['retired']=self.old; self.put(data); before=snapshot(self.home)
        with self.assertRaisesRegex(ValueError,'changed by user'): setup.Installer(self.home)
        self.assertEqual(before,snapshot(self.home))
    def test_owned_install_location_change_refuses(self):
        self.installed(); data=self.get(); data['ssot-pinned']['installLocation']='/changed'; self.put(data)
        with self.assertRaisesRegex(ValueError,'changed by user'): setup.Installer(self.home)
    def test_removed_owned_entry_refuses(self):
        self.installed(); data=self.get(); del data['ssot-pinned']; self.put(data)
        with self.assertRaisesRegex(ValueError,'changed by user'): setup.Installer(self.home)
    def test_backup_tamper_refuses(self):
        e,r=self.installed(); (e.state_dir/r['backup']).write_text('{}')
        with self.assertRaisesRegex(ValueError,'backup changed'): setup.Installer(self.home)
    def test_duplicate_key_and_bad_shape_refuse(self):
        self.installed()
        for data in ['{"user":{},"user":{}}','[]','{"user":2}']:
            self.path.write_text(data)
            with self.assertRaises(ValueError): setup.Installer(self.home)
    def test_symlink_registry_refuses_without_reading_target(self):
        self.installed(); self.path.unlink(); self.path.symlink_to('/does/not/exist')
        with self.assertRaisesRegex(ValueError,'unsafe'): setup.Installer(self.home)
    def test_pending_native_operation_rolls_back_partial_entry_set(self):
        e=setup.Installer(self.home); r=markets.capture(e,['retired'],ROOT/'dependencies/marketplaces/claude',True)
        data=self.get(); data['ssot-pinned']=dict(r['installed']['ssot-pinned']); self.put(data)
        # Pin add succeeded, retirement has not. This is a durable native intent.
        self.command('--assets-only',code=2)
        resumed=setup.Installer(self.home); resumed.uninstall(); self.assertEqual(self.get(),self.original)
    def interrupted_restore(self,after_replace):
        e,r=self.installed(); real=os.replace
        def replace(src,dst):
            if dst==self.path:
                if after_replace: real(src,dst)
                raise OSError('synthetic registry replace interruption')
            return real(src,dst)
        with patch('setup_marketplaces.os.replace',side_effect=replace),self.assertRaises(OSError): e.uninstall()
        # Resume via a new interpreter, not the old in-memory journal.
        self.command('--uninstall','--assets-only')
        self.assertEqual(self.get(),self.original)
        self.assertFalse(self.path.with_name(self.path.name+'.ssot-new').exists())
    def test_restore_interruption_before_replace_resumes(self): self.interrupted_restore(False)
    def test_restore_interruption_after_replace_resumes(self): self.interrupted_restore(True)
    def test_unknown_temp_is_not_overwritten(self):
        e,r=self.installed(); temp=self.path.with_name(self.path.name+'.ssot-new'); temp.write_text('user file')
        before=self.path.read_bytes()
        with self.assertRaisesRegex(ValueError,'unrecognized'): e.uninstall()
        self.assertEqual(temp.read_text(),'user file'); self.assertEqual(self.path.read_bytes(),before)
    def test_external_write_before_replace_is_preserved(self):
        e,r=self.installed(); real=__import__('pathlib').Path.read_bytes; calls=[]
        def read(p):
            if p==self.path:
                calls.append(p)
                if len(calls)==4:
                    data=json.loads(real(p)); data['concurrent']=self.user; p.write_bytes(setup.encode(data))
            return real(p)
        with patch.object(__import__('pathlib').Path,'read_bytes',read),self.assertRaisesRegex(ValueError,'concurrently'): e.uninstall()
        self.assertIn('concurrent',self.get())
    def legacy(self, installed=None):
        # Public legacy API creates hash-only state. No fixture state rewriting.
        e=setup.Installer(self.home)
        final=copy.deepcopy(self.original) if installed is None else installed
        final.pop('retired',None)
        final['ssot-pinned']={'source':{'source':'directory','path':str(ROOT/'dependencies/marketplaces/claude')},'installLocation':str(ROOT/'dependencies/marketplaces/claude'),'lastUpdated':'installed'}
        e.write(markets.REL,setup.encode(final))
        e.state['native']['claude']={'created_marketplace':True,'created_plugin':False,'retired_marketplaces':['retired'],'original_marketplaces':[]}; e.save()
        return e,final
    def test_legacy_exact_hash_migrates_in_memory_dry_run_without_writes(self):
        self.legacy(); before=snapshot(self.home); e=setup.Installer(self.home,True)
        self.assertTrue(e.marketplace_migrated); self.assertEqual(before,snapshot(self.home)); self.command('--assets-only','--dry-run'); self.assertEqual(before,snapshot(self.home))
    def test_legacy_timestamp_witness_migrates_and_keeps_old_record(self):
        old,data=self.legacy(); legacy=copy.deepcopy(old.record(markets.REL)); data['user']['lastUpdated']='runtime'; self.put(data)
        before=snapshot(self.home); e=setup.Installer(self.home)
        self.assertEqual(before,snapshot(self.home)); r=e.record(markets.REL)
        self.assertEqual(r['legacy'],legacy); self.assertEqual(r['witness']['changed_paths'],['user.lastUpdated']); e.save()
        self.assertEqual(setup.Installer(self.home).record(markets.REL)['kind'],'marketplaces')
    def test_legacy_timestamp_witness_changes_only_selected_json_path(self):
        old,data=self.legacy(); data['user']['lastUpdated']='runtime'; data['user']['extra']['same']='runtime'
        # Unknown field addition must not be normalized away.
        self.put(data); before=snapshot(self.home)
        with self.assertRaisesRegex(ValueError,'historical hash witness'): setup.Installer(self.home)
        self.assertEqual(before,snapshot(self.home))
    def test_legacy_unproven_source_or_user_addition_or_spacing_refuses(self):
        old,data=self.legacy(); installed_bytes=self.path.read_bytes()
        for change in ['source','addition','whitespace']:
            data=json.loads(installed_bytes)
            if change=='source': data['ssot-pinned']['source']['path']='/different'
            if change=='addition': data['new']=self.user
            self.put(data)
            if change=='whitespace': self.path.write_text(json.dumps(data))
            before=snapshot(self.home)
            with self.assertRaisesRegex(ValueError,'historical hash witness'): setup.Installer(self.home)
            self.assertEqual(before,snapshot(self.home))
    def test_legacy_ssot_wrong_catalog_even_exact_hash_refuses(self):
        old,data=self.legacy(); self.path.write_bytes(setup.encode(data))
        # New legacy fixture with a wrong pin identity; use write() rather than state edit.
        data['ssot-pinned']['source']['path']='/bad'; old.write(markets.REL,setup.encode(data))
        with self.assertRaisesRegex(ValueError,'ownership cannot be proven'): setup.Installer(self.home)
    def test_readback_does_not_adopt_unexpected_native_source(self):
        e=setup.Installer(self.home); r=markets.capture(e,[],ROOT/'dependencies/marketplaces/claude',True)
        data=self.get(); data['ssot-pinned']=dict(r['installed']['ssot-pinned']); data['ssot-pinned']['installLocation']='/bad'; self.put(data)
        native=NativePlugins(e,ROOT,json.loads((ROOT/'dependencies/lock.yaml').read_text())); before=copy.deepcopy(r['installed'])
        native.update_registry_hashes('claude'); self.assertEqual(r['installed'],before)
        with self.assertRaisesRegex(ValueError,'readback failed'): markets.finalize(e)

    def test_retained_audit_backups_do_not_break_reinstall(self):
        e,r=self.installed(); original_backup=e.state_dir/r['backup']; before=original_backup.read_bytes()
        e.uninstall(); e2,r2=self.installed()
        self.assertNotEqual(r['backup'],r2['backup']); self.assertEqual(original_backup.read_bytes(),before)
        e2.uninstall(); self.assertEqual(len(e2.state['marketplace_journal_archive']),2)

    def test_legacy_journal_survives_semantic_uninstall_in_archive(self):
        old,data=self.legacy(); legacy=copy.deepcopy(old.record(markets.REL))
        e=setup.Installer(self.home); e.uninstall()
        self.assertEqual(e.state['marketplace_journal_archive'][0]['legacy'],legacy)
        self.assertTrue((e.state_dir/legacy['backup']).is_file())

    def test_native_command_guard_refuses_unexpected_source_without_adoption(self):
        e,r=self.installed(); native=NativePlugins(e,ROOT,json.loads((ROOT/'dependencies/lock.yaml').read_text()))
        expected=copy.deepcopy(r['installed'])
        def unexpected(*args,**kwargs):
            data=self.get(); data['ssot-pinned']['source']['path']='/native-wrong'; self.put(data)
            return subprocess.CompletedProcess(args[0],0,'[]','')
        with patch('setup_plugins.subprocess.run',side_effect=unexpected),self.assertRaisesRegex(ValueError,'owned marketplace source'):
            native.run('claude',['plugin','list','--json'])
        self.assertEqual(r['installed'],expected)

    def test_native_mutation_dropped_unknown_fields_are_restored(self):
        e,r=self.installed(); native=NativePlugins(e,ROOT,json.loads((ROOT/'dependencies/lock.yaml').read_text()))
        data=self.get(); data['user']['source']['future']='keep'; self.put(data)
        def native_drop(*args,**kwargs):
            data=self.get(); del data['user']['extra']; del data['user']['source']['future']; data['user']['lastUpdated']='native-refresh'; self.put(data)
            return subprocess.CompletedProcess(args[0],0,'{}','')
        with patch('setup_plugins.subprocess.run',side_effect=native_drop): native.run('claude',['plugin','install','fixture','--json'])
        self.assertEqual(self.get()['user']['extra'],{'keep':1}); self.assertEqual(self.get()['user']['source']['future'],'keep')
        self.assertEqual(self.get()['user']['lastUpdated'],'native-refresh'); self.assertNotIn('native_overlay',r)

    def test_native_overlay_interruption_recovers_in_new_process(self):
        e,r=self.installed(); native=NativePlugins(e,ROOT,json.loads((ROOT/'dependencies/lock.yaml').read_text()))
        def native_crash(*args,**kwargs):
            data=self.get(); del data['user']['extra']; self.put(data); raise OSError('synthetic native interruption')
        with patch('setup_plugins.subprocess.run',side_effect=native_crash),self.assertRaises(OSError): native.run('claude',['plugin','install','fixture','--json'])
        self.command('--assets-only',code=2); self.command('--uninstall','--assets-only')
        self.assertEqual(self.get()['user']['extra'],{'keep':1})

    def test_native_overlay_never_adopts_unrelated_source_change(self):
        e,r=self.installed(); native=NativePlugins(e,ROOT,json.loads((ROOT/'dependencies/lock.yaml').read_text()))
        def native_change(*args,**kwargs):
            data=self.get(); data['user']['source']['repo']='example/changed'; self.put(data)
            return subprocess.CompletedProcess(args[0],0,'{}','')
        with patch('setup_plugins.subprocess.run',side_effect=native_change),self.assertRaisesRegex(ValueError,'unrelated marketplace source'):
            native.run('claude',['plugin','install','fixture','--json'])
        self.assertIn('native_overlay',r); self.assertEqual(self.get()['user']['source']['repo'],'example/changed')


if __name__=='__main__': unittest.main(verbosity=2)
