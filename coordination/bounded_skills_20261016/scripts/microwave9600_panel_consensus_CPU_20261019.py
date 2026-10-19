"""Test existing panel consensus without requiring an already measured frame."""
# ruff: noqa: E402 -- pinned CPU-only geometry hypothesis
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

from robots.libero.v5_verification import moving_panel_points, vertical_face

original = inspect.getsource(moving_panel_points)
first = original.index('    if fixed_anchor is None:')
last = original.index('    if len(points) < 60:', first)
exclusion = original[first:last]
exclusion = exclusion.split('    lo, hi =', 1)[1]
# Retain the exact static-reference exclusion when a real reference exists.
# With none, test only the unchanged 4 mm / 55% consensus and residual gates.
changed = original[:first] + '    if fixed_anchor is not None:\n' + ''.join(
    '    ' + line if line.strip() else line
    for line in ('    lo, hi =' + exclusion).splitlines(keepends=True)) + original[last:]
namespace = dict(moving_panel_points.__globals__)
exec(compile(changed, '<no-reference-consensus-hypothesis>', 'exec'), namespace)
proposed = namespace['moving_panel_points']
audit_path = base / 'reports/microwave9600_identity_audit_CPU_20261019.json'
audit = json.loads(audit_path.read_bytes())
records, seen = [], set()
for index in (10, 14):
    for parent, door in audit['records'][index]['door_measurements'].items():
        for instance in door['instances']:
            ref = instance.get('candidate_cloud')
            if ref is None or ref['sha256'] in seen:
                continue
            seen.add(ref['sha256'])
            path = Path(ref['path'])
            assert hashlib.sha256(path.read_bytes()).hexdigest() == ref['sha256']
            with np.load(path, allow_pickle=False) as saved:
                points = saved[saved.files[0]]
            old, before = moving_panel_points(points, None)
            new, after = proposed(points, None)
            records.append({'row': index, 'parent': parent, 'camera': instance['camera'],
                'input': ref, 'old': {'detail': before, 'points': len(old), 'plane': vertical_face(old)},
                'proposed': {'detail': after, 'points': len(new), 'plane': vertical_face(new)}})
report = {'source': prep['source_commit'], 'records': records,
          'original_function_sha256': hashlib.sha256(original.encode()).hexdigest(),
          'hypothesis_function_sha256': hashlib.sha256(changed.encode()).hexdigest(),
          'audit': {'path': str(audit_path), 'sha256': hashlib.sha256(audit_path.read_bytes()).hexdigest()},
          'scope': 'isolated CPU geometry hypothesis; no production change, independent door identity still required',
          'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
          'physics_steps': 0, 'rpc_calls': 0, 'gpu_used': False, 'private_labels_used': False,
          'training': False, 'confirmation': False}
output = base / 'reports/microwave9600_panel_consensus_CPU_20261019.json'
with output.open('x') as stream:
    json.dump(report, stream, indent=2)
    stream.write('\n')
print(json.dumps({'output': str(output), 'results': [{'row': r['row'], 'camera': r['camera'],
    'before_plane': r['old']['plane'] is not None,
    'after_plane': r['proposed']['plane'] is not None,
    'retained_fraction': r['proposed']['detail'].get('panel_fraction')} for r in records]}))
