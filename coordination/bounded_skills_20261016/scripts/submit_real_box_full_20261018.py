# Copyright 2026 Zhilun Hu.
# SPDX-License-Identifier: Apache-2.0
"""Queue the original real-box cohort after its actual startup has passed."""
import argparse
import hashlib
import json
import subprocess
from pathlib import Path

root = Path('/public/home/sunyihan/rpent_libero_eval')
base = root / 'coordination/bounded_skills_20261016'
reports = base / 'reports'
parser = argparse.ArgumentParser()
parser.add_argument('--startup-receipt', type=Path,
    default=reports / 'real_box_startup_submission_20261018.json')
parser.add_argument('--output', type=Path,
    default=reports / 'real_box20_self_filter_20261018_full_submission.json')
parser.add_argument('--after', help='Existing predecessor array; no held jobs are released')
args = parser.parse_args()
output = args.output
assert not output.exists(), 'Use the existing submission receipt'
startup = json.loads(args.startup_receipt.read_text())
job_id = startup['job'] + '_0'
assert subprocess.check_output([
    'sacct', '-X', '-n', '-j', job_id, '--format=State,ExitCode', '-P',
], text=True).strip() == 'COMPLETED|0:0'
ledger = root / 'results/bounded_skills/feasibility_20261017' / ('job' + job_id) / 'episodes.jsonl'
records = [json.loads(line) for line in ledger.read_text().splitlines()]
proof, = records
assert proof['status'] == 'startup_physical' and proof['sim_steps'] > 0
assert proof['pi05_calls'] == 0
manifest = Path(startup['manifest']['path'])
assert hashlib.sha256(manifest.read_bytes()).hexdigest() == startup['manifest']['sha256']
plan = json.loads(manifest.read_text())
assert len(plan['cases']) == 20 and plan['cases'][0] == proof['case']
assert not plan['training'] and not plan['confirmation']
assert {case['category'] for case in plan['cases']} == {'box_grab_place'}
assert len({(case['bddl']['sha256'], case['state_sha256']) for case in plan['cases']}) == 20
source = Path(startup.get('snapshot', startup.get('source_snapshot')))
launcher = source / 'scripts/run_bounded_21f0744_20261017.sbatch'
assert source.is_absolute() and launcher.is_file()
prior = json.loads((reports / 'original20_self_filter_20261018_full_submission.json').read_text())
arguments = [
    'sbatch', '--parsable', '--nodelist=node02', '--nice=500', '--array=0-19%3',
    '--dependency=afterany:' + (args.after or prior['job']),
    '--export=ALL,SOURCE=' + str(source) + ',SOURCE_COMMIT=' + startup['source_commit']
    + ',MANIFEST=' + str(manifest) + ',SHARD_COUNT=20,STARTUP=0,PAIR_LEGACY=0,PROBE_ARMS=oracle_k4',
    str(launcher),
]
job = subprocess.check_output(arguments, text=True).strip().split(';')[0]
report = {'job': job, 'mode': 'full', 'arguments': arguments, 'indices': list(range(20)),
    'source_commit': startup['source_commit'], 'snapshot': str(source), 'manifest': startup['manifest'],
    'startup_proof': {'job': job_id, 'summary': proof, 'raw_ledger': str(ledger),
        'ledger_sha256': hashlib.sha256(ledger.read_bytes()).hexdigest()},
    'registered_unique_states': 20, 'training': False, 'confirmation': False,
    'startup_reuse': 'Startup is excluded; all twenty formal states run from reset.',
    'scope': 'original cream-cheese-box oracle-only development; pi0.5 disabled',
    'submission_script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
with output.open('x') as stream:
    json.dump(report, stream, indent=2)
    stream.write('\n')
print(json.dumps({key: report[key] for key in ('job', 'registered_unique_states', 'source_commit')}))
