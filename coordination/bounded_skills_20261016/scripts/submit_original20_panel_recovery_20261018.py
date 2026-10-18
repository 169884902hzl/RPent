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
args = parser.parse_args()
root = Path('/public/home/sunyihan/rpent_libero_eval')
reports = root / 'coordination/bounded_skills_20261016/reports'
output = reports / (args.tag + '_full_submission.json')
assert not output.exists(), 'Inspect the existing receipt instead of duplicating a submission'
prior = json.loads((reports / 'chunk_v3_panel_recovery_20261018_full_submission.json').read_text())
startup = prior['startup_proof']
assert startup['first_physical_request']['sim_steps'] > 0
assert subprocess.check_output(['sacct', '-X', '-n', '-j', startup['job'],
    '--format=State,ExitCode', '-P'], text=True).strip() == 'COMPLETED|0:0'
manifest = Path(prior['manifest']['path'])
assert hashlib.sha256(manifest.read_bytes()).hexdigest() == prior['manifest']['sha256']
plan = json.loads(manifest.read_text())
assert not plan['training'] and not plan['confirmation']
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
    'snapshot': str(source), 'manifest': prior['manifest'], 'indices': indices,
    'registered_unique_states': len(indices), 'same_source_state_reuse': [], 'startup_proof': startup,
    'scope': 'original-state oracle K4 development cohorts; pi0.5 disabled',
    'submission_script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    'aggregate_cap': cap, 'queue_before': ours, 'training': False, 'confirmation': False}
with output.open('x') as stream:
    json.dump(report, stream, indent=2)
    stream.write('\n')
print(json.dumps({key: report[key] for key in ('job', 'registered_unique_states', 'source_commit')}))
