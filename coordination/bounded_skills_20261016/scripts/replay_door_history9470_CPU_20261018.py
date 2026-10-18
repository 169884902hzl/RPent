# Copyright 2026 Zhilun Hu.
# SPDX-License-Identifier: Apache-2.0
"""Check retained independent door identity after temporary occlusion."""
# ruff: noqa: E402 -- choose the immutable source and CPU before robot imports
import hashlib
import json
import os
import sys
import time
from pathlib import Path

os.environ.update(CUDA_VISIBLE_DEVICES='', OPENBLAS_NUM_THREADS='1')
root = Path('/public/home/sunyihan/rpent_libero_eval')
base = root/'coordination/bounded_skills_20261016'
source = root/'source_bounded_chunk_v3_lost_contact_20261018_4167f4e'
sys.path.insert(0, str(source))
import numpy as np
import robosuite
from PIL import Image

from robots.libero.bounded_motion import measured_robot
from robots.libero.bounded_offline_labels import load_annotation_state
from robots.libero.bounded_self_filter import public_robot_mask
from robots.libero.v5_microwave_capture import points_mask
from robots.libero.v5_microwave_identity import track_measured_door

choices = next((root/'results/bounded_skills/feasibility_20261017/job9470_140').glob('*oracle*/choices.jsonl'))
rows = [json.loads(line) for line in choices.read_bytes().splitlines()]
directory = choices.parent
xml = Path(robosuite.__file__).parent/'models/assets/grippers/panda_gripper.xml'


def load(path):
    with np.load(path) as arrays:
        return arrays[arrays.files[0]]


records = []
for previous_row, previous_step in ((6, 11), (9, 14)):
    evidence = rows[previous_row]['fixture_measurement_evidence']['e54']['door_measurement']
    measurement = next(item['candidate_cloud'] for item in evidence['instances']
        if item.get('camera') == 'wrist' and item.get('candidate_cloud')
        and not item.get('reason'))
    path = Path(measurement['path'])
    assert hashlib.sha256(path.read_bytes()).hexdigest() == measurement['sha256']
    world_path = directory/'wrist_world_high.npz'/f'{previous_step:02d}.npz'
    rgb_path = directory/'wrist_high.png'/f'{previous_step:02d}.png'
    previous_world, rgb = load(world_path), np.asarray(Image.open(rgb_path).convert('RGB'))
    mask = points_mask(previous_world, load(path))
    for index, step in ((10, 16), (11, 17), (13, 19)):
        ref = rows[index]['private_prefix_annotation_state']
        adapter = load_annotation_state(ref['path'], ref['sha256'])['adapter']
        assert adapter.ex.toolkit._state.latest_step == step
        world = load(directory/'wrist_world_high.npz'/f'{step:02d}.npz')
        current_rgb = np.asarray(Image.open(directory/'wrist_high.png'/f'{step:02d}.png').convert('RGB'))
        robot_mask = public_robot_mask(world, measured_robot(adapter.p), xml)
        started = time.perf_counter()
        tracked, face, detail = track_measured_door(rgb, current_rgb, previous_world, world,
            mask, None, robot_mask=robot_mask)
        record = {'previous_step': previous_step, 'current_step': step,
            'captured_context': ref, 'previous_door_cloud': measurement,
            'fixed_reference': None, 'elapsed_s': time.perf_counter()-started,
            'measured_pixels': int(tracked.sum()), 'face': face, 'diagnostic': detail}
        records.append(record)
        print(json.dumps({key: record[key] for key in (
            'previous_step', 'current_step', 'elapsed_s', 'measured_pixels', 'face')}), flush=True)
output = base/'reports/microwave9470_140_history_retain_CPU_20261018.json'
output.write_text(json.dumps({'source': str(source), 'records': records,
    'choices_sha256': hashlib.sha256(choices.read_bytes()).hexdigest(),
    'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    'scope': 'same public RGB-D and joint-sensor evidence; no new segmentation or simulation',
    'private_labels_used': False, 'controls': 0, 'gpu_used': False, 'training': False}, indent=2)+'\n')
print(json.dumps({'output': str(output)}), flush=True)
