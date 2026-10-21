"""Archive only the object-contact ablation on the strict N1 transport."""
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile


ROOT = Path(__file__).resolve().parents[3]
BASE = '0514333776503c8af58d2ab656b8a3393c168a22'
FIX = '139431e9'


def main():
    fix = subprocess.check_output(['git', 'rev-parse', FIX], cwd=ROOT, text=True).strip()
    files = ['robots/libero/bounded_skills.py',
             'tests/unit_tests/robots/libero/test_bounded_execution_recovery.py']
    patch = subprocess.check_output(['git', 'diff', fix+'^', fix, '--', *files], cwd=ROOT)
    with tempfile.TemporaryDirectory(prefix='rd_contact_ablation_index_') as temp:
        import os
        env = {**os.environ, 'GIT_INDEX_FILE': str(Path(temp)/'index')}
        subprocess.run(['git', 'read-tree', BASE], cwd=ROOT, env=env, check=True)
        subprocess.run(['git', 'apply', '--cached', '-'], input=patch, cwd=ROOT, env=env, check=True)
        tree = subprocess.check_output(['git', 'write-tree'], cwd=ROOT, env=env, text=True).strip()
    archive = Path('/tmp/rd_object_contact_ablation_20261022.tar.gz')
    with archive.open('xb') as stream:
        subprocess.run(['git', 'archive', '--format=tar.gz', tree], cwd=ROOT, stdout=stream, check=True)
    meta = {'scope': 'strict N1 object-contact-chain removal ablation; development only',
        'base_commit': BASE, 'production_fix_commit': fix, 'exact_source_tree': tree,
        'archive': str(archive), 'archive_sha256': hashlib.sha256(archive.read_bytes()).hexdigest(),
        'unchanged_transport': '05143337 full integration/controller/RNG; native-buffer D2 change excluded',
        'changed_files': files, 'training': False}
    print(json.dumps(meta, indent=2))


if __name__ == '__main__':
    main()
