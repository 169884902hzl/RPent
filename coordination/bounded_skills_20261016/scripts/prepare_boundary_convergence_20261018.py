"""Prepare an immutable tested snapshot; this script does not submit GPU jobs."""

import argparse
import hashlib
import json
import os
import subprocess
import tarfile
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument('--archive-sha', required=True)
args = parser.parse_args()
root = Path('/public/home/sunyihan/rpent_libero_eval')
commit = '11ec9aa0b59265cdfd50310e7b9868c4ff1bfa21'
archive = root/'bounded_boundary_convergence_11ec9aa_20261018.tar.gz'
assert hashlib.sha256(archive.read_bytes()).hexdigest() == args.archive_sha
source = root/'source_bounded_11ec9aa_20261018'
source.mkdir()
with tarfile.open(archive) as stream:
    stream.extractall(source)
prep = root/'results/bounded_skills/feasibility_20261017/preparation'
plan = json.loads((prep/'original20_manifest_raw_extent_20261018.json').read_text())
plan['source_commit'] = commit
plan['source_snapshot'] = {'path': str(source), 'code_archive_sha256': args.archive_sha}
manifest = prep/'original20_manifest_boundary_convergence_20261018.json'
manifest.write_text(json.dumps(plan, indent=2)+'\n')
environment = os.environ.copy()
environment.update(PYTHONPATH=str(source), LIBERO_TYPE='standard',
    LIBERO_CONFIG_PATH=str(root/'runtime_config'), CUDA_VISIBLE_DEVICES='', OPENBLAS_NUM_THREADS='1')
preflight = subprocess.run([str(root/'.venv/bin/python'), '-m', 'scripts.v5_probe_preflight',
    '--manifest', str(manifest), '--states'], cwd=source, env=environment,
    capture_output=True, text=True)
log = prep/'preflight_boundary_convergence_20261018.log'
log.write_text(preflight.stdout+preflight.stderr)
assert preflight.returncode == 0, preflight.stderr
report = {'scope': 'CPU preparation only; no GPU submission or physical result',
    'source_commit': commit, 'snapshot': str(source), 'archive_sha256': args.archive_sha,
    'manifest': {'path': str(manifest), 'sha256': hashlib.sha256(manifest.read_bytes()).hexdigest()},
    'preflight': {'exit_code': preflight.returncode, 'log': str(log)},
    'cpu_tests': 225, 'training': False, 'confirmation': False, 'pi05_in_oracle': False}
output = root/'coordination/bounded_skills_20261016/reports/boundary_convergence_preparation_20261018.json'
output.write_text(json.dumps(report, indent=2)+'\n')
print(json.dumps(report, indent=2))
