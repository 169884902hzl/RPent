# Copyright 2026 Zhilun Hu.
# SPDX-License-Identifier: Apache-2.0
"""Explain the recorded reapproach duration without controls or new sensing."""
# ruff: noqa: E402 -- import the exact saved source before unpickling its state
import hashlib
import json
import os
import sys
from pathlib import Path

os.environ.update(CUDA_VISIBLE_DEVICES='', OPENBLAS_NUM_THREADS='1')
root = Path('/public/home/sunyihan/rpent_libero_eval')
source = root/'source_bounded_chunk_v3_payload_interval_20261018_87ef92e'
sys.path.insert(0, str(source))
import numpy as np
from scipy.spatial.transform import Rotation

from robots.libero.bounded_offline_labels import load_annotation_state

base = root/'results/bounded_skills/feasibility_20261017/job9211_10'
records = []
for suffix, index in [('oracle_k4', 3), ('oracle_k4_legacy', 5)]:
    directory = base/('bowl_transfer_libero_spatial_t0_s10_'+suffix)
    path = directory/'choices.jsonl'
    row = json.loads(path.read_bytes().splitlines()[index])
    ref = row['private_prefix_annotation_state']
    state = load_annotation_state(ref['path'], ref['sha256'])
    adapter = state['adapter']
    candidate = next(c for c in row['request']['candidates'] if c['skill'] == 'move_to'
                     and c['id'] in row['decision']['candidate_ids'])
    route = adapter._route(candidate['skill'], candidate['parameters'])
    execution = next(d['execution'] for d in row['execution_details']
                     if d.get('candidate_id') == candidate['id'])
    start = execution['reference_start_pose']
    poses = [{'xyz_m': start['eef_xyz_m'], 'quat_xyzw': start['eef_quat_xyzw']}, *route]
    legs = []
    previous_time = 0.
    for i, (a, b, end_time) in enumerate(zip(poses[:-1], poses[1:], execution['waypoint_times_s'])):
        translation = float(np.linalg.norm(np.asarray(b['xyz_m'])-a['xyz_m']))
        angle = float((Rotation.from_quat(b['quat_xyzw'])*Rotation.from_quat(a['quat_xyzw']).inv()).magnitude())
        legs.append({'index': i, 'translation_m': translation, 'rotation_rad': angle,
            'recorded_reference_duration_s': end_time-previous_time,
            'velocity_lower_bound_s': max(translation/adapter.config.translation_speed_m_s,
                angle/adapter.config.rotation_speed_rad_s)})
        previous_time = end_time
    records.append({'arm': suffix, 'row': index, 'candidate': candidate,
        'route': route, 'recorded_steps': execution['steps_used'],
        'recorded_duration_s': execution['reference_duration_s'], 'legs': legs,
        'annotation_reference': ref, 'ledger_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
        'limits': execution['config'], 'metrics': execution['metrics']})
report = {'records': records, 'controls': 0, 'gpu_used': False, 'training': False,
    'runtime_private_fields_used': False,
    'scope': 'Read only public adapter route and recorded control references; no retiming change',
    'source': str(source), 'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
out = root/'coordination/bounded_skills_20261016/reports/9211_10_reapproach_CPU_20261018.json'
out.write_text(json.dumps(report, indent=2)+'\n')
print(json.dumps({'output': str(out), 'records': [
    {k: r[k] for k in ('arm', 'row', 'recorded_steps', 'legs')} for r in records]}))
