"""Insert a startup or verified full replay in the existing third GPU lane."""
import argparse
import hashlib
import json
import subprocess
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument('--full', action='store_true')
args = parser.parse_args()
root = Path('/public/home/sunyihan/rpent_libero_eval')
base = root/'coordination/bounded_skills_20261016'
mode = 'full' if args.full else 'startup'
receipt = base/'reports'/f'precontact_{mode}_submission_20261018.json'
assert not receipt.exists(), 'Read the existing submission instead of duplicating it'
preparation = json.loads((base/'reports/precontact_preparation_20261018.json').read_text())
source, manifest = Path(preparation['snapshot']), Path(preparation['manifest']['path'])
assert hashlib.sha256(manifest.read_bytes()).hexdigest() == preparation['manifest']['sha256']
launcher = source/'scripts/run_bounded_21f0744_20261017.sbatch'
assert launcher.exists() and manifest.is_absolute()
if args.full:
    startup = json.loads((base/'reports/precontact_startup_submission_20261018.json').read_text())
    job = startup['job'].split(';')[0]+'_24'
    directory = root/'results/bounded_skills/feasibility_20261017'/('job'+job)
    rows = [json.loads(line) for line in (directory/'episodes.jsonl').open()]
    assert len(rows) == 1 and rows[0]['status'] == 'startup_physical'
    physical = json.loads(next(directory.glob('*oracle*/first_physical_request.json')).read_text())
    assert physical['sim_steps'] > 0
    accounting = subprocess.check_output(['sacct', '-X', '-n', '-j', job,
        '--format=State,ExitCode', '-P'], text=True).strip()
    assert accounting == 'COMPLETED|0:0', accounting
raw = subprocess.check_output(['squeue', '-r', '-h', '-u', 'sunyihan',
    '-o', '%i|%j|%T|%N|%R'], text=True)
ours = [line.split('|') for line in raw.splitlines() if '|rd-bounded-' in line]
running = [r for r in ours if r[2] == 'RUNNING']
assert len(running) <= 3 and all(r[3] == 'node02' for r in running), running
active = [r[0] for r in running if r[0].startswith('8173_')]
assert len(active) == 1, active
following = [r[0] for r in ours if r[0].startswith('8173_') and r[2] == 'PENDING']
assert following and all('JobHeld' not in r[4] for r in ours if r[0] in following)
arguments = ['sbatch', '--parsable', '--nodelist=node02', '--nice=500',
    '--array='+('24,25%1' if args.full else '24%1'), '--dependency=afterany:'+active[0],
    '--export=ALL,SOURCE='+str(source)+',SOURCE_COMMIT='+preparation['source_commit']
    +',MANIFEST='+str(manifest)+',STARTUP='+('0' if args.full else '1'), str(launcher)]
job = subprocess.check_output(arguments, text=True).strip().split(';')[0]
updates = []
for child in following:
    command = ['scontrol', 'update', 'JobId='+child, 'Dependency=afterany:'+job]
    subprocess.run(command, check=True)
    updates.append(command)
report = {'scope': 'original box init4/init5 oracle diagnostics; no training or confirmation',
    'job': job, 'mode': mode, 'arguments': arguments, 'following_updates': updates,
    'snapshot': str(source), 'source_commit': preparation['source_commit'],
    'manifest': preparation['manifest'], 'lane': 3, 'aggregate_cap': 3,
    'queue_before': ours, 'pi05_disabled': True}
if args.full:
    report['startup'] = {'job': startup['job'], 'episode': rows[0],
        'state_exit': accounting, 'first_physical_request': physical}
receipt.write_text(json.dumps(report, indent=2)+'\n')
print(json.dumps({k: report[k] for k in ['job', 'mode', 'source_commit', 'snapshot', 'lane']}))
