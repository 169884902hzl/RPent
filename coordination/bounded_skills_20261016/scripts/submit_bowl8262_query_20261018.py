"""Insert two public-image SAM queries in the first serial GPU lane."""
import hashlib
import json
import subprocess
from pathlib import Path

root = Path('/public/home/sunyihan/rpent_libero_eval')
base = root/'coordination/bounded_skills_20261016'
receipt = base/'reports/bowl8262_query_submission_20261018.json'
assert not receipt.exists(), 'Inspect existing receipt instead of duplicating submission'
report = json.loads((base/'reports/bowl8262_16_membership_queries_CPU_20261018.json').read_text())
assert report['private_truth_used'] is False and report['controls'] == 0
case, = report['cases']
assert case['job'] == '8262_16' and len(case['queries']) == 2
queries = {'scope': 'interior points from current public SAM and measured instance extent',
    'private_truth_used': False, 'training': False,
    'choices_prefix_sha256': case['prefix_sha256'], 'queries': case['queries']}
query_file = base/'reports/bowl8262_16_registered_points_CPU_20261018.json'
for query in queries['queries']:
    assert hashlib.sha256(Path(query['image']).read_bytes()).hexdigest() == query['image_sha256']
query_file.write_text(json.dumps(queries, indent=2)+'\n')
raw = subprocess.check_output(['squeue', '-r', '-h', '-u', 'sunyihan',
    '-o', '%i|%j|%T|%N|%R'], text=True)
ours = [line.split('|') for line in raw.splitlines() if '|rd-bounded-' in line]
running = [row for row in ours if row[2] == 'RUNNING']
assert len(running) <= 3 and all(row[3] == 'node02' for row in running)
assert any(row[0] == '8262_60' for row in running)
following = next(row for row in ours if row[0] == '8262_160')
assert following[2] == 'PENDING' and 'JobHeld' not in following[4]
prep = root/'results/bounded_skills/feasibility_20261017/preparation'
launcher = prep/'run_saved_point_query_20261018.sbatch'
script = prep/'saved_point_query_GPU_20261018.py'
subprocess.run([str(root/'.venv/bin/python'), '-m', 'py_compile', str(script)], check=True)
arguments = ['sbatch', '--parsable', '--nodelist=node02', '--nice=500',
    '--dependency=afterany:8262_60',
    '--export=ALL,PUBLIC_QUERY_FILE='+str(query_file)+',PUBLIC_QUERY_STEM=bowl8262_16_interior_query',
    str(launcher)]
job = subprocess.check_output(arguments, text=True).strip().split(';')[0]
record = {'job': job, 'arguments': arguments, 'scope': 'saved original public images; zero controls',
    'training': False, 'confirmation': False, 'lane': 1, 'aggregate_cap': 3,
    'query_file': {'path': str(query_file), 'sha256': hashlib.sha256(query_file.read_bytes()).hexdigest()},
    'script_sha256': hashlib.sha256(script.read_bytes()).hexdigest(),
    'launcher_sha256': hashlib.sha256(launcher.read_bytes()).hexdigest()}
receipt.write_text(json.dumps(record, indent=2)+'\n')
update = ['scontrol', 'update', 'JobId=8262_160', 'Dependency=afterany:'+job]
subprocess.run(update, check=True)
record['following_update'] = update
receipt.write_text(json.dumps(record, indent=2)+'\n')
print(json.dumps(record))
