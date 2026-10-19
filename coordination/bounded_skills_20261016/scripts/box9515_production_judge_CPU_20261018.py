"""Replay the saved box request with a pinned production oracle, on CPU."""
# ruff: noqa: E402 -- pin the requested source before importing oracle code
import argparse
import hashlib
import json
import os
import sys
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument('--source', type=Path, required=True)
parser.add_argument('--output', type=Path, required=True)
args = parser.parse_args()
source = args.source.resolve(strict=True)
os.environ.update(CUDA_VISIBLE_DEVICES='', OPENBLAS_NUM_THREADS='1')
sys.path.insert(0, str(source))
from robots.libero.bounded_offline_labels import annotate_prefix, load_annotation_state
from robots.libero.bounded_oracle import JUDGE_VERSION

root = Path('/public/home/sunyihan/rpent_libero_eval')
directory, = (root/'results/bounded_skills/feasibility_20261017/job9515_4').glob('*oracle_k4')
choices = directory/'choices.jsonl'
row = json.loads(choices.read_bytes().splitlines()[1])
reference = row['private_prefix_annotation_state']
state = load_annotation_state(reference['path'], reference['sha256'])
labels = annotate_prefix(state, row['request'], [])
candidate = next(c for c in row['request']['candidates'] if c['id'] == labels['selected'])
assert JUDGE_VERSION == 'libero-private-task-progress-rules/11'
assert labels['judge'] == JUDGE_VERSION
assert candidate['skill'] == 'lift' and candidate['parameters']['anchor_id'] == 'e39'
assert labels['selected'] in labels['legal'] and set(labels['rule_acceptable']) <= set(labels['legal'])
baseline = root/'coordination/bounded_skills_20261016/reports/box9515_guard_lift_CPU_20261018.json'
report = {'source': str(source), 'judge': JUDGE_VERSION,
    'source_sha256': hashlib.sha256((source/'robots/libero/bounded_oracle.py').read_bytes()).hexdigest(),
    'choices': {'path': str(choices), 'sha256': hashlib.sha256(choices.read_bytes()).hexdigest()},
    'row': 1, 'context': reference, 'labels': labels, 'selected': candidate,
    'baseline': {'path': str(baseline), 'sha256': hashlib.sha256(baseline.read_bytes()).hexdigest(),
                 'selected_skill': 'set_gripper', 'mode': 'open'},
    'physics_steps': 0, 'gpu_used': False, 'rpc_calls': 0,
    'scope': 'CPU production-rule replay; no physical outcome',
    'training': False, 'confirmation': False,
    'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
with args.output.open('x') as stream:
    json.dump(report, stream, indent=2)
    stream.write('\n')
print(json.dumps({'output': str(args.output), 'judge': JUDGE_VERSION,
    'selected': candidate['skill'], 'parameters': candidate['parameters'],
    'legal_n': len(labels['legal']), 'acceptable_n': len(labels['rule_acceptable'])}))
