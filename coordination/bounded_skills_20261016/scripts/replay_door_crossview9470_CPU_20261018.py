# Copyright 2026 Zhilun Hu.
# SPDX-License-Identifier: Apache-2.0
"""Test measured same-instant door identity in the static overview camera."""
# ruff: noqa: E402 -- immutable source and CPU selected before robot imports
import hashlib
import json
import os
import sys
import time
from pathlib import Path

os.environ.update(CUDA_VISIBLE_DEVICES='', OPENBLAS_NUM_THREADS='1')
root = Path('/public/home/sunyihan/rpent_libero_eval')
base = root / 'coordination/bounded_skills_20261016'
source = root / 'source_bounded_chunk_v3_lost_contact_20261018_4167f4e'
sys.path.insert(0, str(source))

import numpy as np
import robosuite
from PIL import Image

from robots.libero.bounded_motion import measured_robot
from robots.libero.bounded_offline_labels import load_annotation_state
from robots.libero.bounded_self_filter import public_robot_mask
from robots.libero.v5_microwave_capture import points_mask
from robots.libero.v5_microwave_identity import (
    match_current_door_across_views,
    track_measured_door,
)

choices = next((root / 'results/bounded_skills/feasibility_20261017/job9470_140').glob(
    '*oracle*/choices.jsonl'))
rows = [json.loads(line) for line in choices.read_bytes().splitlines()]
directory = choices.parent
xml = Path(robosuite.__file__).parent / 'models/assets/grippers/panda_gripper.xml'


def load(path):
    with np.load(path) as arrays:
        return arrays[arrays.files[0]]


def capture(camera, step):
    world = load(directory / f'{camera}_world_high.npz' / f'{step:02d}.npz')
    rgb = np.asarray(Image.open(directory / f'{camera}_high.png' / f'{step:02d}.png').convert('RGB'))
    return rgb, world


def overlay(rgb, mask, name):
    image = rgb.copy()
    image[mask] = (.45 * image[mask] + .55 * np.array([0, 255, 255])).astype(np.uint8)
    path = base / 'reports/microwave9470_140_crossview_images' / name
    path.parent.mkdir(exist_ok=True)
    Image.fromarray(image).save(path)
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


records = []
for previous_row, previous_step in ((6, 11), (9, 14)):
    evidence = rows[previous_row]['fixture_measurement_evidence']['e54']['door_measurement']
    measurement = next(item['candidate_cloud'] for item in evidence['instances']
        if item.get('camera') == 'wrist' and item.get('candidate_cloud') and not item.get('reason'))
    path = Path(measurement['path'])
    assert hashlib.sha256(path.read_bytes()).hexdigest() == measurement['sha256']
    wrist_rgb, wrist_world = capture('wrist', previous_step)
    mask = points_mask(wrist_world, load(path))
    old_rgb, old_world = capture('agentview', previous_step)
    cross_mask, cross_face, cross_detail = match_current_door_across_views(
        wrist_world, mask, old_world, None)
    cross = {'kind': 'same_instant_cross_view', 'source_step': previous_step,
        'measured_pixels': int(cross_mask.sum()), 'face': cross_face, 'diagnostic': cross_detail,
        'source_measurement': measurement, 'fixed_reference': None,
        'seed_overlay': overlay(wrist_rgb, mask, f'wrist{previous_step}.png'),
        'overview_overlay': overlay(old_rgb, cross_mask, f'overview{previous_step}.png')}
    records.append(cross)
    print(json.dumps(cross), flush=True)
    if cross_face is None:
        continue
    for index, step in ((10, 16), (11, 17), (13, 19)):
        ref = rows[index]['private_prefix_annotation_state']
        adapter = load_annotation_state(ref['path'], ref['sha256'])['adapter']
        assert adapter.ex.toolkit._state.latest_step == step
        rgb, world = capture('agentview', step)
        robot_mask = public_robot_mask(world, measured_robot(adapter.p), xml)
        started = time.perf_counter()
        tracked, face, detail = track_measured_door(old_rgb, rgb, old_world, world,
            cross_mask, None, robot_mask=robot_mask)
        record = {'kind': 'overview_temporal_tracking', 'previous_step': previous_step,
            'current_step': step, 'measured_pixels': int(tracked.sum()), 'face': face,
            'diagnostic': detail, 'elapsed_s': time.perf_counter() - started,
            'captured_context': ref, 'fixed_reference': None,
            'overlay': overlay(rgb, tracked, f'overview{previous_step}_to{step}.png')}
        records.append(record)
        print(json.dumps(record), flush=True)

output = base / 'reports/microwave9470_140_crossview_CPU_20261018.json'
output.write_text(json.dumps({'source': str(source), 'records': records,
    'choices_sha256': hashlib.sha256(choices.read_bytes()).hexdigest(),
    'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    'scope': 'same recorded public RGB-D; no segmentation, simulator or private task labels',
    'controls': 0, 'gpu_used': False, 'training': False}, indent=2) + '\n')
print(json.dumps({'output': str(output)}), flush=True)
