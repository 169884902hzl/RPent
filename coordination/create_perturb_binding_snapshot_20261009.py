"""Archive the native guard, contact approach and source-binding fixes."""

import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tarfile

ROOT = Path('/public/home/sunyihan/rpent_libero_eval')
PARENT = ROOT / 'source_v5_native_stop_guard_20261009_r2'
SOURCE = ROOT / 'source_v5_perturb_binding_20261009_r1'


def ref(path):
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    parent = json.loads((PARENT / 'source_snapshot.json').read_text())
    archive = Path(parent['archive']['path'])
    if ref(archive) != parent['archive']:
        raise ValueError('Parent source archive changed')
    with tarfile.open(archive) as stream:
        names = stream.getnames()
    shutil.copytree(PARENT, SOURCE, symlinks=True,
                    ignore=shutil.ignore_patterns('__pycache__', '.pytest_cache'))
    patches = [ROOT / 'coordination' / name for name in (
        'grasp_wrist_contact_v3_20261009.patch', 'oracle_source_clause_binding_20261009.patch')]
    for patch in patches:
        subprocess.run(['git', 'apply', '--check', str(patch)], cwd=SOURCE, check=True)
        subprocess.run(['git', 'apply', str(patch)], cwd=SOURCE, check=True)
    changed = ['robots/libero/v5_runtime.py', 'robots/libero/v5_oracle_policy.py']
    target = SOURCE / 'tests/unit_tests/robots/libero/test_v5_oracle_policy.py'
    shutil.copy2(ROOT / 'coordination/test_v5_oracle_policy_binding_20261009.py', target)
    changed.append(str(target.relative_to(SOURCE)))
    output = Path(str(SOURCE) + '.tar')
    members = list(dict.fromkeys([*names, *changed]))
    with tarfile.open(output, 'x') as stream:
        for relative in members:
            stream.add(SOURCE / relative, arcname=relative, recursive=False)
    with tarfile.open(output) as stream:
        for relative in changed:
            if hashlib.sha256(stream.extractfile(relative).read()).hexdigest() != ref(SOURCE / relative)['sha256']:
                raise ValueError('Archived code differs from execution directory')
    files = {str(item.get('relative_path') or Path(item['path']).relative_to(PARENT)):
             None for item in parent['files']}
    files.update(dict.fromkeys(changed))
    identity = {'path': str(SOURCE), 'commit': parent['commit'], 'parent_snapshot': ref(PARENT / 'source_snapshot.json'),
                'base_archive': parent['archive'], 'patches': [ref(p) for p in patches],
                'files': [{**ref(SOURCE / r), 'relative_path': r} for r in files],
                'archive': ref(output), 'archive_complete': True, 'archive_member_count': len(members),
                'modified_modules_in_archive_verified': True, 'unrelated_dirty_changes_excluded': True}
    (SOURCE / 'source_snapshot.json').write_text(json.dumps(identity, indent=2) + '\n')
    print(json.dumps(identity))


if __name__ == '__main__':
    main()
