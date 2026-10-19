"""Test whether a zero-control chunk guard is mistaken for a failed lift."""
# ruff: noqa: E402 -- pin CPU/source first
import hashlib
import inspect
import json
import os
import sys
import textwrap
from pathlib import Path

os.environ.update(CUDA_VISIBLE_DEVICES='', OPENBLAS_NUM_THREADS='1')
root = Path('/public/home/sunyihan/rpent_libero_eval')
source = root/'source_bounded_chunk_v3_transport_identity_20261018_94db13e'
sys.path.insert(0, str(source))
from robots.libero import bounded_oracle
from robots.libero.bounded_offline_labels import annotate_prefix, load_annotation_state

directory, = (root/'results/bounded_skills/feasibility_20261017/job9515_4').glob('*oracle_k4')
row = json.loads((directory/'choices.jsonl').read_bytes().splitlines()[1])
reference = row['private_prefix_annotation_state']
state = load_annotation_state(reference['path'], reference['sha256'])
original = bounded_oracle.BoundedOracle._choose_one
code = textwrap.dedent(inspect.getsource(original))
old = "failed_lift = last and last['skill'] == 'lift' and last['outcome'] != 'success'"
new = (old + " and not (last.get('steps_used') == 0 and last.get('stop_reason') == 'predicted_anchor_changed')")
assert code.count(old) == 1
code = code.replace(old, new)
namespace = dict(vars(bounded_oracle))
exec(compile(code, '<cpu_zero_control_lift_guard>', 'exec'), namespace)
results = []
try:
    for name, method in [('baseline', original), ('zero_control_guard_is_not_failed_contact', namespace['_choose_one'])]:
        bounded_oracle.BoundedOracle._choose_one = method
        result = annotate_prefix(state, row['request'], [])
        option = next(c for c in row['request']['candidates'] if c['id'] == result['selected'])
        results.append({'method': name, 'labels': result, 'selected': option})
        print(json.dumps({'method': name, 'selected_skill': option['skill'],
            'parameters': option['parameters'], 'legal_n': len(result['legal']),
            'acceptable_n': len(result['rule_acceptable'])}), flush=True)
finally:
    bounded_oracle.BoundedOracle._choose_one = original
report = {'source': str(source), 'job': '9515_4', 'row': 1, 'context': reference,
    'results': results, 'candidate_method': code, 'physics_steps': 0, 'gpu_used': False,
    'rpc_calls': 0, 'scope': 'Private CPU oracle-rule diagnostic; no changed public candidate or physical outcome',
    'training': False, 'confirmation': False,
    'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
output = root/'coordination/bounded_skills_20261016/reports/box9515_guard_lift_CPU_20261018.json'
with output.open('x') as stream:
    json.dump(report, stream, indent=2)
    stream.write('\n')
