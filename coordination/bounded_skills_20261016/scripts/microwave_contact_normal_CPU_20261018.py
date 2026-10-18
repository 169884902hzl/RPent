# Copyright 2026 The RPent Authors.
# SPDX-License-Identifier: Apache-2.0
"""Refit saved public panel captures without simulation or private coordinates."""
import argparse
import hashlib
import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace

os.environ.update(CUDA_VISIBLE_DEVICES='', OPENBLAS_NUM_THREADS='1')
parser = argparse.ArgumentParser()
parser.add_argument('--source', type=Path, required=True)
parser.add_argument('--output', type=Path, required=True)
args = parser.parse_args()
sys.path.insert(0, str(args.source))

import numpy as np  # noqa: E402

from robots.libero.bounded_skills import MeasuredSkillAdapter  # noqa: E402
from robots.libero.v5_state import Entity  # noqa: E402

root = Path('/public/home/sunyihan/rpent_libero_eval')
directory = root/'results/bounded_skills/feasibility_20261017/job8993_120'
arm = next(directory.glob('*oracle_k4'))
raw = (arm/'choices.jsonl').read_bytes()
rows = [json.loads(line) for line in raw.splitlines()]
old = next(d['plan']['surface_measurement']['normal_xyz'] for row in rows
           for d in row.get('candidate_screen_diagnostics', [])
           if d.get('stage') == 'fixture_contact_plan' and d.get('anchor_id') == 'e114')
records = []
for artifact in sorted((arm/'bounded_contact_e114_reference.npz').glob('*.npz')):
    step = int(artifact.stem)
    with np.load(artifact) as stored:
        points = stored[stored.files[0]]
    adapter = MeasuredSkillAdapter.__new__(MeasuredSkillAdapter)
    entity = Entity('e114', 'microwave door', tuple(np.median(points, axis=0)),
                    tuple(points.min(0)), tuple(points.max(0)), True, step)
    adapter.scene = SimpleNamespace(measurement_clouds={entity.id: points})
    adapter.ex = SimpleNamespace(toolkit=SimpleNamespace(_state=SimpleNamespace(latest_step=step)))
    reference = {'xyz_world': [[0., 0., 0.]], 'source_step': 0, 'normal_xyz': list(old)}
    adapter._refresh_contact_normal(entity, {'surface_measurement': reference})
    assert reference['xyz_world'] == [[0., 0., 0.]] and reference['source_step'] == 0
    normal = np.asarray(reference['normal_xyz'])
    angle = float(np.degrees(np.arccos(np.clip(np.dot(old, normal), -1., 1.))))
    records.append({'artifact': str(artifact), 'sha256': hashlib.sha256(artifact.read_bytes()).hexdigest(),
        'points': len(points), 'capture_step': step, 'old_normal': old, 'new_normal': normal.tolist(),
        'normal_source_step': reference.get('normal_source_step'), 'changed_angle_deg': angle})
report = {'source': str(args.source), 'module_sha256': hashlib.sha256(
    (args.source/'robots/libero/bounded_skills.py').read_bytes()).hexdigest(),
    'choices_sha256': hashlib.sha256(raw).hexdigest(), 'rows': records,
    'private_truth_used': False, 'gpu_used': False, 'controls': 0, 'training': False,
    'limitation': 'Saved associated contact surfaces test the normal refit; live segmentation and task success remain separate.'}
args.output.write_text(json.dumps(report, indent=2)+'\n')
print(json.dumps(report))
