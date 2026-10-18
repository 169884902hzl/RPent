"""Queue one original-box physical startup after the representative checks."""
import hashlib
import json
import subprocess
from pathlib import Path

root = Path('/public/home/sunyihan/rpent_libero_eval')
base = root / 'coordination/bounded_skills_20261016'
checked = json.loads((base / 'reports/real_box_coverage_r2_CPU_20261018.json').read_text())
receipt = base / 'reports/real_box_startup_submission_20261018.json'
assert not receipt.exists(), 'Use the existing submission receipt'
manifest = Path(checked['manifest']['path'])
assert hashlib.sha256(manifest.read_bytes()).hexdigest() == checked['manifest']['sha256']
plan = json.loads(manifest.read_text())
source = Path(checked['source_snapshot']['path'])
launcher = source / 'scripts/run_bounded_21f0744_20261017.sbatch'
assert launcher.is_file() and launcher.is_absolute()
assert checked['preflight_exit_code'] == 0 and len(plan['cases']) == 20
assert checked['runtime_states_equal_registered_original_file']
assert plan['training'] is False and plan['confirmation'] is False
arguments = [
    'sbatch', '--parsable', '--nodelist=node02', '--nice=500', '--array=0%1',
    '--dependency=afterany:8846:8860_24',
    '--export=ALL,SOURCE=' + str(source) + ',SOURCE_COMMIT=' + plan['source_commit']
    + ',MANIFEST=' + str(manifest) + ',SHARD_COUNT=20,STARTUP=1,PAIR_LEGACY=0',
    str(launcher),
]
job = subprocess.check_output(arguments, text=True).strip().split(';')[0]
report = {
    'job': job, 'mode': 'startup', 'arguments': arguments,
    'source_snapshot': str(source), 'source_commit': plan['source_commit'],
    'manifest': checked['manifest'], 'case': plan['cases'][0],
    'physical_validation': 'pending first physical request',
    'formal_array_submitted': False, 'training': False, 'confirmation': False,
    'scope': 'supplemental original real-box feasibility; existing220 unchanged',
    'submission_script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
}
with receipt.open('x') as stream:
    json.dump(report, stream, indent=2)
    stream.write('\n')
print(json.dumps(report))
