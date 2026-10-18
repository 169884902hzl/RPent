"""Queue full original oracle diagnostics after real same-launcher startup."""

import hashlib
import json
import subprocess
from pathlib import Path

root = Path('/public/home/sunyihan/rpent_libero_eval')
base = root/'coordination/bounded_skills_20261016'
receipt = json.loads((base/'reports/curved_handle_submission_20261018.json').read_text())
source = Path(receipt['snapshot'])
startup_job = receipt['job']+'_100'
accounting = subprocess.check_output(['sacct', '-X', '-n', '-j', startup_job,
    '--format=State,ExitCode', '-P'], text=True).strip()
assert accounting == 'COMPLETED|0:0', accounting
physical = next((root/'results/bounded_skills/feasibility_20261017'/('job'+startup_job)).glob('*/first_physical_request.json'))
request = json.loads(physical.read_text())
assert request['sim_steps'] > 0, request
queue = subprocess.check_output(['squeue', '-h', '-u', 'sunyihan', '-o', '%i|%j|%T|%N'], text=True)
ours = [line.split('|') for line in queue.splitlines() if line.split('|')[1].startswith('rd-bounded-')]
assert {row[0].split('_')[0] for row in ours} <= {'8117', '8159', '8163', '8164', '8169'}, ours
assert sum(row[2] == 'RUNNING' for row in ours) <= 2, ours
assert all(row[3] == 'node02' for row in ours if row[2] == 'RUNNING')
export = 'ALL,SOURCE='+str(source)+',SOURCE_COMMIT='+receipt['source_commit']+',MANIFEST='+receipt['manifest']['path']+',STARTUP=0'
def submit(array, dependency):
    arguments = ['sbatch', '--parsable', '--nodelist=node02', '--nice=500', '--array='+array,
        '--dependency=afterany:'+dependency, '--export='+export,
        str(source/'scripts/run_bounded_21f0744_20261017.sbatch')]
    return {'job': subprocess.check_output(arguments, text=True).strip(), 'arguments': arguments}
full = submit('100%1', startup_job)
representatives = submit('80,120,180,200%1', full['job'])
report = {'source_commit': receipt['source_commit'], 'snapshot': str(source),
    'manifest': receipt['manifest'], 'startup_accounting': accounting,
    'startup_physical_request': {'path': str(physical), 'sha256': hashlib.sha256(physical.read_bytes()).hexdigest(), **request},
    'paired_drawer_open': full, 'fixture_representatives': representatives,
    'aggregate_cap': 3, 'lane': '2; two other serial lanes unchanged',
    'scope': 'full original oracle development, pi05 disabled; not confirmation or training'}
(base/'reports/curved_handle_full_submission_20261018.json').write_text(json.dumps(report, indent=2)+'\n')
print(json.dumps(report, indent=2))
