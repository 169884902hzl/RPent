"""Compare complete measured-handle re-entry routes on saved public geometry."""
# ruff: noqa: E402 -- pin CPU/source before optional robot imports
import copy
import hashlib
import inspect
import json
import os
import sys
import textwrap
import time
from collections import Counter
from pathlib import Path

os.environ.update(CUDA_VISIBLE_DEVICES='', OPENBLAS_NUM_THREADS='1')
root = Path('/public/home/sunyihan/rpent_libero_eval')
source = root/'source_bounded_chunk_v3_transport_identity_20261018_94db13e'
sys.path.insert(0, str(source))
from robots.libero import bounded_skills
from robots.libero.bounded_offline_labels import load_annotation_state

original = bounded_skills.MeasuredSkillAdapter._screen_fixture_approaches
code = textwrap.dedent(inspect.getsource(original))
old = "for rotate_at in ('entry', 'clearance'):"
assert code.count(old) == 1
code = code.replace(old, "for rotate_at in ('entry', 'clearance', 'entry_direct', 'current_direct'):")
old = "                route.append({'xyz_m': contact.tolist(), 'quat_xyzw': quat})"
new = """                if rotate_at == 'entry_direct':
                    route = [route[2], route[3]]
                elif rotate_at == 'current_direct':
                    route = [{'xyz_m': robot['eef_xyz_m'], 'quat_xyzw': quat}, route[3]]
                route.append({'xyz_m': contact.tolist(), 'quat_xyzw': quat})"""
assert code.count(old) == 1
code = code.replace(old, new)
namespace = dict(vars(bounded_skills))
exec(compile(code, '<cpu_complete_handle_reentry>', 'exec'), namespace)
variant = namespace['_screen_fixture_approaches']
directory, = (root/'results/bounded_skills/feasibility_20261017/job9513_120').glob('*oracle_k4')
rows = [json.loads(line) for line in (directory/'choices.jsonl').read_bytes().splitlines()]
records = []
for index in (6, 14):
    row = rows[index]
    ref = row['private_prefix_annotation_state']
    frozen = load_annotation_state(ref['path'], ref['sha256'])
    handle, = [item['measurement'] for item in row['candidate_screen_diagnostics']
        if item.get('stage') == 'fixture_contact_measurement' and item.get('anchor_id') == 'e114']
    search, = [item for item in row['candidate_screen_diagnostics']
        if item.get('stage') == 'fixture_route_search' and item.get('anchor_id') == 'e114']
    seed = search['candidates'][0]
    plan = {'xyz_m': seed['route'][-1]['xyz_m'], 'quat_xyzw': seed['route'][-1]['quat_xyzw'],
        'approach_xyz_m': seed['route'][-2]['xyz_m'], 'width_m': seed['width_m'],
        'handle_measurement': handle}
    results = []
    for name, method in [('baseline', original), ('add_direct_routes', variant)]:
        adapter = copy.deepcopy(frozen['adapter'])
        adapter.candidate_diagnostics = []
        # Annotation captures freeze candidate plans, not re-entry history.
        # These rows have no preceding failed descent, the only writer of
        # this blacklist. Reconstruct its demonstrably empty value.
        assert not any(receipt['skill'] == 'descend' and receipt['outcome'] != 'success'
            for prior in rows[:index] for receipt in prior.get('receipts', []))
        adapter.failed_contact_poses = {}
        started = time.perf_counter()
        candidate = method(adapter, adapter.scene.entities['e114'], copy.deepcopy(plan))
        diagnostic = adapter.candidate_diagnostics[-1]
        result = {'method': name, 'cpu_s': time.perf_counter()-started,
            'plan': candidate, 'diagnostic': diagnostic}
        results.append(result)
        print(json.dumps({'row': index, 'method': name, 'plan_available': candidate is not None,
            'selected': diagnostic['selected'], 'cpu_s': result['cpu_s'],
            'reasons': dict(Counter((item.get('screen') or {}).get('reason')
                for item in diagnostic['candidates']))}), flush=True)
    records.append({'row': index, 'context': ref, 'seed_plan': plan, 'results': results})
report = {'source': str(source), 'job': '9513_120', 'records': records,
    'original_method_sha256': hashlib.sha256(inspect.getsource(original).encode()).hexdigest(),
    'variant_method_sha256': hashlib.sha256(code.encode()).hexdigest(), 'variant_method': code,
    'physics_steps': 0, 'gpu_used': False, 'rpc_calls': 0, 'private_truth_used': False,
    'scope': 'Frozen public-geometry whole-route screen only, not a physical success result',
    'training': False, 'confirmation': False,
    'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
output = root/'coordination/bounded_skills_20261016/reports/microwave9513_reentry_routes_CPU_20261018.json'
with output.open('x') as stream:
    json.dump(report, stream, indent=2)
    stream.write('\n')
