"""F5/F6 boundaries. Live native coverage remains a separate smoke test."""
import json
import os
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch
import test_regressions as regressions
import setup_symlinks as setup


def metadata(root):
    result={}
    for base,dirs,files in os.walk(root,followlinks=False):
        for name in dirs+files:
            p=Path(base)/name; st=p.lstat()
            result[str(p.relative_to(root))]=(st.st_mode,st.st_mtime_ns,os.readlink(p) if p.is_symlink() else p.read_bytes() if p.is_file() else None)
    st=root.stat(); result['.']=(st.st_mode,st.st_mtime_ns)
    return result


class FinalBoundaryTests(unittest.TestCase):
    setUp=regressions.RegressionTests.setUp
    tearDown=regressions.RegressionTests.tearDown
    run_setup=regressions.RegressionTests.run_setup
    config=regressions.RegressionTests.config
    oracle=regressions.RegressionTests.oracle

    def test_final_headers_effective_values_restore_bytes_and_metadata(self):
        for header in ('[agents.debugger]',"[agents.'debugger']",'[agents.debugger] # user table','[agents.debugger]\n# trailing comment'):
            with self.subTest(header=header):
                p=self.config(header); p.chmod(0o640); original=(p.read_bytes(),p.stat().st_mode,p.stat().st_mtime_ns)
                self.oracle(p)
                result=self.run_setup('--assets-only'); self.assertEqual(result.returncode,0,result.stderr)
                parsed=self.oracle(p)
                desired=setup.render(self.templates['codex'],self.home)
                for role,values in desired['agents'].items():
                    self.assertEqual(parsed['agents'][role]['config_file'],values['config_file'])
                after=metadata(self.home); result=self.run_setup('--assets-only')
                self.assertEqual(result.returncode,0,result.stderr); self.assertEqual(result.stdout,''); self.assertEqual(after,metadata(self.home))
                self.assertEqual(self.run_setup('--assets-only','--uninstall').returncode,0)
                self.assertEqual(original,(p.read_bytes(),p.stat().st_mode,p.stat().st_mtime_ns))
                before=metadata(self.home); result=self.run_setup('--assets-only','--uninstall')
                self.assertEqual(result.returncode,0,result.stderr); self.assertEqual(result.stdout,''); self.assertEqual(before,metadata(self.home))

    def test_effective_value_guard_catches_syntax_valid_comment_loss(self):
        desired={(('agents','debugger'),'config_file'):'expected.toml'}
        for text in ('[agents.debugger] # config_file = "expected.toml"','[agents.debugger]\nconfig_file = "wrong.toml"\n'):
            with self.subTest(text=text):
                with self.assertRaisesRegex(ValueError,'readback'): setup.validate_managed_toml(text,desired,None)
                try:
                    import tomllib
                except ImportError:
                    continue
                with self.assertRaisesRegex(ValueError,'readback'): setup.validate_managed_toml(text,desired,tomllib)

    def test_unmanaged_array_multiline_and_literal_dot_survive_readback(self):
        original='note = """\n[agents.debugger]\nconfig_file = "not-a-setting"\n"""\n[[local]]\nvalue = "keep"\n["agents.debugger"]\nconfig_file = "literal"'
        p=self.config(original); self.oracle(p)
        result=self.run_setup('--assets-only'); self.assertEqual(result.returncode,0,result.stderr)
        parsed=self.oracle(p); self.assertEqual(parsed['local'],[{'value':'keep'}]); self.assertEqual(parsed['agents.debugger']['config_file'],'literal')
        self.assertEqual(parsed['agents']['debugger']['config_file'],str(self.home/'.codex/agents/debugger.toml'))
        self.assertEqual(self.run_setup('--assets-only','--uninstall').returncode,0); self.assertEqual(p.read_text(),original)

    def test_second_uninstall_and_never_installed_full_mode_exact_noop(self):
        for mode in (['--assets-only'],[]):
            with self.subTest(mode=mode):
                before=metadata(self.home); result=self.run_setup(*mode,'--uninstall')
                self.assertEqual(result.returncode,0,result.stderr); self.assertEqual(result.stdout,''); self.assertEqual(before,metadata(self.home))
        self.assertEqual(self.run_setup('--assets-only').returncode,0)
        self.assertEqual(self.run_setup('--assets-only','--uninstall').returncode,0)
        for mode in (['--assets-only'],[]):
            before=metadata(self.home); result=self.run_setup(*mode,'--uninstall')
            self.assertEqual(result.returncode,0,result.stderr); self.assertEqual(result.stdout,''); self.assertEqual(before,metadata(self.home))

    def test_nonempty_directory_journal_still_cleared(self):
        engine=setup.Installer(self.home); engine.mkdir(self.home/'.claude/skills')
        self.assertTrue(engine.state['directories']); engine.uninstall()
        self.assertFalse((self.home/'.claude').exists())
        self.assertEqual(json.loads(engine.state_path.read_text())['directories'],[])
        before=metadata(self.home); engine.uninstall(); self.assertEqual(before,metadata(self.home))

    def test_value_validation_failure_aborts_full_setup_before_writes(self):
        before=metadata(self.home)
        with patch.object(setup,'validate_managed_toml',side_effect=ValueError('managed TOML value readback failed')),patch.dict(os.environ,HOME=str(self.home)),patch('sys.argv',['setup']),patch('setup_plugins.NativePlugins.preflight') as native:
            with self.assertRaisesRegex(ValueError,'readback'): setup.main()
            native.assert_not_called()
        self.assertEqual(before,metadata(self.home))


if __name__=='__main__': unittest.main(verbosity=2)
