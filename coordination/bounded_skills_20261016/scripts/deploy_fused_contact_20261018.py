"""Deploy the measured contact repair without adding a fourth GPU lane."""
import hashlib
import json
import os
import subprocess
import tarfile
from pathlib import Path

root = Path('/public/home/sunyihan/rpent_libero_eval')
commit = '8e491524af107c82f2951882e25a9d25b205cdb4'
archive = root/'bounded_8e49152_20261018_code.tar.gz'
archive_sha = hashlib.sha256(archive.read_bytes()).hexdigest()
assert archive_sha == 'fbd253fed0a60c3243d1bea68bb488460b7ba4e53829dede758d54a449971365'
source = root/'source_bounded_8e49152_20261018'
source.mkdir()
with tarfile.open(archive) as stream:
    stream.extractall(source)
prep = root/'results/bounded_skills/feasibility_20261017/preparation'
plan = json.loads((prep/'original20_manifest_7e2e869_contact_extent.json').read_text())
plan['source_commit'] = commit
plan['source_snapshot'] = {'path': str(source), 'code_archive_sha256': archive_sha}
manifest = prep/'original20_manifest_8e49152_fused_contact.json'
manifest.write_text(json.dumps(plan, indent=2)+'\n')
environment = os.environ.copy()
environment.update(PYTHONPATH=str(source), LIBERO_TYPE='standard',
    LIBERO_CONFIG_PATH=str(root/'runtime_config'), CUDA_VISIBLE_DEVICES='', OPENBLAS_NUM_THREADS='1')
preflight = subprocess.run([str(root/'.venv/bin/python'), '-m', 'scripts.v5_probe_preflight',
    '--manifest', str(manifest), '--states'], cwd=source, env=environment, capture_output=True, text=True)
log = prep/'preflight_8e49152_20261018.log'
log.write_text(preflight.stdout+preflight.stderr)
assert preflight.returncode == 0, preflight.stderr
queue = subprocess.check_output(['squeue', '-r', '-h', '-u', 'sunyihan',
    '-o', '%i|%j|%T|%N'], text=True)
active = [line.split('|') for line in queue.splitlines()
    if line.split('|')[1].startswith('rd-bounded-')]
assert {row[0].split('_')[0] for row in active} <= {'8117', '8145', '8147', '8151'}, active
replaced = [row for row in active if row[0].split('_')[0] == '8147'
    and int(row[0].split('_')[1]) >= 24]
assert all(row[2] == 'PENDING' for row in replaced), replaced
if replaced:
    subprocess.run(['scancel', *[row[0] for row in replaced]], check=True)
arguments = ['sbatch', '--parsable', '--nodelist=node02', '--nice=500', '--array=21%1',
    '--dependency=afterany:8147',
    '--export=ALL,SOURCE='+str(source)+',SOURCE_COMMIT='+commit+',MANIFEST='+str(manifest)+',STARTUP=1',
    str(source/'scripts/run_bounded_21f0744_20261017.sbatch')]
job = subprocess.check_output(arguments, text=True).strip()
report = {'job': job, 'arguments': arguments, 'source_commit': commit,
    'snapshot': str(source), 'archive_sha256': archive_sha,
    'manifest': {'path': str(manifest), 'sha256': hashlib.sha256(manifest.read_bytes()).hexdigest()},
    'preflight': {'exit_code': preflight.returncode, 'log': str(log)},
    'scope': 'same-launcher original can init1 startup; oracle, pi05 disabled; not training or confirmation',
    'replaced_pending': replaced, 'replacement_reason': 'current measured contact membership repairs pre-lift route; preserve all running work and raw results',
    'queue_before': active, 'aggregate_cap': 3,
    'cpu_checks': {'bounded_screen_payload_geometry': 217}}
output = root/'coordination/bounded_skills_20261016/reports/fused_contact_submission_20261018.json'
output.write_text(json.dumps(report, indent=2)+'\n')
print(json.dumps(report, indent=2))
