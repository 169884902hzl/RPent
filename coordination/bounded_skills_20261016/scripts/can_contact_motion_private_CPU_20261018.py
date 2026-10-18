# Copyright 2026 Zhilun Hu.
# SPDX-License-Identifier: Apache-2.0
"""Privately check saved can motion; never export truth to runtime geometry."""
# ruff: noqa: E402 -- pin CPU and original-task source before simulator imports
import hashlib
import json
import os
import pickle
import sys
from pathlib import Path

os.environ.update(CUDA_VISIBLE_DEVICES='', LIBERO_TYPE='standard',
    OPENBLAS_NUM_THREADS='1', MUJOCO_GL='egl')
root = Path('/public/home/sunyihan/rpent_libero_eval')
base = root/'coordination/bounded_skills_20261016'
sys.path.insert(0, str(root/'source_bounded_chunk_v3_precontact_stationary_20261018_c1bc859'))

import numpy as np
from libero.libero.envs.env_wrapper import ControlEnv
from scipy.spatial.transform import Rotation

from robots.libero.v5_branch_state import restore_actuators
from robots.libero.v5_reset_seed import attach_reset_seed

records = []
for job in ('9026_22', '9026_25'):
    directory, = (root/'results/bounded_skills/feasibility_20261017'/('job'+job)).glob('*oracle*')
    rows = [json.loads(line) for line in (directory/'choices.jsonl').read_bytes().splitlines()]
    episode = json.loads((directory.parent/'episodes.jsonl').read_bytes().splitlines()[0])
    env = ControlEnv(bddl_file_name=episode['case']['bddl']['path'], use_camera_obs=False,
        has_renderer=False, has_offscreen_renderer=False, camera_names=[],
        ignore_done=True, horizon=10015)
    attach_reset_seed(env)
    env.seed(0)
    env.reset()
    samples = []
    try:
        names = [name for name in env.env.obj_body_id if 'alphabet_soup' in name]
        assert len(names) == 1, names
        body = env.env.obj_body_id[names[0]]
        for index in (0, 1):
            reference = rows[index]['private_pre_execution_snapshot']
            raw = Path(reference['path']).read_bytes()
            assert hashlib.sha256(raw).hexdigest() == reference['sha256']
            saved = pickle.loads(raw)
            env.set_init_state(saved['sim_state'])
            restore_actuators(env, saved['actuator_state'])
            sim = env.env.sim
            error = float(np.max(np.abs(sim.get_state().flatten()-saved['sim_state'])))
            assert error < 1e-8
            samples.append({'row': index, 'snapshot': reference, 'restore_error': error,
                'private_position_m': np.asarray(sim.data.body_xpos[body]).tolist(),
                'private_rotation': np.asarray(sim.data.body_xmat[body]).reshape(3, 3).tolist()})
        shift = np.asarray(samples[1]['private_position_m'])-samples[0]['private_position_m']
        rotation = Rotation.from_matrix(np.asarray(samples[1]['private_rotation'])
            @np.asarray(samples[0]['private_rotation']).T)
        records.append({'job': job, 'body': names[0], 'samples': samples,
            'private_translation_m': shift.tolist(),
            'private_rotation_rad': float(rotation.magnitude()),
            'private_rotation_vector': rotation.as_rotvec().tolist()})
    finally:
        env.close()
report = {'records': records, 'controls': 0, 'gpu_used': False,
    'private_diagnostic_only': True, 'runtime_or_training_use': False,
    'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
output = base/'reports/can_contact_motion_private_CPU_20261018.json'
output.write_text(json.dumps(report, indent=2)+'\n')
print(json.dumps({'output': str(output), 'results': [{k: r[k] for k in
    ('job', 'private_translation_m', 'private_rotation_rad', 'private_rotation_vector')}
    for r in records]}))
