"""Keep the qualified N1 execution tree and add registered fork transport only."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile


ROOT = Path(__file__).resolve().parents[3]
BASE = '9d00ee63ab2196b95f8374e8245d9dea2ed8782b'
TRANSPORT = '29b55f21a2341c77b45c53e12aa166e253bac0f7'
FILES = (
    'robots/libero/v5_branch_state.py',
    'scripts/probe_bounded_hybrid_d2.py',
    'scripts/probe_bounded_hybrid_repair.py',
    'coordination/bounded_skills_20261016/scripts/run_schema6_physical_20261020.py',
    'coordination/bounded_skills_20261016/scripts/run_fixed_latency_20261020.py',
    'tests/unit_tests/robots/libero/test_bounded_hybrid_diagnostic.py',
    'tests/unit_tests/robots/libero/test_v5_branch_state.py',
    'tests/unit_tests/robots/libero/test_bounded_hybrid_repair.py',
    'tests/unit_tests/robots/libero/test_schema6_physical_launcher.py',
)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--archive', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    a.output.mkdir(parents=True, exist_ok=False)
    with tempfile.TemporaryDirectory(prefix='rd_qualified90_index_') as temp:
        env = {**os.environ, 'GIT_INDEX_FILE': str(Path(temp)/'index')}
        subprocess.run(['git', 'read-tree', BASE], cwd=ROOT, env=env, check=True)
        blobs = {}
        for path in FILES:
            blob = subprocess.check_output(['git', 'rev-parse', TRANSPORT+':'+path],
                cwd=ROOT, text=True).strip()
            subprocess.run(['git', 'update-index', '--cacheinfo', '100644,'+blob+','+path],
                cwd=ROOT, env=env, check=True)
            blobs[path] = blob
        tree = subprocess.check_output(['git', 'write-tree'], cwd=ROOT, env=env, text=True).strip()
    changed = subprocess.check_output(['git', 'diff', '--name-only', BASE, tree],
        cwd=ROOT, text=True).splitlines()
    assert set(changed) <= set(FILES)
    for path in ('robots/libero/bounded_skills.py', 'robots/libero/bounded_screen.py',
                 'robots/libero/bounded_oracle.py', 'robots/libero/bounded_chunk.py'):
        assert subprocess.check_output(['git', 'rev-parse', BASE+':'+path], cwd=ROOT) == \
            subprocess.check_output(['git', 'rev-parse', tree+':'+path], cwd=ROOT)
    with a.archive.open('xb') as stream:
        subprocess.run(['git', 'archive', '--format=tar.gz', tree], cwd=ROOT, stdout=stream, check=True)
    subprocess.run(['tar', '-xzf', str(a.archive), '-C', str(a.output)], check=True)
    evidence = {'qualified_N1_tree': BASE, 'transport_commit': TRANSPORT,
        'source_tree': tree, 'overlay_blobs': blobs, 'changed_files': changed,
        'execution_planning_oracle_unchanged': True, 'dirty_worktree_included': False,
        'archive': str(a.archive), 'archive_sha256': hashlib.sha256(a.archive.read_bytes()).hexdigest(),
        'training': False}
    Path(str(a.archive)+'.json').write_text(json.dumps(evidence, indent=2)+'\n')
    print(json.dumps(evidence, indent=2))


if __name__ == '__main__':
    main()
