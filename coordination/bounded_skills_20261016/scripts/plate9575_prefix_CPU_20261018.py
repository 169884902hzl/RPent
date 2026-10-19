"""Inspect a real directional-contact prefix without stepping or RPC."""
# ruff: noqa: E402 -- pin the recorded source before restoring captured classes
import copy
import hashlib
import json
import os
import sys
import time
from pathlib import Path

os.environ.update(CUDA_VISIBLE_DEVICES='', OPENBLAS_NUM_THREADS='1')
root = Path('/public/home/sunyihan/rpent_libero_eval')
source = root/'source_bounded_chunk_v3_directional_contact_20261018_4db4ea4'
sys.path.insert(0, str(source))
from robots.libero.bounded_chunk import PublicPrefixPrediction
from robots.libero.bounded_offline_labels import annotate_prefix, load_annotation_state

directory, = (root/'results/bounded_skills/feasibility_20261017/job9575_160').glob('*oracle_k4')
path = directory/'choices.jsonl'
raw = path.read_bytes()
row = json.loads(raw.splitlines()[0])
reference = row['private_prefix_annotation_state']
state = load_annotation_state(reference['path'], reference['sha256'])
request = row['request']
cid = row['decision']['candidate_ids'][0]
candidate, = [c for c in request['candidates'] if c['id'] == cid]
started = time.monotonic()
prediction = PublicPrefixPrediction(copy.deepcopy(state['adapter']), request)
prediction.advance(candidate)
context = prediction.context()
labels = annotate_prefix(state, request, [cid])
report = {'source': str(source), 'context': reference,
    'choices': {'path': str(path), 'sha256': hashlib.sha256(raw).hexdigest()},
    'prefix_candidate': candidate, 'predicted_robot': context['predicted_robot'],
    'plans': {key: {k: v for k, v in plan.items() if k != 'surface_measurement'}
              for key, plan in prediction.adapter.plans.items()},
    'contact_successors': [c for c in context['candidates']
        if c['skill'] in {'align', 'descend', 'set_gripper', 'observe'}],
    'labels': labels, 'cpu_s': time.monotonic()-started,
    'physics_steps': 0, 'rpc_calls': 0, 'gpu_used': False,
    'training': False, 'confirmation': False,
    'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
output = root/'coordination/bounded_skills_20261016/reports/plate9575_prefix_CPU_20261018.json'
with output.open('x') as stream:
    json.dump(report, stream, indent=2)
    stream.write('\n')
print(json.dumps({'selected': candidate['parameters'], 'cpu_s': report['cpu_s'],
    'labels': labels, 'contact_successors': report['contact_successors']}))
