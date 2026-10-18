"""Insert two saved public image queries in lane one without exceeding three GPUs."""
import hashlib
import json
import subprocess
from pathlib import Path

root = Path('/public/home/sunyihan/rpent_libero_eval')
base = root/'coordination/bounded_skills_20261016'
receipt = base/'reports/box_interior_query_submission_20261018.json'
assert not receipt.exists(), 'Read the existing submission instead of duplicating it'
query_file = base/'reports/box8173_24_interior_queries_CPU_20261018.json'
queries = json.loads(query_file.read_text())
assert queries['private_truth_used'] is False and len(queries['queries']) == 2
for query in queries['queries']:
    assert hashlib.sha256(Path(query['image']).read_bytes()).hexdigest() == query['image_sha256']
queue = subprocess.check_output(['squeue', '-h', '-u', 'sunyihan', '-o', '%i|%j|%T|%N'], text=True)
ours = [line.split('|') for line in queue.splitlines() if '|rd-bounded-' in line]
running = [row for row in ours if row[2] == 'RUNNING']
assert len(running) <= 3 and all(row[3] == 'node02' for row in running), running
assert any(row[0] == '8262_14' for row in running), running
following = ['8262_16', '8262_60', '8262_160']
for child in following:
    state = subprocess.check_output(['squeue', '-h', '-j', child, '-o', '%T'], text=True).strip()
    assert state == 'PENDING', (child, state)
prep = root/'results/bounded_skills/feasibility_20261017/preparation'
launcher = prep/'run_saved_point_query_20261018.sbatch'
script = prep/'saved_point_query_GPU_20261018.py'
assert launcher.exists() and script.exists()
subprocess.run([str(root/'.venv/bin/python'), '-m', 'py_compile', str(script)], check=True)
arguments = ['sbatch', '--parsable', '--nodelist=node02', '--nice=500',
    '--dependency=afterany:8262_14',
    '--export=ALL,PUBLIC_QUERY_FILE='+str(query_file)+',PUBLIC_QUERY_STEM=box8173_24_interior_query',
    str(launcher)]
job = subprocess.check_output(arguments, text=True).strip().split(';')[0]
updates = []
for child in following:
    command = ['scontrol', 'update', 'JobId='+child, 'Dependency=afterany:'+job]
    subprocess.run(command, check=True)
    updates.append(command)
report = {'scope': 'saved original public images only; zero controls, no training or confirmation',
    'job': job, 'arguments': arguments, 'following_updates': updates,
    'query_file': {'path': str(query_file), 'sha256': hashlib.sha256(query_file.read_bytes()).hexdigest()},
    'script_sha256': hashlib.sha256(script.read_bytes()).hexdigest(),
    'launcher_sha256': hashlib.sha256(launcher.read_bytes()).hexdigest(),
    'aggregate_cap': 3, 'lane': '1: bowl init14 -> saved query -> bowl16/cup/plate -> microwave'}
receipt.write_text(json.dumps(report, indent=2)+'\n')
print(json.dumps(report, indent=2))
