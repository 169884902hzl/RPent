# Copyright 2026 Zhilun Hu.
# SPDX-License-Identifier: Apache-2.0
"""Freeze named development outcomes without replacing earlier evidence."""
import argparse
import hashlib
import json
import subprocess
from collections import Counter
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

parser = argparse.ArgumentParser()
parser.add_argument('--output', type=Path, required=True)
parser.add_argument('--jobs', help='Comma-separated exact job identities; default retains the original probe set')
args = parser.parse_args()
root = Path('/public/home/sunyihan/rpent_libero_eval')
jobs = ('9472_0', '9472_1', '9472_2', '9507_0', '9507_1',
        '9502_160', '9502_161', '9504_120', '9504_140', '9248_19')
if args.jobs:
    jobs = tuple(args.jobs.split(','))
records = []
for job in jobs:
    directory = root/'results/bounded_skills/feasibility_20261017'/('job'+job)
    for choices in directory.glob('*oracle*/choices.jsonl'):
        rows = [json.loads(line) for line in choices.open()]
        summary = choices.parent/'summary.json'
        physical_rows = [row for row in rows if 'receipts' in row]
        record = {'job': job, 'choices_path': str(choices), 'decisions_recorded': len(physical_rows),
            'receipt_reasons': dict(Counter(r['stop_reason'] for row in physical_rows for r in row['receipts'])),
            'skill_sim_steps': dict(Counter()),
            'recent_receipts': [[{k: r[k] for k in ('skill', 'outcome', 'stop_reason', 'steps_used')}
                for r in row['receipts']] for row in physical_rows[-3:]],
            'status': 'incomplete', 'summary': None}
        steps = Counter()
        for row in physical_rows:
            for receipt in row['receipts']:
                steps[receipt['skill']] += receipt['steps_used']
        record['skill_sim_steps'] = dict(steps)
        if summary.exists():
            record.update(status='physical_result', summary=json.loads(summary.read_text()),
                summary_path=str(summary), summary_sha256=hashlib.sha256(summary.read_bytes()).hexdigest(),
                choices_sha256=hashlib.sha256(choices.read_bytes()).hexdigest())
        records.append(record)
queue = [line.split('|') for line in subprocess.check_output(['squeue', '-r', '-h',
    '-u', 'sunyihan', '-o', '%i|%j|%T|%N|%b|%R'], text=True).splitlines()]
ours = [row for row in queue if row[1].startswith('rd-bounded-')
    and not row[1].startswith('rd-bounded-choice-') and row[2] == 'RUNNING']
c2 = [row for row in queue if row[1].startswith(('rd-bounded-choice-', 'rd-c2-'))
    and row[2] in {'RUNNING', 'PENDING'} and 'gpu' in row[4].lower()]
report = {'time_pacific': datetime.now(ZoneInfo('America/Los_Angeles')).isoformat(),
    'records': records, 'running': ours, 'codex2_gpu': c2, 'aggregate_cap': 3 if c2 else 4,
    'accounting': subprocess.check_output(['sacct', '-X', '-n', '-j', ','.join(jobs),
        '--format=JobID%32,State%32,ExitCode,Elapsed,NodeList', '-P'], text=True).splitlines(),
    'training': False, 'confirmation': False,
    'scope': 'Original-state development results; incomplete episodes excluded from success denominators'}
with args.output.open('x') as stream:
    json.dump(report, stream, indent=2)
    stream.write('\n')
for record in records:
    summary = record['summary'] or {}
    print(json.dumps({'job': record['job'], 'status': record['status'],
        'success': summary.get('success'), 'physical_chunks_recorded': record['decisions_recorded'],
        'summary_decisions': summary.get('decisions'),
        'sim_steps': summary.get('sim_steps'), 'wall_s': summary.get('wall_s')}))
