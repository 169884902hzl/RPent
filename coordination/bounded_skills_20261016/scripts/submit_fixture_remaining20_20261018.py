"""Continue the measured fixture representatives to twenty original states."""

import hashlib
import json
import os
import subprocess
from pathlib import Path

root = Path('/public/home/sunyihan/rpent_libero_eval')
base = root/'coordination/bounded_skills_20261016'
output = base/'reports/fixture_remaining20_submission_20261018.json'
assert not output.exists(), 'Inspect existing submission; do not duplicate states'
previous = json.loads((base/'reports/handle_overlap_full_submission_20261018.json').read_text())
source, manifest = Path(previous['snapshot']), Path(previous['manifest']['path'])
assert hashlib.sha256(manifest.read_bytes()).hexdigest() == previous['manifest']['sha256']
launcher = source/'scripts/run_bounded_21f0744_20261017.sbatch'
assert launcher.is_file()
proof = []
for task, category in ((80, 'drawer_close'), (180, 'stove_off'), (200, 'stove_on')):
    p = root/f'results/bounded_skills/feasibility_20261017/job8184_{task}/episodes.jsonl'
    rows = [json.loads(line) for line in p.open()]
    assert len(rows) == 1 and rows[0]['status'] == 'physical_result'
    assert rows[0]['success'] and rows[0]['pi05_calls'] == 0
    assert rows[0]['case']['category'] == category
    proof.append({'path': str(p), 'sha256': hashlib.sha256(p.read_bytes()).hexdigest(),
                  'episode': rows[0]})
env = os.environ.copy()
env.update(PYTHONPATH=str(source), LIBERO_TYPE='standard', CUDA_VISIBLE_DEVICES='',
           LIBERO_CONFIG_PATH=str(root/'runtime_config'), OPENBLAS_NUM_THREADS='1')
preflight = subprocess.run([str(root/'.venv/bin/python'), '-m', 'scripts.v5_probe_preflight',
    '--manifest', str(manifest), '--states'], cwd=source, env=env, capture_output=True, text=True)
log = base/'reports/fixture_remaining20_preflight_20261018.log'
log.write_text(preflight.stdout+preflight.stderr)
assert preflight.returncode == 0, preflight.stderr
raw = subprocess.check_output(['squeue', '-r', '-h', '-u', 'sunyihan', '-o', '%i|%j|%T|%N'], text=True)
ours = [line.split('|') for line in raw.splitlines() if '|rd-bounded-' in line]
running = [line for line in ours if line[2] == 'RUNNING']
assert len(running) <= 3 and all(line[3] == 'node02' for line in running), running
assert any(line[0].startswith('8192_') for line in ours), 'Refresh the completed lane dependency'
arguments = ['sbatch', '--parsable', '--nodelist=node02', '--nice=500',
    '--array=81-99,181-199,201-219%1', '--dependency=afterany:8192',
    '--export=ALL,SOURCE='+str(source)+',SOURCE_COMMIT='+previous['source_commit']
    +',MANIFEST='+str(manifest)+',STARTUP=0', str(launcher)]
job = subprocess.check_output(arguments, text=True).strip()
report = {'scope': 'original-scene oracle development only; remaining nineteen states per category',
    'training': False, 'confirmation': False, 'pi05_disabled': True,
    'source_commit': previous['source_commit'], 'snapshot': str(source),
    'manifest': previous['manifest'], 'job': job, 'arguments': arguments,
    'same_source_startup': previous['startup_physical_request'],
    'full_representative_proofs': proof, 'preflight_exit': preflight.returncode,
    'queue_before': ours, 'aggregate_cap': 3, 'lane': 2}
output.write_text(json.dumps(report, indent=2)+'\n')
print(json.dumps({'job': job, 'lane': 2, 'states': 57, 'source_commit': previous['source_commit']}))
