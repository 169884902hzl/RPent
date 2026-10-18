# Copyright 2026 Zhilun Hu.
# SPDX-License-Identifier: Apache-2.0
"""Check public point-recall coverage when nonempty door masks are rejected."""
# ruff: noqa: E402 -- frozen source and CPU selected before imports
import hashlib
import json
import os
import sys
from pathlib import Path

os.environ.update(CUDA_VISIBLE_DEVICES='', OPENBLAS_NUM_THREADS='1')
root = Path('/public/home/sunyihan/rpent_libero_eval')
base = root/'coordination/bounded_skills_20261016'
source = root/'source_bounded_chunk_v3_anchor_recovery_20261018_eee8434'
sys.path.insert(0, str(source))
import numpy as np
import robosuite
from PIL import Image, ImageDraw

from robots.libero.bounded_motion import measured_robot
from robots.libero.bounded_offline_labels import load_annotation_state
from robots.libero.bounded_self_filter import public_robot_mask
from robots.libero.v5_fixture_parts import adjacent_panel_prompt

choices = next((root/'results/bounded_skills/feasibility_20261017/job9470_140').glob('*oracle*/choices.jsonl'))
rows = [json.loads(line) for line in choices.open()]
xml = Path(robosuite.__file__).parent/'models/assets/grippers/panda_gripper.xml'
images = base/'reports/door9470_recall_images'
images.mkdir(exist_ok=True)
records = []
for index in (10, 13):
    ref = rows[index]['private_prefix_annotation_state']
    adapter = load_annotation_state(ref['path'], ref['sha256'])['adapter']
    step = adapter.ex.toolkit._state.latest_step
    for camera in ('agentview', 'wrist'):
        path = choices.parent/f'{camera}_world_high.npz'/f'{step:02d}.npz'
        with np.load(path) as arrays:
            original = arrays[arrays.files[0]]
        world = original.copy()
        world[public_robot_mask(world, measured_robot(adapter.p), xml)] = np.nan
        for parent in adapter.scene.entities.values():
            if parent.name != 'microwave':
                continue
            point, evidence = adjacent_panel_prompt(world, parent)
            image = Image.open(choices.parent/f'{camera}_high.png'/f'{step:02d}.png').convert('RGB')
            if point is not None:
                y, x = point
                draw = ImageDraw.Draw(image)
                draw.ellipse((x-8, y-8, x+8, y+8), outline='magenta', width=3)
            overlay = images/f'{parent.id}_{camera}_{step}.png'
            image.save(overlay)
            records.append({'row': index, 'step': step, 'camera': camera,
                'parent': {'id': parent.id, 'xyz_m': parent.xyz, 'lower_m': parent.lower, 'upper_m': parent.upper},
                'point_yx': point, 'evidence': evidence,
                'overlay': {'path': str(overlay), 'sha256': hashlib.sha256(overlay.read_bytes()).hexdigest()},
                'recorded_door_evidence': rows[index].get('fixture_measurement_evidence', {}).get(parent.id, {}).get('door_measurement')})
output = base/'reports/microwave9470_rejected_mask_recall_CPU_20261018.json'
output.write_text(json.dumps({'records': records, 'source': str(source),
    'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    'scope': 'public RGB-D adjacent-plane diagnostic; no new segmentation, control, simulation or private labels',
    'gpu_used': False, 'physics_steps': 0, 'training': False}, indent=2)+'\n')
print(json.dumps({'output': str(output), 'points': [
    {'step': r['step'], 'parent': r['parent']['id'], 'camera': r['camera'],
     'point': r['point_yx'], 'reason': r['evidence'].get('reason')} for r in records]}))
