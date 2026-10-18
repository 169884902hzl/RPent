"""Queue six original20 oracle cohorts, reusing three same-source states."""
import hashlib
import json
import subprocess
from collections import Counter
from pathlib import Path

root = Path('/public/home/sunyihan/rpent_libero_eval')
base = root / 'coordination/bounded_skills_20261016'
reports = base / 'reports'
output = reports / 'original20_self_filter_20261018_full_submission.json'
assert not output.exists(), 'Use the existing submission receipt'
prior_path = reports / 'chunk_v3_self_filter_20261018_full_submission.json'
prior = json.loads(prior_path.read_text())
startup = prior['startup_proof']
assert startup['first_physical_request']['sim_steps'] > 0
assert subprocess.check_output([
    'sacct', '-X', '-n', '-j', startup['job'], '--format=State,ExitCode', '-P',
], text=True).strip() == 'COMPLETED|0:0'
manifest = Path(prior['manifest']['path'])
assert hashlib.sha256(manifest.read_bytes()).hexdigest() == prior['manifest']['sha256']
plan = json.loads(manifest.read_text())
assert Counter(c['category'] for c in plan['cases'][:120]) == {
    'bowl_transfer': 20, 'box_transfer': 20, 'container': 20,
    'cup_transfer': 20, 'drawer_close': 20, 'drawer_open': 20,
}
assert not plan['training'] and not plan['confirmation']
reuse_indices = [0, 60, 100]
assert all(index in prior['indices'] for index in reuse_indices)
indices = [index for index in range(120) if index not in reuse_indices]
assert len(indices) == 117
source = Path(prior['snapshot'])
launcher = source / 'scripts/run_bounded_21f0744_20261017.sbatch'
assert source.is_absolute() and launcher.is_file()
arguments = [
    'sbatch', '--parsable', '--nodelist=node02', '--nice=500',
    '--array=1-59,61-99,101-119%3', '--dependency=afterany:' + prior['job'],
    '--export=ALL,SOURCE=' + str(source) + ',SOURCE_COMMIT=' + prior['source_commit']
    + ',MANIFEST=' + str(manifest) + ',SHARD_COUNT=220,STARTUP=0,PAIR_LEGACY=0,PROBE_ARMS=oracle_k4',
    str(launcher),
]
job = subprocess.check_output(arguments, text=True).strip().split(';')[0]
report = {
    'job': job, 'mode': 'full', 'arguments': arguments,
    'source_commit': prior['source_commit'], 'snapshot': str(source),
    'manifest': prior['manifest'], 'indices': indices,
    'startup_proof': startup, 'registered_unique_states': 120,
    'same_source_state_reuse': [
        {'index': index, 'case': plan['cases'][index], 'arm': 'oracle_k4',
         'record': str(root / 'results/bounded_skills/feasibility_20261017'
                       / ('job' + prior['job'] + '_' + str(index)) / 'episodes.jsonl'),
         'rule': 'Use the recorded result, including failure; do not replace it or count twice.'}
        for index in reuse_indices
    ],
    'other_categories': 'Current-source representatives precede their original20 cohorts.',
    'scope': 'six original20 oracle-only development cohorts; pi0.5 disabled',
    'submission_script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    'training': False, 'confirmation': False,
}
with output.open('x') as stream:
    json.dump(report, stream, indent=2)
    stream.write('\n')
print(json.dumps({key: report[key] for key in ('job', 'registered_unique_states', 'source_commit')}))
