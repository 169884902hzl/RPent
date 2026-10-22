"""Overlay committed execution changes on the fixed N1 D3 transport."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile


ROOT = Path(__file__).resolve().parents[3]
BASE = '2eb423798d158fc4d7a84843928be884a15fc56e'
FILES = (
    'robots/libero/bounded_skills.py',
    'tests/unit_tests/robots/libero/test_bounded_skills.py',
    'tests/unit_tests/robots/libero/test_bounded_execution_recovery.py',
    'tests/unit_tests/robots/libero/test_bounded_schema6.py',
)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--commit', required=True)
    parser.add_argument('--archive', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    args.archive.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='rd_selected_grasp_index_') as temp:
        env = {**os.environ, 'GIT_INDEX_FILE': str(Path(temp)/'index')}
        subprocess.run(['git', 'read-tree', BASE], cwd=ROOT, env=env, check=True)
        files = {}
        for path in FILES:
            blob = subprocess.check_output(['git', 'rev-parse', args.commit+':'+path],
                cwd=ROOT, text=True).strip()
            subprocess.run(['git', 'update-index', '--cacheinfo', '100644,'+blob+','+path],
                cwd=ROOT, env=env, check=True)
            files[path] = blob
        tree = subprocess.check_output(['git', 'write-tree'], cwd=ROOT, env=env, text=True).strip()
    with args.archive.open('xb') as stream:
        subprocess.run(['git', 'archive', '--format=tar.gz', tree], cwd=ROOT, stdout=stream, check=True)
    subprocess.run(['tar', '-xzf', str(args.archive), '-C', str(args.output)], check=True)
    evidence = {'base_tree': BASE, 'execution_commit': args.commit, 'source_tree': tree,
        'archive': str(args.archive), 'archive_sha256': hashlib.sha256(args.archive.read_bytes()).hexdigest(),
        'committed_overlay_blobs': files, 'training': False, 'dirty_worktree_included': False}
    Path(str(args.archive)+'.json').write_text(json.dumps(evidence, indent=2)+'\n')
    print(json.dumps(evidence))


if __name__ == '__main__':
    main()
