"""F13 protocol boundaries; live_inventory_gap.py supplies actual CLI evidence."""
import contextlib
import io
import json
import os
import unittest
from unittest.mock import patch
import test_regressions as regressions
from test_final_boundaries import metadata
from test_setup import ROOT
import setup_symlinks as setup
from setup_plugins import NativePlugins


class InventoryGapTests(unittest.TestCase):
    setUp=regressions.RegressionTests.setUp
    tearDown=regressions.RegressionTests.tearDown
    config=regressions.RegressionTests.config

    def fixture(self,selector='superpowers@unavailable-local'):
        self.config('[plugins."'+selector+'"]\nenabled = true\n')
        plugin,market=selector.split('@')
        p=self.home/'.codex/plugins/cache'/market/plugin/'1/.codex-plugin/plugin.json'
        p.parent.mkdir(parents=True)
        p.write_text(json.dumps({'name':plugin,'version':'1.0.0'}))
        return NativePlugins(setup.Installer(self.home),ROOT,self.lock)

    def test_inventory_gap_refuses_full_setup_before_assets_journal_and_native_mutations(self):
        self.fixture(); before=metadata(self.home); calls=[]
        def run(native,target,args,cwd=None):
            calls.append((target,args))
            self.assertEqual((target,args),('codex',['plugin','list','--json']))
            return {'installed':[]}
        with patch.object(NativePlugins,'run',run),patch('setup_plugins.shutil.which',return_value='/fixture/native'),patch.dict(os.environ,HOME=str(self.home)),patch('sys.argv',['setup']):
            with self.assertRaisesRegex(ValueError,'absent from native inventory; preserved config/cache'):
                setup.main()
        self.assertEqual(calls,[('codex',['plugin','list','--json'])])
        self.assertEqual(before,metadata(self.home))
        self.assertFalse((self.home/'.claude').exists())
        self.assertFalse((self.home/'.agent-skills-setup').exists())

    def test_inventory_visible_retirement_is_allowed(self):
        native=self.fixture()
        before=metadata(self.home)
        native.verify_local_inventory('codex',[{'_id':'superpowers@unavailable-local'}])
        self.assertEqual(before,metadata(self.home))

    def test_pin_and_unrelated_metadata_do_not_need_retirement_ownership(self):
        native=self.fixture('superpowers@ssot-pinned')
        native.verify_local_inventory('codex',[])
        native=self.fixture('unrelated@unavailable-local')
        native.verify_local_inventory('codex',[])

    def test_disabled_and_generated_retirement_candidates_also_refuse(self):
        native=self.fixture()
        self.config('[plugins."superpowers@unavailable-local"]\nenabled = false\n')
        with self.assertRaisesRegex(ValueError,'superpowers@unavailable-local'):
            native.verify_local_inventory('codex',[])
        self.config('[plugins."bagjuhyeon-agent-ssot@generated-local-cache"]\nenabled = true\n')
        with self.assertRaisesRegex(ValueError,'bagjuhyeon-agent-ssot@generated-local-cache'):
            native.verify_local_inventory('codex',[])

    def test_dry_metadata_probe_does_not_invoke_native_cli_or_write(self):
        native=self.fixture(); native.e.dry=True; before=metadata(self.home)
        with patch('setup_plugins.shutil.which',return_value='/fixture/native'),patch.object(native,'run',side_effect=AssertionError('native read in dry run')),contextlib.redirect_stdout(io.StringIO()):
            native.preflight(False); native.install(False)
        self.assertEqual(before,metadata(self.home))

    def test_direct_install_refuses_even_when_pin_is_already_exact(self):
        native=self.fixture(); native.spec={'codex':native.spec['codex']}; spec=native.spec['codex']
        records=[{'_id':spec['id'],'enabled':True,'version':spec['version'],'source':{'sha':spec['commit'],'url':spec['repository']}}]
        before=metadata(self.home)
        with patch.object(native,'plugins',return_value=records),patch.object(native,'marketplaces',side_effect=AssertionError('must refuse before mutation planning')):
            with self.assertRaisesRegex(ValueError,'absent from native inventory'):
                native.install(False)
        self.assertEqual(before,metadata(self.home))

    def test_symlink_cache_is_not_promoted_to_owned_retirement(self):
        native=self.fixture(); cache=self.home/'.codex/plugins/cache/unavailable-local/superpowers'
        moved=cache.with_name('original'); cache.rename(moved); cache.symlink_to(moved)
        before=metadata(self.home)
        with self.assertRaisesRegex(ValueError,'symlink'):
            native.verify_local_inventory('codex',[])
        self.assertEqual(before,metadata(self.home))


if __name__=='__main__': unittest.main(verbosity=2)
