"""SSOT consolidation regressions; fixture HOMEs only, no native model calls."""
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import setup_symlinks as setup
import verify_external_skills as external

class ConsolidationTests(unittest.TestCase):
    def setUp(self):
        base=ROOT/'.test-tmp'; base.mkdir(exist_ok=True)
        self.temp=tempfile.TemporaryDirectory(dir=base)
        self.base=Path(self.temp.name); self.home=self.base/'home'; self.home.mkdir()
        self.manifest=json.loads((ROOT/'manifest.yaml').read_text())
        self.inventory=json.loads((ROOT/'docs/SYMLINK-INVENTORY.json').read_text())
    def tearDown(self): self.temp.cleanup()
    def run_command(self, args, code=0):
        env=dict(os.environ,HOME=str(self.home),CLAUDE_CONFIG_DIR=str(self.home/'.claude'),CODEX_HOME=str(self.home/'.codex'),PYTHONDONTWRITEBYTECODE='1')
        p=subprocess.run(args,cwd=ROOT,env=env,capture_output=True,text=True)
        self.assertEqual(p.returncode,code,p.stdout+p.stderr)
        return p
    def test_all_common_entries_have_one_native_named_source(self):
        common=self.inventory['shared_skill_names']; self.assertEqual(len(common),25)
        for name in common:
            rows=[e for e in self.manifest['links'] if e['destination']=='skills/'+name]
            self.assertEqual({e['harness'] for e in rows},{'claude','codex'})
            self.assertEqual({e['source'] for e in rows},{'sources/skills/'+name})
            self.assertFalse((ROOT/'sources/skills'/(name+'-claude')).exists())
            self.assertFalse((ROOT/'sources/skills'/(name+'-codex')).exists())
        self.assertEqual(self.inventory['links'],len(self.manifest['links']))
    def test_taste_locked_bytes_and_license(self):
        result=external.verify(); self.assertEqual(result['skills'],7); self.assertEqual(result['files'],7)
        self.assertEqual(result['revision'],'84ff339312d29955ce2040c02fd6e5bedb934608')
        self.assertEqual(result['license'],'MIT')
    def test_taste_tamper_extra_file_and_mutable_revision_fail(self):
        r=self.base/'repo'; (r/'dependencies').mkdir(parents=True)
        lock=json.loads((ROOT/'dependencies/lock.yaml').read_text()); pack=lock['external_skills'][0]
        for s in pack['skills']: shutil.copytree(ROOT/s['canonical'],r/s['canonical'])
        lic=r/pack['license_file']; lic.parent.mkdir(parents=True); lic.write_bytes((ROOT/pack['license_file']).read_bytes())
        target=r/'dependencies/lock.yaml'; target.write_text(json.dumps(lock))
        victim=r/pack['skills'][0]['canonical']/'SKILL.md'; original=victim.read_bytes(); victim.write_bytes(original+b'changed')
        with self.assertRaisesRegex(ValueError,'vendored bytes differ'): external.verify(r)
        victim.write_bytes(original); extra=victim.parent/'extra'; extra.write_text('unexpected')
        with self.assertRaisesRegex(ValueError,'unlocked file set'): external.verify(r)
        extra.unlink(); pack['commit']='main'; target.write_text(json.dumps(lock))
        with self.assertRaisesRegex(ValueError,'immutable'): external.verify(r)
    def test_shared_edit_readthrough_and_conflicting_item_exact_restore(self):
        # A fixture copies only skill assets, not actual HOME or repo state.
        repo=self.base/'repo'; names=self.inventory['shared_skill_names']; entries=[]
        for name in names:
            source=repo/'sources/skills'/name; source.mkdir(parents=True)
            (source/'SKILL.md').write_bytes((ROOT/'sources/skills'/name/'SKILL.md').read_bytes())
            for harness in ('claude','codex'):
                entries.append({'harness':harness,'destination':'skills/'+name,'source':'sources/skills/'+name})
        old=self.home/'.claude/skills/brandkit'; old.mkdir(parents=True); f=old/'local.txt'; f.write_bytes(b'preexisting user bytes'); f.chmod(0o640)
        os.utime(f,ns=(1650000000000000000,1650000000000000000)); identity=(f.read_bytes(),f.stat().st_mode,f.stat().st_mtime_ns)
        dangling=self.home/'.codex/skills/brandkit'; dangling.parent.mkdir(parents=True); dangling.symlink_to('../../missing-brandkit'); linktime=dangling.lstat().st_mtime_ns
        for rel in ('.claude/skills/agentcat-usage/local','.codex/skills/lost-me/local','.claude/hooks/unknown.py'):
            p=self.home/rel; p.parent.mkdir(parents=True,exist_ok=True); p.write_bytes(b'unmanaged')
        with patch.object(setup,'ROOT',repo):
            engine=setup.Installer(self.home)
            for row in entries:
                engine.link('.'+row['harness']+'/'+row['destination'],repo/row['source'])
            for name in names:
                source=repo/'sources/skills'/name/'SKILL.md'; source.write_bytes(source.read_bytes()+b'\nshared edit\n')
                for harness in ('claude','codex'):
                    self.assertEqual((self.home/('.'+harness)/'skills'/name/'SKILL.md').read_bytes(),source.read_bytes())
            engine.uninstall()
        self.assertEqual((f.read_bytes(),f.stat().st_mode,f.stat().st_mtime_ns),identity)
        self.assertEqual(os.readlink(dangling),'../../missing-brandkit'); self.assertEqual(dangling.lstat().st_mtime_ns,linktime)
        for rel in ('.claude/skills/agentcat-usage/local','.codex/skills/lost-me/local','.claude/hooks/unknown.py'):
            self.assertEqual((self.home/rel).read_bytes(),b'unmanaged')
    def test_domain_native_adapters_reference_common_bodies(self):
        mappings={'humanize':('humanize-fidelity-auditor','humanize-ko-detector','humanize-ko-monolith','humanize-ko-rewriter','humanize-naturalness-reviewer','humanize-taxonomist','humanize-web-architect'),'latex-publication':('md-tex-injection-planner','md-fragment-converter-coordinator','tex-fragment-format-auditor')}
        for skill,names in mappings.items():
            for name in names:
                self.assertTrue((ROOT/'sources/skills'/skill/'agents'/(name+'.md')).is_file())
                for harness,ext in (('claude','md'),('codex','toml')):
                    text=(ROOT/'sources/agents'/(name+'-'+harness+'.'+ext)).read_text()
                    self.assertIn('SKILL_ROOT/agents/'+name+'.md',text)
                    self.assertIn('missing',text); self.assertNotIn('Score 0',text)
                    self.assertTrue(any(e['source']=='sources/agents/'+name+'-'+harness+'.'+ext for e in self.manifest['links']))
    def test_critic_both_native_consumers_static_contract(self):
        self.run_command(['bash',str(ROOT/'sources/skills/iterative-academic-writer/evals/check_sync.sh')])
    def test_driller_active_paths_do_not_infer_claude_home(self):
        skill=ROOT/'sources/skills/paper-driller'
        for rel in ('SKILL.md','references/workflow.md','references/templates/general-v1.md'):
            text=(skill/rel).read_text()
            self.assertNotIn('~/.claude/',text)
            self.assertNotIn('$HOME/.claude/',text)
        self.assertIn('PAPER_FRONTMATTER_PYTHON',(skill/'SKILL.md').read_text())

    def test_driller_static_is_portable_without_vault_or_claude_install(self):
        p=self.run_command(['bash',str(ROOT/'sources/skills/paper-driller/scripts/validate-driller.sh')])
        self.assertIn('PASS canonical',p.stdout); self.assertIn('SKIPPED local vault',p.stdout)
        self.assertFalse((self.home/'.claude').exists())
    def test_driller_hook_schema_and_templates_resolve_canonical(self):
        spec=importlib.util.spec_from_file_location('paper_validator_ssot',ROOT/'sources/hooks/claude/paper-format-validator.py'); module=importlib.util.module_from_spec(spec)
        with patch.dict(os.environ,HOME=str(self.home)): spec.loader.exec_module(module)
        self.assertEqual(module.SCHEMA_PATH,ROOT/'sources/skills/paper-driller/references/paper-schema.json')
        self.assertEqual(module.TEMPLATES_DIR,ROOT/'sources/skills/paper-driller/references/templates')
        self.assertIsNone(module._SCHEMA_ERROR)
    def test_latex_diagnostic_does_not_force_xelatex(self):
        spec=importlib.util.spec_from_file_location('latex_diag_ssot',ROOT/'sources/skills/latex-publication/scripts/diagnose.py'); module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
        with patch.object(module.subprocess,'run',return_value=subprocess.CompletedProcess([],0,'LATEX_ENGINE=pdflatex\nTL_BIN=/fixture/bin\n','')):
            self.assertEqual(module._resolved_texlive_bin(str(self.base)),'/fixture/bin')
            self.assertEqual(module.TL_ENGINE,'pdflatex')
        report={'preamble':{'korean_packages':['kotex'],'pdflatex_only_markers':[],'custom_sty_files':[],'magic_program':'pdflatex'},'bib_with_korean':[],'missing_char_warnings':0,'abs_path_hits':[]}
        env={'engine':'pdflatex','engine_tool':'/fixture/bin/pdflatex','kotex':'yes','xecjk':None,'fonts_korean':[]}
        text='\n'.join(module.recommend(report,env))
        self.assertNotIn('xelatex',text)
    def test_legacy_export_never_defaults_to_personal_home(self):
        p=self.run_command(['bash',str(ROOT/'sources/skills/latex-publication/scripts/sync_plugin.sh')],3)
        self.assertIn('--dest',p.stderr)

if __name__=='__main__': unittest.main()
