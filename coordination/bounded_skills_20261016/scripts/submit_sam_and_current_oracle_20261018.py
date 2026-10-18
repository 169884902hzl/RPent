"""Reuse the third serial lane for identity diagnosis and current-source oracle."""

import hashlib
import json
import subprocess
from pathlib import Path

root = Path('/public/home/sunyihan/rpent_libero_eval')
base = root/'coordination/bounded_skills_20261016'
prep = root/'results/bounded_skills/feasibility_20261017/preparation'
receipt = json.loads((base/'reports/curved_handle_full_submission_20261018.json').read_text())
assert receipt['startup_accounting'] == 'COMPLETED|0:0'
assert receipt['startup_physical_request']['sim_steps'] > 0
script, launcher = (prep/name for name in ('cup8158_sam_identity_GPU_20261018.py', 'run_cup_sam_identity_20261018.sbatch'))
compile(script.read_text(), str(script), 'exec')
subprocess.run(['bash', '-n', str(launcher)], check=True)
queue = subprocess.check_output(['squeue', '-r', '-h', '-u', 'sunyihan', '-o', '%i|%j|%T|%N'], text=True)
ours = [line.split('|') for line in queue.splitlines() if line.split('|')[1].startswith('rd-bounded-')]
assert sum(row[2] == 'RUNNING' for row in ours) <= 3
assert all(row[3] == 'node02' for row in ours if row[2] == 'RUNNING')
replaced = []
for index in range(3, 60):
    rows = [row for row in ours if row[0] == f'8159_{index}']
    assert len(rows) == 1 and rows[0][2] == 'PENDING', rows
    replaced.extend(rows)
subprocess.run(['scancel', *[row[0] for row in replaced]], check=True)
args = ['sbatch', '--parsable', '--nodelist=node02', '--nice=500',
    '--dependency=afterany:8159_2', str(launcher)]
diagnostic = {'job': subprocess.check_output(args, text=True).strip(), 'arguments': args}
source = Path(receipt['snapshot'])
args = ['sbatch', '--parsable', '--nodelist=node02', '--nice=500', '--array=3-59%1',
    '--dependency=afterany:'+diagnostic['job'],
    '--export=ALL,SOURCE='+str(source)+',SOURCE_COMMIT='+receipt['source_commit']+',MANIFEST='+receipt['manifest']['path']+',STARTUP=0',
    str(source/'scripts/run_bounded_21f0744_20261017.sbatch')]
oracle = {'job': subprocess.check_output(args, text=True).strip(), 'arguments': args}
report = {'source_commit': receipt['source_commit'], 'snapshot': str(source), 'manifest': receipt['manifest'],
    'diagnostic': diagnostic, 'remaining_oracle': oracle, 'replaced_pending': replaced,
    'diagnostic_script': {'path': str(script), 'sha256': hashlib.sha256(script.read_bytes()).hexdigest()},
    'diagnostic_launcher': {'path': str(launcher), 'sha256': hashlib.sha256(launcher.read_bytes()).hexdigest()},
    'replacement_reason': 'remaining original oracle states use current tested3d71f44 source including contact retry fix; saved-public SAM diagnosis runs first in the same lane',
    'aggregate_cap': 3, 'lane': '3, after running8159_2; other two serial lanes unchanged',
    'scope': 'original public perception/oracle development only; not confirmation, training or a new model'}
(base/'reports/sam_and_current_oracle_submission_20261018.json').write_text(json.dumps(report, indent=2)+'\n')
print(json.dumps({k:v for k,v in report.items() if k != 'replaced_pending'}, indent=2))
