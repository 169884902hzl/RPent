"""Replace only the still-pending D2 startup after same-source CPU preflight."""
import hashlib
import json
import os
import subprocess
import tarfile
from pathlib import Path

root = Path('/public/home/sunyihan/rpent_libero_eval')
base = root / 'coordination/bounded_skills_20261016'
commit = '2a869b26f45b0671a70aee66136d19cbc08023be'
archive = root / 'bounded_hybrid_d2_startup_20261019_2a869b26.tar.gz'
archive_sha = '35c61ee663b7cc3191741e1a29bcee9b03157f7742a173e1bcb524152b155b21'
assert hashlib.sha256(archive.read_bytes()).hexdigest() == archive_sha
source = root / 'source_bounded_hybrid_d2_startup_20261019_2a869b26'
if not source.exists():
    source.mkdir()
    with tarfile.open(archive) as stream:
        stream.extractall(source)
manifest = root / 'results/bounded_skills/hybrid_d2_20261019/preparation/D2_hybrid_manifest_2a869b26.json'
env = {**os.environ, 'PYTHONPATH': str(source), 'SOURCE_COMMIT': commit,
       'LIBERO_TYPE': 'pro', 'LIBERO_CONFIG_PATH': str(root / 'runtime_config'),
       'CUDA_VISIBLE_DEVICES': '', 'OPENBLAS_NUM_THREADS': '1'}
command = [str(root / '.venv/bin/python'), '-m', 'scripts.probe_bounded_hybrid_d2',
           '--build-plan', str(manifest)]
assert not manifest.exists(), 'preparation must preserve any existing plan'
checked = subprocess.run(command, cwd=source, env=env, capture_output=True, text=True)
log = manifest.parent / '2a869b26_startup_preflight.log'
log.write_text(checked.stdout + checked.stderr)
checked.check_returncode()
plan = json.loads(manifest.read_bytes())
previous = json.loads((manifest.parent / 'D2_hybrid_manifest_e9aeaf9b.json').read_bytes())
assert plan['cases'] == previous['cases'] and len(plan['cases']) == 40
for path in (manifest, source / 'scripts/run_bounded_hybrid_d2_20261019.sbatch'):
    assert path.is_absolute() and path.is_file()
receipt_path = base / 'reports/hybrid_d2_2a869b26_startup_submission_20261019.json'
assert not receipt_path.exists(), 'do not submit duplicate startup'
old = json.loads((base / 'reports/hybrid_d2_e9aeaf9b_startup_submission_20261019.json').read_text())
old_job = old['job'] + '_' + str(old['startup_index'])
state = subprocess.check_output(['squeue', '-h', '-j', old_job, '-o', '%T|%R'], text=True).strip()
assert state.startswith('PENDING|') and 'JobHeld' not in state, state
arguments = ['sbatch', '--parsable', '--nodelist=node02', '--nice=500', '--array=0%1',
             '--dependency=afterany:9791',
             '--export=ALL,SOURCE='+str(source)+',SOURCE_COMMIT='+commit+',MANIFEST='+str(manifest)+',STARTUP=1',
             str(source / 'scripts/run_bounded_hybrid_d2_20261019.sbatch')]
# Ordinary pending development startup only; no running or held job is touched.
subprocess.run(['scancel', old_job], check=True)
job = subprocess.check_output(arguments, text=True).strip().split(';')[0]
receipt = {'job': job, 'startup_index': 0, 'prerequisite_job': '9791',
           'arguments': arguments, 'source_commit': commit, 'snapshot': str(source),
           'archive_sha256': archive_sha, 'manifest': {'path': str(manifest),
               'sha256': hashlib.sha256(manifest.read_bytes()).hexdigest()},
           'preflight': {'exit_code': checked.returncode, 'log': str(log), 'command': command,
                         'same_forty_registered_case_hashes': True},
           'replaced_pending_startup': old_job, 'replaced_state': state,
           'first_physical_vla_request': 'pending', 'formal_array_submitted': False,
           'scope': 'D2 development only; startup calls VLA directly, no self branch',
           'training': False, 'confirmation': False}
receipt_path.write_text(json.dumps(receipt, indent=2)+'\n')
print(json.dumps(receipt))
