"""F7 namespace/retirement and discovery oracle regression tests."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import unittest
import test_regressions as regressions
from test_final_boundaries import metadata
from native_metadata import claude_entry, front
from test_setup import ROOT
import setup_symlinks as setup


class CommandNamespaceTests(unittest.TestCase):
    setUp = regressions.RegressionTests.setUp
    tearDown = regressions.RegressionTests.tearDown
    run_setup = regressions.RegressionTests.run_setup
    fake_contract = regressions.RegressionTests.fake_contract

    def original(self, link=False):
        path=self.home/'.claude/commands/humanize.md'
        path.parent.mkdir(parents=True,exist_ok=True)
        approved=ROOT/'sources/commands/command-humanize/command.md'
        if link: path.symlink_to(approved)
        else: shutil.copy2(approved,path); path.chmod(0o640)
        os.utime(path,ns=(1234567890000000000,1234567890000000000),follow_symlinks=False)
        return path

    def roundtrip(self, link):
        path=self.original(link); before=metadata(self.home)[str(path.relative_to(self.home))]
        unknown=self.home/'.claude/commands/external.md'; unknown.symlink_to(ROOT/'README.md')
        external=metadata(self.home)['.claude/commands/external.md']
        dry=metadata(self.home); result=self.run_setup('--assets-only','--dry-run')
        self.assertEqual(result.returncode,0,result.stderr); self.assertEqual(dry,metadata(self.home))
        result=self.run_setup('--assets-only'); self.assertEqual(result.returncode,0,result.stderr)
        self.assertFalse(path.exists() or path.is_symlink())
        self.assertTrue((self.home/'.claude/commands/humanize-command.md').is_symlink())
        installed=metadata(self.home); result=self.run_setup('--assets-only')
        self.assertEqual(result.returncode,0,result.stderr); self.assertEqual(result.stdout,''); self.assertEqual(installed,metadata(self.home))
        result=self.run_setup('--assets-only','--uninstall'); self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(before,metadata(self.home)[str(path.relative_to(self.home))])
        self.assertEqual(external,metadata(self.home)['.claude/commands/external.md'])
        restored=metadata(self.home); result=self.run_setup('--assets-only','--uninstall')
        self.assertEqual(result.returncode,0,result.stderr); self.assertEqual(restored,metadata(self.home))

    def test_approved_command_copy_retired_and_exactly_restored(self): self.roundtrip(False)
    def test_approved_command_symlink_retired_and_exactly_restored(self): self.roundtrip(True)

    def refuse(self, path, root=ROOT):
        trap=self.base/'bin'; trap.mkdir(exist_ok=True)
        called=self.base/'native-called'
        for cli in ('claude','codex'):
            p=trap/cli; p.write_text('#!/bin/sh\ntouch "'+str(called)+'"\nexit 99\n'); p.chmod(0o755)
        env=dict(os.environ,HOME=str(self.home),CLAUDE_CONFIG_DIR=str(self.home/'.claude'),CODEX_HOME=str(self.home/'.codex'),PATH=str(trap)+os.pathsep+os.environ['PATH'],PYTHONDONTWRITEBYTECODE='1')
        for mode in ([],['--assets-only'],['--dry-run']):
            before=metadata(self.home)
            result=subprocess.run([sys.executable,str(root/'tools/setup_symlinks.py'),*mode],env=env,capture_output=True,text=True)
            self.assertEqual(result.returncode,2,result.stdout+result.stderr)
            self.assertEqual(before,metadata(self.home)); self.assertFalse(called.exists())
            self.assertRegex(result.stderr,'differs from approved|skill/command native namespace')

    def test_modified_command_copy_refused_before_home_and_native_writes(self):
        p=self.original(); p.write_text('user modified wrapper'); self.refuse(p)

    def test_modified_command_symlink_target_refused_even_identical_bytes(self):
        p=self.original(True); p.unlink(); external=self.base/'external.md'
        shutil.copy2(ROOT/'sources/commands/command-humanize/command.md',external); p.symlink_to(external)
        self.refuse(p)

    def test_dangling_command_symlink_refused_before_writes(self):
        p=self.original(True); p.unlink(); p.symlink_to(self.base/'missing'); self.refuse(p)

    def test_distinct_definitions_same_native_namespace_refused_before_writes(self):
        for skill_name in ('humanize', 'different-directory'):
            entries=[{'harness':'claude','destination':'skills/'+skill_name,'source':'sources/a'},
                     {'harness':'claude','destination':'commands/humanize.md','source':'sources/command.md'}]
            fake=self.fake_contract(entries)
            (fake/'sources/a/SKILL.md').write_text('---\nname: "humanize"\ndescription: skill definition\n---\nSkill\n')
            (fake/'sources/command.md').write_text('---\ndescription: different wrapper\n---\nCommand\n')
            self.refuse(None,root=fake)

    def test_discovery_oracle_rejects_shadow_wrong_description_and_duplicates(self):
        e=next(e for e in self.manifest['links'] if e['destination']=='commands/humanize-command.md')
        meta=front(ROOT/e['source']); hint=meta['argument-hint'][1:-1]
        correct={'name':'humanize-command','description':meta['description']+' (user)','argumentHint':hint}
        self.assertTrue(claude_entry(ROOT,e,{'commands':[correct]})['recognized'])
        for items in ([dict(correct,description='skill description (user)')],[correct,correct],[],[dict(correct,argumentHint='wrong')]):
            self.assertFalse(claude_entry(ROOT,e,{'commands':items})['recognized'])

    def test_counts_names_and_immutable_humanize_approval_snapshot(self):
        self.assertEqual(len(self.manifest['links']),155)
        for category,count in [('skills',37),('commands',2),('agents',34)]:
            self.assertEqual(sum(e['harness']=='claude' and e['destination'].startswith(category+'/') for e in self.manifest['links']),count)
        # F7 wrapper approval stays immutable; the skill can be reviewed as a shared revision.
        for relative in ('sources/commands/command-humanize/command.md',):
            old=subprocess.check_output(['git','show','0cb38e2edc88e6bd82956489e225b47ae8767f69:'+relative],cwd=ROOT)
            self.assertEqual(old,(ROOT/relative).read_bytes())
        skill=next(e for e in self.manifest['links'] if e['harness']=='claude' and e['destination']=='skills/humanize')
        self.assertEqual(front(ROOT/skill['source']/'SKILL.md')['name'],'humanize')


if __name__=='__main__': unittest.main(verbosity=2)
