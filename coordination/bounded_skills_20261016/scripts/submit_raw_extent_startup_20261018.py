"""Insert the same-launcher raw-extent startup in the existing third GPU lane."""

import hashlib
import json
import subprocess
from pathlib import Path

root = Path('/public/home/sunyihan/rpent_libero_eval')
base = root/'coordination/bounded_skills_20261016'
receipt = json.loads((base/'reports/raw_extent_preparation_20261018.json').read_text())
pair_path = base/'reports/bowl8173_guided_runtime_pair_r3_CPU_20261018.json'
pair = json.loads(pair_path.read_text())
assert pair['source'] == receipt['snapshot']
assert pair['results'][0]['check']['passed'] is False
assert pair['results'][1]['check']['passed'] is True
source, manifest = Path(receipt['snapshot']), Path(receipt['manifest']['path'])
assert receipt['preflight']['exit_code'] == 0
assert hashlib.sha256(manifest.read_bytes()).hexdigest() == receipt['manifest']['sha256']
raw = subprocess.check_output(['squeue', '-r', '-h', '-u', 'sunyihan',
    '-o', '%i|%j|%T|%N'], text=True)
ours = [row.split('|') for row in raw.splitlines() if '|rd-bounded-' in row]
running = [row for row in ours if row[2] == 'RUNNING']
assert len(running) <= 3 and all(row[3] == 'node02' for row in running), running
assert any(row[0] == '8173_12' for row in running), running
following = [row[0] for row in ours if row[0].startswith('8173_') and row[2] == 'PENDING']
assert following and all(13 <= int(task.split('_')[1]) <= 59 for task in following)
assert any(row[0].startswith('8192_') and row[2] == 'PENDING' for row in ours)
export = ('ALL,SOURCE='+str(source)+',SOURCE_COMMIT='+receipt['source_commit']
    +',MANIFEST='+str(manifest)+',STARTUP=1')
# Keep the new job ineligible while moving the pending successors; only
# after their dependencies are installed is its own third-lane edge opened.
arguments = ['sbatch', '--parsable', '--nodelist=node02', '--nice=500', '--array=6%1',
    '--dependency=afterany:8192', '--export='+export,
    str(source/'scripts/run_bounded_21f0744_20261017.sbatch')]
job = subprocess.check_output(arguments, text=True).strip()
updates = []
for task in following:
    command = ['scontrol', 'update', 'JobId='+task, 'Dependency=afterany:'+job]
    subprocess.run(command, check=True)
    updates.append(command)
command = ['scontrol', 'update', 'JobId='+job, 'Dependency=afterany:8173_12']
subprocess.run(command, check=True)
updates.append(command)
report = {'scope': 'same-launcher original bowl init6 startup, pi05 disabled, not confirmation/training',
    'job': job, 'arguments': arguments, 'updates': updates, 'source_commit': receipt['source_commit'],
    'snapshot': str(source), 'manifest': receipt['manifest'], 'queue_before': ours,
    'cpu_pair': {'path': str(pair_path), 'sha256': hashlib.sha256(pair_path.read_bytes()).hexdigest()},
    'aggregate_cap': 3, 'lane': '3:8173_12 -> '+job+' -> remaining8173'}
(base/'reports/raw_extent_startup_submission_20261018.json').write_text(json.dumps(report, indent=2)+'\n')
print(json.dumps({k:v for k,v in report.items() if k not in ('updates','queue_before')}))
