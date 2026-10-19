"""Compare the old terminal public request with the current private selector."""
# ruff: noqa: E402 -- pin the selector and use CPU only
import hashlib
import json
import os
import sys
import time
from pathlib import Path

os.environ.update(CUDA_VISIBLE_DEVICES='', OPENBLAS_NUM_THREADS='1')
root = Path('/public/home/sunyihan/rpent_libero_eval')
source = root/'source_bounded_chunk_v3_panel_joint_room_20261018_184ba1d7'
sys.path.insert(0, str(source))
from robots.libero.bounded_offline_labels import annotate_prefix, load_annotation_state

directory, = (root/'results/bounded_skills/feasibility_20261017/job9248_192').glob('*oracle_k4')
choices = directory/'choices.jsonl'
raw = choices.read_bytes()
rows = [json.loads(line) for line in raw.splitlines()]
row = rows[-1]
assert row.get('event') and 'receipts' not in row
reference = row['private_prefix_annotation_state']
state = load_annotation_state(reference['path'], reference['sha256'])
started = time.monotonic()
labels = annotate_prefix(state, row['request'], [])
adapter = state['adapter']
output = root/'coordination/bounded_skills_20261016/reports/drawer9248_192_terminal_CPU_20261018.json'
report = {'diagnostic_selector_source': str(source), 'original_source_commit': 'ec89f74',
    'choices': {'path': str(choices), 'sha256': hashlib.sha256(raw).hexdigest()},
    'context': reference, 'terminal_request_index': row['index'],
    'cpu_s': time.monotonic()-started, 'labels': labels,
    'active': adapter.active, 'held': adapter.held,
    'plans': {key: {k: v for k, v in value.items() if k not in ('surface_measurement', 'handle_measurement')}
        for key, value in adapter.plans.items()},
    'private_bindings': {'bindings': state['binding'].get('_bindings', {}),
        'peers': {key: sorted(peers) for key, peers in state['binding'].get('_binding_peers', {}).items()}},
    'private_goals': state['private_status'],
    'public_candidates': [{'id': c['id'], 'skill': c['skill'], 'parameters': c['parameters'],
        'recent_failures': c['recent_failures'], 'last_failure': c['last_failure']}
        for c in row['request']['candidates']],
    'receipts': [receipt for r in rows for receipt in r.get('receipts', [])],
    'scope': 'cross-source CPU diagnosis; not physical replay, source-matched labels, or training data',
    'physics_steps': 0, 'rpc_calls': 0, 'gpu_used': False, 'training': False,
    'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
with output.open('x') as stream:
    json.dump(report, stream, indent=2)
    stream.write('\n')
print(json.dumps({'output': str(output), 'cpu_s': report['cpu_s'],
    'active': adapter.active, 'plans': list(adapter.plans), 'labels': labels,
    'gripper_candidates': [c for c in report['public_candidates'] if c['skill'] == 'set_gripper']}))
