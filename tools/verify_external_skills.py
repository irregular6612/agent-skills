"""Read-only audit of exact vendored external bytes and optional Git checkout."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]

def git(repo, *args):
    return subprocess.check_output(['git', '-C', str(repo), *args])

def verify(root=ROOT, upstream=None):
    pack = json.loads((root/'dependencies/lock.yaml').read_text())['external_skills'][0]
    revision = pack['commit']
    if not re.fullmatch('[0-9a-f]{40}', revision):
        raise ValueError('external commit is not an immutable SHA')
    if upstream is not None:
        if git(upstream, 'rev-parse', 'HEAD').decode().strip() != revision:
            raise ValueError('upstream checkout HEAD differs from the lock')
    count = 0
    for skill in pack['skills']:
        directory = root/skill['canonical']
        actual = {p.relative_to(directory).as_posix() for p in directory.rglob('*') if p.is_file()}
        if actual != set(skill['sha256']):
            raise ValueError('unlocked file set: '+skill['name'])
        if upstream is not None:
            tree = git(upstream, 'rev-parse', revision+':'+skill['upstream_path']).decode().strip()
            if tree != skill['git_tree']:
                raise ValueError('upstream Git tree differs: '+skill['name'])
        for rel, expected in skill['sha256'].items():
            data = (directory/rel).read_bytes()
            if hashlib.sha256(data).hexdigest() != expected:
                raise ValueError('vendored bytes differ: '+skill['name']+'/'+rel)
            if upstream is not None and data != git(upstream, 'show', revision+':'+skill['upstream_path']+'/'+rel):
                raise ValueError('upstream bytes differ: '+skill['name']+'/'+rel)
            count += 1
    license_data = (root/pack['license_file']).read_bytes()
    if hashlib.sha256(license_data).hexdigest() != pack['license_sha256']:
        raise ValueError('vendored license differs')
    if upstream is not None and license_data != git(upstream, 'show', revision+':LICENSE'):
        raise ValueError('upstream license differs')
    return {'revision':revision, 'skills':len(pack['skills']), 'files':count, 'license':pack['license'], 'upstream_checked':upstream is not None}

def main():
    p=argparse.ArgumentParser(); p.add_argument('--upstream-checkout', type=Path); a=p.parse_args()
    print(json.dumps(verify(upstream=a.upstream_checkout), indent=2))

if __name__ == '__main__':
    main()
