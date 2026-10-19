"""Read existing request timers and disjoint episode wall attribution on CPU."""
import hashlib
import json
import re
from collections import defaultdict
from pathlib import Path

import numpy as np

root = Path('/public/home/sunyihan/rpent_libero_eval')
base = root / 'coordination/bounded_skills_20261016'
source = base / 'reports/original20_support_interim_r18_20261019.json'
cohort = json.loads(source.read_bytes())
groups = defaultdict(list)
records = []
for episode in cohort['cohort']['rows']:
    ledger = Path(episode['record'])
    choices, = ledger.parent.glob('*oracle_k4/choices.jsonl')
    digest, times = hashlib.sha256(), []
    with choices.open('rb') as stream:
        for line in stream:
            digest.update(line)
            matches = re.findall(rb'"request_generation_s"\s*:\s*([0-9.eE+-]+)', line)
            if len(matches) > 1:
                raise ValueError('ambiguous per-request timer')
            if matches:
                times.append(float(matches[0]))
    breakdown = episode['wall_time_breakdown']
    exclusive = breakdown['main_thread_exclusive_s']
    attribution = {name: sum(value for key, value in exclusive.items()
        if key.startswith(prefix)) for name, prefix in (
            ('perception_s', 'perception.'), ('planning_s', 'planning.'),
            ('simulation_s', 'simulation.'), ('oracle_s', 'decision.oracle'),
            ('pi05_s', 'vla.'), ('private_label_s', 'private_labels.'), ('artifact_s', 'artifact_io'))}
    requests = breakdown['calls'].get('planning.request:None', 0)
    request_root = breakdown['main_thread_exclusive_by_root_s'].get('planning.request', {})
    record = {'case': episode['case'], 'category': episode['report_category'],
        'source_commit': cohort['source_commit'], 'choices': str(choices),
        'choices_sha256': digest.hexdigest(), 'logged_request_wall_s': times,
        'root_request_calls': requests, 'root_request_client_s': sum(request_root.values()),
        'wall_s': breakdown['wall_s'], 'exclusive': attribution,
        'main_thread_unattributed_s': breakdown['main_thread_unattributed_s']}
    records.append(record)
    groups[record['category']].append(record)

def distribution(values):
    return {'n': len(values), 'median': float(np.median(values)) if values else None,
        'p90': float(np.quantile(values, .9)) if values else None,
        'max': max(values) if values else None}

summary = []
for category, rows in sorted(groups.items()):
    wall = sum(row['wall_s'] for row in rows)
    exclusive = {key: sum(row['exclusive'][key] for row in rows) for key in rows[0]['exclusive']}
    summary.append({'category': category, 'episodes': len(rows),
        'request_client_wall_s': distribution([t for row in rows for t in row['logged_request_wall_s']]),
        'wall_s': distribution([row['wall_s'] for row in rows]),
        'exclusive_total_s': exclusive,
        'exclusive_wall_fraction': {key: value/wall for key, value in exclusive.items()}})
report = {'scope': 'existing source-pinned original episodes; no new performance intervention or simulation',
    'cohort': {'path': str(source), 'sha256': hashlib.sha256(source.read_bytes()).hexdigest()},
    'source_commit': cohort['source_commit'], 'summary': summary, 'records': records,
    'physics_steps': 0, 'rpc_calls': 0, 'gpu_used': False, 'training': False,
    'interpretation': 'Request wall includes perception and consequences. Exclusive episode categories do not overlap. Cross-category timing is not a paired optimization effect.',
    'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
output = base / 'reports/original_request_costs_CPU_20261019.json'
with output.open('x') as stream:
    json.dump(report, stream, indent=2)
    stream.write('\n')
print(json.dumps({'output': str(output), 'episodes': len(records), 'summary': summary}))
