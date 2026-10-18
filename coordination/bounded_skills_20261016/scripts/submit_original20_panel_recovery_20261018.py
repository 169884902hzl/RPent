# Copyright 2026 Zhilun Hu.
# SPDX-License-Identifier: Apache-2.0
"""Resume original-state oracle cohorts from the verified panel-recovery source."""

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument('--indices', default='0-119,160-219')
parser.add_argument('--tag', default='original20_panel_recovery_20261018')
parser.add_argument('--source-tag', default='chunk_v3_panel_recovery_20261018')
parser.add_argument('--manifest', type=Path,
    help='Optional absolute manifest with the same registered cases in a different order')
parser.add_argument('--startup-receipt', type=Path,
    help='Actual startup submission for this manifest and source')
args = parser.parse_args()
root = Path('/public/home/sunyihan/rpent_libero_eval')
reports = root / 'coordination/bounded_skills_20261016/reports'
output = reports / (args.tag + '_full_submission.json')
assert not output.exists(), 'Inspect the existing receipt instead of duplicating a submission'
prior = json.loads((reports / (args.source_tag + '_full_submission.json')).read_text())
startup = prior['startup_proof']
assert startup['first_physical_request']['sim_steps'] > 0
assert subprocess.check_output(['sacct', '-X', '-n', '-j', startup['job'],
    '--format=State,ExitCode', '-P'], text=True).strip() == 'COMPLETED|0:0'
registered = Path(prior['manifest']['path'])
assert hashlib.sha256(registered.read_bytes()).hexdigest() == prior['manifest']['sha256']
manifest = args.manifest or registered
assert manifest.is_absolute() and manifest.is_file()
plan = json.loads(manifest.read_text())
assert not plan['training'] and not plan['confirmation']
canonical_plan = json.loads(registered.read_text())
assert {k: v for k, v in plan.items() if k != 'cases'} == {
    k: v for k, v in canonical_plan.items() if k != 'cases'}
def case_bytes(case):
    return json.dumps(case, sort_keys=True)


assert sorted(map(case_bytes, plan['cases'])) == sorted(map(case_bytes, canonical_plan['cases']))
if args.startup_receipt:
    actual = json.loads(args.startup_receipt.read_text())
    assert actual['snapshot'] == prior['snapshot'] and actual['source_commit'] == prior['source_commit']
    assert actual['manifest'] == {'path': str(manifest),
        'sha256': hashlib.sha256(manifest.read_bytes()).hexdigest()}
    job = actual['job']+'_'+str(actual['indices'][0])
    directory = root/'results/bounded_skills/feasibility_20261017'/('job'+job)
    rows = [json.loads(line) for line in (directory/'episodes.jsonl').read_text().splitlines()]
    assert len(rows) == 1 and rows[0]['status'] == 'startup_physical'
    physical = json.loads(next(directory.glob('*oracle*/first_physical_request.json')).read_text())
    assert physical['sim_steps'] > 0
    assert subprocess.check_output(['sacct', '-X', '-n', '-j', job,
        '--format=State,ExitCode', '-P'], text=True).strip() == 'COMPLETED|0:0'
    startup = {'job': job, 'summary': rows[0], 'first_physical_request': physical,
        'submission': str(args.startup_receipt), 'state_exit': 'COMPLETED|0:0'}
indices = []
for part in args.indices.split(','):
    ends = [int(value) for value in part.split('-')]
    assert len(ends) in (1, 2)
    indices.extend(range(ends[0], ends[-1]+1))
assert len(indices) == len(set(indices)) and all(0 <= index < len(plan['cases']) for index in indices)
source = Path(prior['snapshot'])
launcher = source / 'scripts/run_bounded_21f0744_20261017.sbatch'
assert source.is_absolute() and launcher.is_file()
rows = [line.split('|') for line in subprocess.check_output(['squeue', '-r', '-h',
    '-u', 'sunyihan', '-o', '%i|%j|%T|%N|%b|%R'], text=True).splitlines()]
ours = [row for row in rows if row[1].startswith('rd-bounded-')
    and not row[1].startswith('rd-bounded-choice-')]
active = [row for row in ours if row[2] == 'RUNNING']
assert len(active) <= 4 and all(row[3] == 'node02' for row in active)
c2 = [row for row in rows if row[1].startswith(('rd-bounded-choice-', 'rd-c2-'))
    and row[2] in {'PENDING', 'RUNNING'} and 'gpu' in row[4].lower()]
cap = 3 if c2 else 4
capacity = max(1, cap-len(active))
dependency = 'afterany:' + (':'.join(row[0] for row in active)
    if len(active) >= cap else startup['job'])
arguments = ['sbatch', '--parsable', '--nodelist=node02', '--nice=500',
    '--array='+args.indices+'%'+str(capacity), '--dependency='+dependency,
    '--export=ALL,SOURCE='+str(source)+',SOURCE_COMMIT='+prior['source_commit']
    +',MANIFEST='+str(manifest)+',SHARD_COUNT=220,STARTUP=0,PAIR_LEGACY=0,PROBE_ARMS=oracle_k4',
    str(launcher)]
job = subprocess.check_output(arguments, text=True).strip().split(';')[0]
report = {'job': job, 'mode': 'full', 'arguments': arguments, 'source_commit': prior['source_commit'],
    'snapshot': str(source), 'manifest': {'path': str(manifest),
        'sha256': hashlib.sha256(manifest.read_bytes()).hexdigest()}, 'indices': indices,
    'registered_unique_states': len(indices), 'same_source_state_reuse': [], 'startup_proof': startup,
    'scope': 'original-state oracle K4 development cohorts; pi0.5 disabled',
    'submission_script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    'aggregate_cap': cap, 'queue_before': ours, 'training': False, 'confirmation': False}
with output.open('x') as stream:
    json.dump(report, stream, indent=2)
    stream.write('\n')
print(json.dumps({key: report[key] for key in ('job', 'registered_unique_states', 'source_commit')}))
