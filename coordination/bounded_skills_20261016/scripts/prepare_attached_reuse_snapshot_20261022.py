"""Pin the verified standoff removal and pending-attachment reuse on N1 D3."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile


ROOT = Path(__file__).resolve().parents[3]
BASE = '7bfd88d4b5942732cc6369994cd157ccd46305ca'
CACHE_FIX = '6178f265'
EXECUTION_FIX = '36dcaca6'
FILES = [
    'robots/libero/bounded_skills.py',
    'tests/unit_tests/robots/libero/test_bounded_execution_recovery.py',
    'coordination/bounded_skills_20261016/scripts/run_fixed_latency_20261020.py',
]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive', type=Path, default=Path('/tmp/rd_attached_reuse_20261022.tar.gz'))
    args = parser.parse_args()
    patch = subprocess.check_output(['git', 'diff', EXECUTION_FIX+'^', EXECUTION_FIX,
        '--', *FILES], cwd=ROOT)
    if not patch or b'_guided_payload_capture' in patch:
        raise ValueError('expected only the registered execution/diagnostic patch')
    cache_patch = subprocess.check_output(['git', 'diff', CACHE_FIX+'^', CACHE_FIX,
        '--', 'robots/libero/bounded_chunk.py',
        'tests/unit_tests/robots/libero/test_bounded_chunk.py'], cwd=ROOT)
    with tempfile.TemporaryDirectory(prefix='rd_attachment_reuse_index_') as temp:
        env = {**os.environ, 'GIT_INDEX_FILE': str(Path(temp)/'index')}
        subprocess.run(['git', 'read-tree', BASE], cwd=ROOT, env=env, check=True)
        for data in (cache_patch, patch):
            subprocess.run(['git', 'apply', '--cached', '-'], input=data,
                cwd=ROOT, env=env, check=True)
        tree = subprocess.check_output(['git', 'write-tree'], cwd=ROOT, env=env,
            text=True).strip()
    archive = args.archive
    with archive.open('xb') as stream:
        subprocess.run(['git', 'archive', '--format=tar.gz', tree],
            cwd=ROOT, stdout=stream, check=True)
    print(json.dumps({'scope': 'N1 development execution probes; old complete-state transport',
        'base_tree': BASE, 'prefix_cache_fix': CACHE_FIX, 'exact_source_tree': tree,
        'production_fix_commit': EXECUTION_FIX, 'patch_sha256': hashlib.sha256(patch).hexdigest(),
        'archive': str(archive), 'archive_sha256': hashlib.sha256(archive.read_bytes()).hexdigest(),
        'training': False}, indent=2))


if __name__ == '__main__':
    main()
