"""Pair the closed plate replays with the pinned original oracle cohort."""
import hashlib
import json
from pathlib import Path

base = Path(__file__).resolve().parents[1]
old_path = base/'reports/original20_support_interim_r13_20261018.json'
new_path = base/'reports/plate_directional9576_closed_20261018.json'
old, new = [json.loads(path.read_bytes()) for path in (old_path, new_path)]
old_rows = {row['case']['state_sha256']: row for row in old['cohort']['rows']
    if row['report_category'] == 'plate_push'}
pairs = []
fields = ('success', 'decisions', 'sim_steps', 'wall_s', 'failure_phase',
    'record', 'terminal_diagnostic', 'chunk_truncations', 'skill_attempts')
for after in new['cohort']['rows']:
    before = old_rows[after['case']['state_sha256']]
    assert before['case'] == after['case']
    assert before['status'] == after['status'] == 'physical_result'
    assert before['arm'] == after['arm'] == 'oracle_k4'
    assert before['pi05_calls'] == after['pi05_calls'] == 0
    pairs.append({'case': after['case'],
        'before': {key: before[key] for key in fields},
        'after': {key: after[key] for key in fields}})
assert len(pairs) == len(new['cohort']['rows']) == 2
counts = {name: sum(bool(pair['before']['success']) == first
                    and bool(pair['after']['success']) == second for pair in pairs)
    for name, first, second in [('both_success', True, True), ('improved', False, True),
        ('regressed', True, False), ('both_failure', False, False)]}
output = base/'reports/plate9576_closed_paired_CPU_20261018.json'
report = {'before_source': old['source_commit'], 'after_source': new['source_commit'],
    'inputs': [{'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
        for path in (old_path, new_path)], 'counts': counts, 'pairs': pairs,
    'scope': 'two closed development replays; failures retained; not category qualification',
    'physics_steps_in_analysis': 0, 'training': False, 'confirmation': False,
    'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
with output.open('x') as stream:
    json.dump(report, stream, indent=2)
    stream.write('\n')
print(json.dumps({'output': str(output), 'counts': counts,
    'pairs': [{'name': pair['case']['name'],
        'before_decisions': pair['before']['decisions'], 'after_decisions': pair['after']['decisions'],
        'before_sim_steps': pair['before']['sim_steps'], 'after_sim_steps': pair['after']['sim_steps']}
        for pair in pairs]}))
