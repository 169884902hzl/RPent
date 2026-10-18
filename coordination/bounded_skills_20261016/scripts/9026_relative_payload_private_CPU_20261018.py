# Copyright 2026 Zhilun Hu.
# SPDX-License-Identifier: Apache-2.0
"""Diagnose grip compliance in saved states; no labels enter public requests."""
# ruff: noqa: E402 -- CPU and immutable source selected before simulator imports
import hashlib
import json
import os
import pickle
import sys
from pathlib import Path

os.environ.update(CUDA_VISIBLE_DEVICES='', LIBERO_TYPE='standard', OPENBLAS_NUM_THREADS='1', MUJOCO_GL='egl')
root = Path('/public/home/sunyihan/rpent_libero_eval')
base = root/'coordination/bounded_skills_20261016'
sys.path.insert(0, str(root/'source_bounded_chunk_v3_payload_interval_20261018_87ef92e'))
import numpy as np
from libero.libero.envs.env_wrapper import ControlEnv
from scipy.spatial.transform import Rotation

from robots.libero.v5_branch_state import restore_actuators
from robots.libero.v5_reset_seed import attach_reset_seed

records = []
for job, before_index, after_index in [('16', 1, 2), ('19', 4, 5)]:
    directory, = (root/'results/bounded_skills/feasibility_20261017'/('job9026_'+job)).glob('*oracle*')
    rows = [json.loads(line) for line in (directory/'choices.jsonl').read_bytes().splitlines()]
    episode = json.loads((directory.parent/'episodes.jsonl').read_bytes().splitlines()[0])
    env = ControlEnv(bddl_file_name=episode['case']['bddl']['path'], use_camera_obs=False,
        has_renderer=False, has_offscreen_renderer=False, camera_names=[], ignore_done=True, horizon=10015)
    attach_reset_seed(env)
    env.seed(0)
    env.reset()
    samples = []
    try:
        for index in (before_index, after_index):
            ref = rows[index]['private_pre_execution_snapshot']
            raw = Path(ref['path']).read_bytes()
            assert hashlib.sha256(raw).hexdigest() == ref['sha256']
            saved = pickle.loads(raw)
            env.set_init_state(saved['sim_state'])
            restore_actuators(env, saved['actuator_state'])
            sim = env.env.sim
            assert np.max(np.abs(sim.get_state().flatten()-saved['sim_state'])) < 1e-8
            body = env.env.obj_body_id['akita_black_bowl_1']
            robot = rows[index]['request']['robot']
            rotation = Rotation.from_quat(robot['eef_quat_xyzw']).as_matrix()
            position = np.asarray(sim.data.body_xpos[body]).copy()
            relative_position = rotation.T@(position-np.asarray(robot['eef_xyz_m']))
            relative_rotation = rotation.T@np.asarray(sim.data.body_xmat[body]).reshape(3, 3)
            samples.append({'row': index, 'snapshot': ref, 'relative_position_m': relative_position.tolist(),
                'relative_rotation': relative_rotation.tolist()})
        delta = np.linalg.norm(np.asarray(samples[1]['relative_position_m'])-samples[0]['relative_position_m'])
        angle = Rotation.from_matrix(np.asarray(samples[1]['relative_rotation'])
            @np.asarray(samples[0]['relative_rotation']).T).magnitude()
        records.append({'job': '9026_'+job, 'samples': samples,
            'private_relative_translation_m': float(delta), 'private_relative_rotation_rad': float(angle)})
    finally:
        env.close()
output = base/'reports/9026_relative_payload_private_CPU_20261018.json'
output.write_text(json.dumps({'records': records, 'controls': 0, 'gpu_used': False,
    'private_diagnostic_only': True, 'runtime_or_training_use': False}, indent=2)+'\n')
print(json.dumps({'output': str(output), 'results': [{k:r[k] for k in (
    'job', 'private_relative_translation_m', 'private_relative_rotation_rad')} for r in records]}))
