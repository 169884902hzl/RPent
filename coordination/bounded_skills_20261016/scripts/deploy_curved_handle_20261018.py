"""Deploy the measured handle fix in the existing second serial GPU lane."""

import hashlib
import json
import os
import subprocess
import tarfile
from pathlib import Path

root = Path('/public/home/sunyihan/rpent_libero_eval')
commit = '3d71f446c846f0e7bc2b1ae2816f6aab6d3ed461'
archive = root/'bounded_curved_handle_3d71f44_20261018.tar.gz'
archive_sha = hashlib.sha256(archive.read_bytes()).hexdigest()
assert archive_sha == '6f5f2e3c499e169755f1449ed0ef404817b56f000519364bd4694f64dcebcb82'
source = root/'source_bounded_3d71f44_20261018'
source.mkdir()
with tarfile.open(archive) as stream:
    stream.extractall(source)
prep = root/'results/bounded_skills/feasibility_20261017/preparation'
plan = json.loads((prep/'original20_manifest_contact_retry_20261018.json').read_text())
plan['source_commit'] = commit
plan['source_snapshot'] = {'path': str(source), 'code_archive_sha256': archive_sha}
manifest = prep/'original20_manifest_curved_handle_20261018.json'
manifest.write_text(json.dumps(plan, indent=2)+'\n')
environment = os.environ.copy()
environment.update(PYTHONPATH=str(source), LIBERO_TYPE='standard',
    LIBERO_CONFIG_PATH=str(root/'runtime_config'), CUDA_VISIBLE_DEVICES='', OPENBLAS_NUM_THREADS='1')
preflight = subprocess.run([str(root/'.venv/bin/python'), '-m', 'scripts.v5_probe_preflight',
    '--manifest', str(manifest), '--states'], cwd=source, env=environment, capture_output=True, text=True)
log = prep/'preflight_curved_handle_20261018.log'
log.write_text(preflight.stdout+preflight.stderr)
assert preflight.returncode == 0, preflight.stderr
queue = subprocess.check_output(['squeue', '-r', '-h', '-u', 'sunyihan', '-o', '%i|%j|%T|%N'], text=True)
ours = [line.split('|') for line in queue.splitlines() if line.split('|')[1].startswith('rd-bounded-')]
assert sum(row[2] == 'RUNNING' for row in ours) <= 3
assert all(row[3] == 'node02' for row in ours if row[2] == 'RUNNING')
replaced = []
for task in ('8162_120', '8162_180', '8162_200'):
    row = [row for row in ours if row[0] == task]
    assert len(row) == 1 and row[0][2] == 'PENDING', (task, row)
    subprocess.run(['scancel', task], check=True)
    replaced.extend(row)
arguments = ['sbatch', '--parsable', '--nodelist=node02', '--nice=500', '--array=100%1',
    '--dependency=afterany:8162_80',
    '--export=ALL,SOURCE='+str(source)+',SOURCE_COMMIT='+commit+',MANIFEST='+str(manifest)+',STARTUP=1',
    str(source/'scripts/run_bounded_21f0744_20261017.sbatch')]
job = subprocess.check_output(arguments, text=True).strip()
report = {'job': job, 'arguments': arguments, 'source_commit': commit, 'snapshot': str(source),
    'archive_sha256': archive_sha, 'manifest': {'path': str(manifest),
        'sha256': hashlib.sha256(manifest.read_bytes()).hexdigest()},
    'preflight': {'exit_code': preflight.returncode, 'log': str(log)}, 'cpu_checks': 206,
    'scope': 'original drawer startup, oracle pi05 disabled; not confirmation or training',
    'aggregate_cap': 3, 'lane': '2, after running8162_80; other two serial lanes unchanged',
    'replaced_pending': replaced,
    'replacement_reason': 'unstarted fixture diagnostics replaced by tested curved handle source; full episodes wait for physical startup',
    'queue_before': ours}
output = root/'coordination/bounded_skills_20261016/reports/curved_handle_submission_20261018.json'
output.write_text(json.dumps(report, indent=2)+'\n')
print(json.dumps(report, indent=2))
