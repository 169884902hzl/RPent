"""Build complete archives using the parent archive's complete member list."""

import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tarfile

ROOT = Path('/public/home/sunyihan/rpent_libero_eval')
PARENT = ROOT / 'source_v5_skill_budget_20261009_r2'


def ref(path):
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    parent = json.loads((PARENT / 'source_snapshot.json').read_text())
    archive = Path(parent['archive']['path'])
    assert ref(archive) == parent['archive']
    with tarfile.open(archive) as stream:
        names = stream.getnames()
    assert 'robots/libero/v5_runtime.py' in names
    for name, patch_name, test_name in [
        ('source_v5_native_stop_guard_20261009_r2', 'subtask_native_stop_guard_20261009.patch',
         'test_v5_subtask_release_reverify.py'),
        ('source_v5_wrist_contact_20261009_r2', 'grasp_wrist_contact_v3_20261009.patch',
         'test_v5_grasp_closeup.py')]:
        source = ROOT / name
        identity_path = source / 'source_snapshot.json'
        if identity_path.exists() and json.loads(identity_path.read_text()).get('archive_complete'):
            print(identity_path.read_text()[:200]); continue
        if source.exists():
            raise ValueError('existing incomplete destination must be inspected before resuming')
        shutil.copytree(PARENT, source, symlinks=True,
                        ignore=shutil.ignore_patterns('__pycache__', '.pytest_cache'))
        patch = ROOT / 'coordination' / patch_name
        subprocess.run(['git', 'apply', '--check', str(patch)], cwd=source, check=True)
        subprocess.run(['git', 'apply', str(patch)], cwd=source, check=True)
        test_relative = 'tests/unit_tests/robots/libero/' + test_name
        shutil.copy2(ROOT / 'coordination' / test_name, source / test_relative)
        updated = ['robots/libero/v5_runtime.py', test_relative]
        files = []
        for item in parent['files']:
            relative = str(item.get('relative_path') or Path(item['path']).relative_to(PARENT))
            files.append({**ref(source / relative), 'relative_path': relative})
        for relative in updated:
            files.append({**ref(source / relative), 'relative_path': relative})
        output = Path(str(source) + '.tar')
        with tarfile.open(output, 'x') as stream:
            for relative in dict.fromkeys([*names, *updated]):
                path = source / relative
                assert path.exists() or path.is_symlink(), str(path)
                stream.add(path, arcname=relative, recursive=False)
        # Validate the archived execution code, not just metadata lists.
        with tarfile.open(output) as stream:
            for relative in updated:
                assert hashlib.sha256(stream.extractfile(relative).read()).hexdigest() == ref(source / relative)['sha256']
        identity = {'path': str(source), 'commit': parent['commit'],
            'identity_kind': 'full_parent_source_archive_plus_scoped_patch',
            'base_archive': parent['archive'], 'patch': ref(patch),
            'files': files, 'archive': ref(output), 'archive_complete': True,
            'archive_member_count': len(dict.fromkeys([*names, *updated])),
            'modified_runtime_in_archive_verified': True, 'unrelated_dirty_changes_excluded': True}
        identity_path.write_text(json.dumps(identity, indent=2)+'\n')
        print(json.dumps({'source': str(source), 'archive': identity['archive'],
                          'runtime': ref(source/'robots/libero/v5_runtime.py')}), flush=True)


if __name__ == '__main__':
    main()
