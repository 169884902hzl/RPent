"""Deploy the tested instance correction in the existing third GPU lane."""
import argparse
import hashlib
import json
import os
import subprocess
import tarfile
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument('--commit', required=True)
parser.add_argument('--archive-sha256', required=True)
args = parser.parse_args()
root = Path('/public/home/sunyihan/rpent_libero_eval')
short = args.commit[:7]
archive = root/f'bounded_{short}_20261018_code.tar.gz'
assert hashlib.sha256(archive.read_bytes()).hexdigest() == args.archive_sha256
source = root/f'source_bounded_{short}_20261018'
source.mkdir()
with tarfile.open(archive) as stream:
    stream.extractall(source)
prep = root/'results/bounded_skills/feasibility_20261017/preparation'
plan = json.loads((prep/'original20_manifest_9e03b06_single_sample.json').read_text())
plan['source_commit'] = args.commit
plan['source_snapshot'] = {'path': str(source), 'code_archive_sha256': args.archive_sha256}
manifest = prep/f'original20_manifest_{short}_missing_view.json'
manifest.write_text(json.dumps(plan, indent=2)+'\n')
environment = os.environ.copy()
environment.update(PYTHONPATH=str(source), LIBERO_TYPE='standard',
    LIBERO_CONFIG_PATH=str(root/'runtime_config'), CUDA_VISIBLE_DEVICES='', OPENBLAS_NUM_THREADS='1')
preflight = subprocess.run([str(root/'.venv/bin/python'), '-m', 'scripts.v5_probe_preflight',
    '--manifest', str(manifest), '--states'], cwd=source, env=environment, capture_output=True, text=True)
log = prep/f'preflight_{short}_20261018.log'
log.write_text(preflight.stdout+preflight.stderr)
assert preflight.returncode == 0, preflight.stderr
queue = subprocess.check_output(['squeue', '-r', '-h', '-u', 'sunyihan',
    '-o', '%i|%j|%T|%N'], text=True)
active = [line.split('|') for line in queue.splitlines()
    if line.split('|')[1].startswith('rd-bounded-') and line.split('|')[2] != 'COMPLETING']
assert {row[0].split('_')[0] for row in active} <= {'8109', '8117'}, active
launcher = source/'scripts/run_bounded_21f0744_20261017.sbatch'
arguments = ['sbatch', '--parsable', '--nodelist=node02', '--nice=500', '--array=22%1',
    '--export=ALL,SOURCE='+str(source)+',SOURCE_COMMIT='+args.commit+',MANIFEST='+str(manifest)+',STARTUP=1',
    str(launcher)]
job = subprocess.check_output(arguments, text=True).strip()
report = {'scope': 'original-scene development startup; not a whole-task result',
    'source_commit': args.commit, 'snapshot': str(source), 'archive_sha256': args.archive_sha256,
    'manifest': str(manifest), 'manifest_sha256': hashlib.sha256(manifest.read_bytes()).hexdigest(),
    'base_config': plan['base_config'], 'preflight': {'exit_code': preflight.returncode, 'log': str(log)},
    'startup_job': job, 'launcher': str(launcher), 'arguments': arguments,
    'queue_before': active, 'gpu_lanes': ['8109', '8117', job], 'aggregate_cap': 3,
    'training': False, 'confirmation': False, 'pi05_in_oracle': False}
output = root/'coordination/bounded_skills_20261016/reports'/f'missing_view_{short}_submission_20261018.json'
output.write_text(json.dumps(report, indent=2)+'\n')
print(json.dumps(report, indent=2))
