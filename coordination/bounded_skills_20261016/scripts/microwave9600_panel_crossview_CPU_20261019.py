"""Check cross-view depth support for the competing current door surfaces."""
# ruff: noqa: E402 -- pinned public images and CPU-only hypothesis
import hashlib
import inspect
import json
import os
import sys
from pathlib import Path

os.environ.update(CUDA_VISIBLE_DEVICES='', OPENBLAS_NUM_THREADS='1')
root = Path('/public/home/sunyihan/rpent_libero_eval')
base = root / 'coordination/bounded_skills_20261016'
prep = json.loads((base / 'reports/chunk_v3_panel_joint_room_20261018_preparation.json').read_text())
sys.path.insert(0, prep['snapshot'])
import numpy as np

from robots.libero.v5_microwave_capture import points_mask
from robots.libero.v5_microwave_identity import match_current_door_across_views
from robots.libero.v5_verification import moving_panel_points

original = inspect.getsource(moving_panel_points)
first = original.index('    if fixed_anchor is None:')
last = original.index('    if len(points) < 60:', first)
exclusion = original[first:last].split('    lo, hi =', 1)[1]
changed = original[:first] + '    if fixed_anchor is not None:\n' + ''.join(
    '    ' + line if line.strip() else line
    for line in ('    lo, hi =' + exclusion).splitlines(keepends=True)) + original[last:]
namespace = dict(moving_panel_points.__globals__)
exec(compile(changed, '<no-reference-consensus-hypothesis>', 'exec'), namespace)
proposed = namespace['moving_panel_points']
audit_path = base / 'reports/microwave9600_identity_audit_CPU_20261019.json'
audit = json.loads(audit_path.read_bytes())
directory, = (root / 'results/bounded_skills/feasibility_20261017/job9600_140').glob('*oracle_k4')

def load(path):
    with np.load(path, allow_pickle=False) as saved:
        assert len(saved.files) == 1
        return saved[saved.files[0]]

records, seen, inputs = [], set(), [audit_path]
for index in (10, 14):
    for parent, door in audit['records'][index]['door_measurements'].items():
        for instance in door['instances']:
            ref = instance.get('candidate_cloud')
            if ref is None or ref['sha256'] in seen:
                continue
            seen.add(ref['sha256'])
            cloud_path = Path(ref['path'])
            assert hashlib.sha256(cloud_path.read_bytes()).hexdigest() == ref['sha256']
            panel, fitting = proposed(load(cloud_path), None)
            camera, step = instance['camera'], ref['source_step']
            target = 'wrist' if camera == 'agentview' else 'agentview'
            source_path = directory / (camera + '_world_high.npz') / f'{step:02d}.npz'
            target_path = directory / (target + '_world_high.npz') / f'{step:02d}.npz'
            source, other = load(source_path), load(target_path)
            mask = points_mask(source, panel)
            matched, face, detail = match_current_door_across_views(source, mask, other, None)
            records.append({'row': index, 'parent': parent, 'camera': camera, 'target_camera': target,
                            'source_step': step, 'input': ref, 'fitting': fitting,
                            'source_pixels': int(mask.sum()), 'target_pixels': int(matched.sum()),
                            'cross_view_plane': face, 'detail': detail, 'robot_mask': None})
            inputs.extend((cloud_path, source_path, target_path))
output = base / 'reports/microwave9600_panel_crossview_CPU_20261019.json'
report = {'source': prep['source_commit'], 'records': records,
          'inputs': [{'path': str(p), 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()}
                     for p in dict.fromkeys(inputs)],
          'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
          'hypothesis_function_sha256': hashlib.sha256(changed.encode()).hexdigest(),
          'scope': 'same-instant public depth support after isolated plane-fit hypothesis; no production change',
          'physics_steps': 0, 'rpc_calls': 0, 'gpu_used': False, 'private_labels_used': False,
          'training': False, 'confirmation': False}
with output.open('x') as stream:
    json.dump(report, stream, indent=2)
    stream.write('\n')
print(json.dumps({'output': str(output), 'records': [{'row': r['row'], 'camera': r['camera'],
    'pixels': r['target_pixels'], 'plane': r['cross_view_plane'] is not None,
    'reason': r['detail']['reason']} for r in records]}))
