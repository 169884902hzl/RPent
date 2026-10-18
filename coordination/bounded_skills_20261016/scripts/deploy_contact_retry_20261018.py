"""Deploy the tested contact retry fix and queue a same-launcher startup."""
import hashlib
import json
import os
import subprocess
import tarfile
from pathlib import Path

root = Path('/public/home/sunyihan/rpent_libero_eval')
commit = 'c3a78f82331ecd6b6a8030fcf0136c51a966f949'
archive = root/'bounded_contact_retry_c3a78f8_20261018.tar.gz'
archive_sha = hashlib.sha256(archive.read_bytes()).hexdigest()
assert archive_sha == 'd5460718781399dde8fc3961cbbdc4564a6ee0b03b5c6fc8642bab15b2fd75b0'
source = root/'source_bounded_c3a78f8_20261018'
source.mkdir()
with tarfile.open(archive) as stream:
    stream.extractall(source)
prep = root/'results/bounded_skills/feasibility_20261017/preparation'
plan = json.loads((prep/'original20_manifest_fresh_contact_20261018.json').read_text())
plan['source_commit'] = commit
plan['source_snapshot'] = {'path':str(source), 'code_archive_sha256':archive_sha}
manifest = prep/'original20_manifest_contact_retry_20261018.json'
manifest.write_text(json.dumps(plan,indent=2)+'\n')
environment = os.environ.copy()
environment.update(PYTHONPATH=str(source), LIBERO_TYPE='standard',
    LIBERO_CONFIG_PATH=str(root/'runtime_config'), CUDA_VISIBLE_DEVICES='', OPENBLAS_NUM_THREADS='1')
preflight = subprocess.run([str(root/'.venv/bin/python'), '-m', 'scripts.v5_probe_preflight',
    '--manifest',str(manifest),'--states'],cwd=source,env=environment,capture_output=True,text=True)
log = prep/'preflight_contact_retry_20261018.log'
log.write_text(preflight.stdout+preflight.stderr)
assert preflight.returncode == 0, preflight.stderr
queue = subprocess.check_output(['squeue','-h','-u','sunyihan','-o','%i|%j|%T|%N'],text=True)
ours = [line.split('|') for line in queue.splitlines() if line.split('|')[1].startswith('rd-bounded-')]
assert sum(row[2] == 'RUNNING' for row in ours) <= 3
assert all(row[3] == 'node02' for row in ours if row[2] == 'RUNNING')
arguments = ['sbatch','--parsable','--nodelist=node02','--nice=500','--array=160%1',
    '--dependency=afterany:8163',
    '--export=ALL,SOURCE='+str(source)+',SOURCE_COMMIT='+commit+',MANIFEST='+str(manifest)+',STARTUP=1',
    str(source/'scripts/run_bounded_21f0744_20261017.sbatch')]
job = subprocess.check_output(arguments,text=True).strip()
report = {'job':job,'arguments':arguments,'source_commit':commit,'snapshot':str(source),
    'archive_sha256':archive_sha,'manifest':{'path':str(manifest),
        'sha256':hashlib.sha256(manifest.read_bytes()).hexdigest()},
    'preflight':{'exit_code':preflight.returncode,'log':str(log)},'cpu_checks':187,
    'scope':'original plate startup,oracle pi05 disabled;not confirmation or training',
    'aggregate_cap':3,'lane':'1,after8163;other two serial lanes unchanged','queue_before':ours}
output = root/'coordination/bounded_skills_20261016/reports/contact_retry_submission_20261018.json'
output.write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
