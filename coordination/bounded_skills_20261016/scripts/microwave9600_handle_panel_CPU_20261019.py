"""Test current independent handle support for competing observed door planes."""
# ruff: noqa: E402 -- immutable source and CPU environment before imports
import hashlib
import inspect
import json
import os
import sys
from pathlib import Path

os.environ.update(CUDA_VISIBLE_DEVICES='', OPENBLAS_NUM_THREADS='1')
root = Path('/public/home/sunyihan/rpent_libero_eval')
base = root / 'coordination/bounded_skills_20261016'
prep_path = base / 'reports/chunk_v3_panel_consensus_20261019_preparation.json'
prep = json.loads(prep_path.read_bytes())
sys.path.insert(0, prep['snapshot'])
import numpy as np

from robots.libero.v5_fixture_parts import measured_handle_backing_face
from robots.libero.v5_verification import moving_panel_points, vertical_face

directory, = (root / 'results/bounded_skills/feasibility_20261017/job9600_140').glob('*oracle_k4')
choices_path = directory / 'choices.jsonl'
rows = [json.loads(line) for line in choices_path.read_bytes().splitlines()]
inputs = {str(path): hashlib.sha256(path.read_bytes()).hexdigest()
          for path in (prep_path, choices_path)}


def load(ref):
    path = Path(ref['path'])
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    assert actual == ref['sha256'], path
    inputs[str(path)] = actual
    with np.load(path, allow_pickle=False) as saved:
        assert len(saved.files) == 1
        return saved[saved.files[0]]


records = []
for index in (4, 10, 14):
    row = rows[index]
    handles = {}
    for diagnostic in row['candidate_screen_diagnostics']:
        if diagnostic.get('stage') != 'fixture_contact_measurement':
            continue
        measurement = diagnostic['measurement']
        for camera, view in measurement.get('views', {}).items():
            ref = view.get('cloud')
            if ref is not None:
                handles[ref['sha256']] = {'anchor': diagnostic['anchor_id'],
                    'camera': camera, 'source_step': measurement['source_step'], 'ref': ref}
    seen = set()
    for parent, fixture in row.get('fixture_measurement_evidence', {}).items():
        for instance in fixture.get('door_measurement', {}).get('instances', []):
            ref = instance.get('candidate_cloud')
            if ref is None or ref['sha256'] in seen:
                continue
            seen.add(ref['sha256'])
            panel, consensus = moving_panel_points(load(ref), None)
            face = vertical_face(panel)
            record = {'row': index, 'parent': parent, 'camera': instance['camera'],
                      'source_step': ref['source_step'], 'ref': ref, 'face': face,
                      'consensus': consensus, 'handle_support': []}
            if face is not None:
                normal = np.asarray(face['normal_xy'])
                tangent = np.array([-normal[1], normal[0]])
                side = np.quantile(panel[:, :2] @ tangent, [.1, .9])
                height = np.quantile(panel[:, 2], [.1, .9])
                for handle in handles.values():
                    if handle['source_step'] != ref['source_step']:
                        continue
                    cloud = load(handle['ref'])
                    centre = np.median(cloud, axis=0)
                    gap = float(abs((centre[:2] - face['centre'][:2]) @ normal))
                    projection = float(centre[:2] @ tangent)
                    # Exactly the existing backing-plane support gates, not
                    # an endpoint threshold or a task-specific size prior.
                    conditions = {
                        'plane_width': bool(side[1] - side[0] >= .08),
                        'plane_height': bool(height[1] - height[0] >= .08),
                        'normal_offset': bool(.005 <= gap <= .06),
                        'within_width': bool(side[0] - .03 <= projection <= side[1] + .03),
                        'within_height': bool(height[0] - .03 <= centre[2] <= height[1] + .03)}
                    record['handle_support'].append({**handle, 'normal_gap_m': gap,
                        'tangent_projection_m': projection, 'tangent_extent_m': side.tolist(),
                        'height_extent_m': height.tolist(), 'conditions': conditions,
                        'supported': all(conditions.values())})
            records.append(record)

output = base / 'reports/microwave9600_handle_panel_CPU_20261019.json'
report = {'source_commit': prep['source_commit'], 'snapshot': prep['snapshot'],
    'records': records, 'inputs': inputs,
    'existing_gate_function_sha256': hashlib.sha256(inspect.getsource(measured_handle_backing_face).encode()).hexdigest(),
    'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    'scope': 'saved public current handle and door-cloud association hypothesis; no production change',
    'physics_steps': 0, 'rpc_calls': 0, 'gpu_used': False, 'private_labels_used': False,
    'training': False, 'confirmation': False}
with output.open('x') as stream:
    json.dump(report, stream, indent=2)
    stream.write('\n')
print(json.dumps({'output': str(output), 'records': [{
    'row': r['row'], 'camera': r['camera'], 'parent': r['parent'],
    'plane': r['face'] is not None,
    'supports': [{'anchor': h['anchor'], 'gap_m': h['normal_gap_m'],
                  'supported': h['supported']} for h in r['handle_support']]}
    for r in records]}))
