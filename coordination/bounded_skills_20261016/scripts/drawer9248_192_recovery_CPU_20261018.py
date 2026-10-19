"""Check the lost-binding recovery on the preserved terminal public request."""
# ruff: noqa: E402 -- pinned CPU-only diagnostic, no environment startup
import argparse
import hashlib
import json
import os
import sys
import time
from pathlib import Path

os.environ.update(CUDA_VISIBLE_DEVICES='', OPENBLAS_NUM_THREADS='1')
parser = argparse.ArgumentParser()
parser.add_argument('--source', type=Path, required=True)
parser.add_argument('--output', type=Path, required=True)
args = parser.parse_args()
sys.path.insert(0, str(args.source))
from robots.libero.bounded_offline_labels import annotate_prefix, load_annotation_state

root = Path('/public/home/sunyihan/rpent_libero_eval')
before_path = root/'coordination/bounded_skills_20261016/reports/drawer9248_192_terminal_CPU_20261018.json'
before = json.loads(before_path.read_bytes())
raw = Path(before['choices']['path']).read_bytes()
assert hashlib.sha256(raw).hexdigest() == before['choices']['sha256']
row = json.loads(raw.splitlines()[before['terminal_request_index']])
reference = row['private_prefix_annotation_state']
assert reference == before['context']
state = load_annotation_state(reference['path'], reference['sha256'])
started = time.monotonic()
labels = annotate_prefix(state, row['request'], [])
elapsed = time.monotonic()-started
candidate, = [c for c in row['request']['candidates'] if c['id'] == labels['selected']]
assert candidate['skill'] == 'set_gripper' and candidate['parameters'] == {'mode': 'open'}
assert labels['legal'] == before['labels']['legal']
assert labels['rule_acceptable'] == [candidate['id']]
assert labels['judge'] == 'libero-private-task-progress-rules/13'
assert state['adapter'].active is None and state['adapter'].held is None
report = {'source': str(args.source), 'before_report': str(before_path),
    'before_report_sha256': hashlib.sha256(before_path.read_bytes()).hexdigest(),
    'context': reference, 'request_sha256': labels['request_sha256'],
    'before': before['labels'], 'after': labels, 'cpu_s': elapsed,
    'selected_candidate': candidate, 'public_legal_unchanged': True,
    'physics_steps': 0, 'rpc_calls': 0, 'gpu_used': False,
    'training': False, 'confirmation': False,
    'scope': 'cross-source frozen-context CPU regression; not physical replay or training labels',
    'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
with args.output.open('x') as stream:
    json.dump(report, stream, indent=2)
    stream.write('\n')
print(json.dumps({'output': str(args.output), 'selected': candidate['skill'],
    'parameters': candidate['parameters'], 'cpu_s': elapsed,
    'legal_unchanged': True, 'judge': labels['judge']}))
