# Copyright 2026 Zhilun Hu.
# SPDX-License-Identifier: Apache-2.0
"""Compare conditional IK reseeding with and without moving its fixed base."""
# ruff: noqa: E402 -- pin the captured source and CPU before robot imports
import copy
import hashlib
import json
import os
import sys
import time
from pathlib import Path

os.environ.update(CUDA_VISIBLE_DEVICES='', OPENBLAS_NUM_THREADS='1')
root = Path('/public/home/sunyihan/rpent_libero_eval')
base = root/'coordination/bounded_skills_20261016'
source = root/'source_bounded_chunk_v3_support_plane_20261018_ec89f74'
sys.path.insert(0, str(source))
import numpy as np
from scipy.spatial.transform import Rotation
from robots.libero.bounded_chunk import PublicPrefixPrediction
from robots.libero.bounded_offline_labels import load_annotation_state
from robots.libero.v5_grasp_kinematics import forward
from rpent.skill_package.contract import legal_after

choices = next((root/'results/bounded_skills/feasibility_20261017/job9248_6').glob('*oracle*/choices.jsonl'))
row = json.loads(choices.read_bytes().splitlines()[9])
ref = row['private_prefix_annotation_state']
state = load_annotation_state(ref['path'], ref['sha256'])
request = row['request']
legal = legal_after(request, [])
records = []
for candidate in request['candidates']:
    if (candidate['skill'] != 'nudge' or candidate['id'] not in legal
            or abs(candidate['parameters']['distance_m']) != .02):
        continue
    for arm in ('recalibrated_base', 'fixed_capture_base'):
        started = time.perf_counter()
        prediction = PublicPrefixPrediction(copy.deepcopy(state['adapter']), request)
        assert not hasattr(prediction.adapter.p.env, 'step')
        rotation = prediction.ik.world_rotation.copy()
        offset = prediction.ik.world_offset.copy()
        actual = prediction.candidate(candidate)
        effect = actual['consequences']
        record = dict(arm=arm, candidate_id=candidate['id'], parameters=candidate['parameters'],
                      initial_consequences=effect, plan_available=None)
        if effect['collision'] is not True and effect['ik_reachable'] is True:
            prediction.advance(actual)
            rebased_rotation = prediction.ik.world_rotation.copy()
            rebased_offset = prediction.ik.world_offset.copy()
            record.update(
                implicit_offset_change_m=float(np.linalg.norm(rebased_offset-offset)),
                implicit_rotation_change_rad=float(Rotation.from_matrix(rebased_rotation@rotation.T).magnitude()))
            pose = forward(prediction.ik.nodes, prediction.sensor['joint_positions_rad'])
            site = pose[:3, 3]+pose[:3, :3]@prediction.ik.site_offset
            record['fixed_base_endpoint_error_m'] = float(np.linalg.norm(
                offset+rotation@site-prediction.sensor['eef_xyz_m']))
            if arm == 'fixed_capture_base':
                # Experimental comparison only: this does not edit the runtime.
                prediction.ik.world_rotation = rotation.copy()
                prediction.ik.world_offset = offset.copy()
            adapter = prediction.adapter
            adapter._instance_cache = {'e114': prediction._original_target('e114').copy()}
            plan = adapter._surface_contact_plan(
                adapter.scene.entities['e114'], adapter.scene.measurement_clouds['e114'])
            record.update(plan_available=plan is not None, plan=plan,
                          diagnostics=adapter.candidate_diagnostics[-1])
        record['elapsed_s'] = time.perf_counter()-started
        records.append(record)
        print(json.dumps({k: v for k, v in record.items() if k not in {
            'initial_consequences', 'plan', 'diagnostics'}}), flush=True)
output = base/'reports/microwave9248_6_predicted_base_CPU_20261018.json'
output.write_text(json.dumps(dict(source=str(source), context=ref, records=records,
    choices_sha256=hashlib.sha256(choices.read_bytes()).hexdigest(),
    script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    scope='same public measured state, conditional CPU prediction; no physical success claim',
    controls=0, gpu_used=False, training=False), indent=2)+'\n')
print(json.dumps({'output': str(output)}), flush=True)
