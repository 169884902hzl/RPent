"""Distinguish dropped payload from a public hold-verifier error, without controls."""
# ruff: noqa: E402 -- pin CPU and the recorded source before simulator imports
import hashlib
import json
import os
import pickle
import sys
from pathlib import Path

os.environ.update(CUDA_VISIBLE_DEVICES='', LIBERO_TYPE='standard', OPENBLAS_NUM_THREADS='1')
root = Path('/public/home/sunyihan/rpent_libero_eval')
source = root/'source_bounded_chunk_v3_distal_pad_20261018_5e1c8fc'
# This source contains the same simulator restoration API as ee42501.
sys.path.insert(0, str(source))
import mujoco
import numpy as np
from libero.libero.envs.env_wrapper import ControlEnv

from robots.libero.v5_branch_state import restore_actuators
from robots.libero.v5_reset_seed import attach_reset_seed

directory, = (root/'results/bounded_skills/feasibility_20261017/job9515_2').glob('*oracle_k4')
raw_choices = (directory/'choices.jsonl').read_bytes()
rows = [json.loads(line) for line in raw_choices.splitlines()]
case = json.loads((directory/'summary.json').read_text())['case']
env = ControlEnv(bddl_file_name=case['bddl']['path'], use_camera_obs=False,
    has_renderer=False, has_offscreen_renderer=False, camera_names=[], ignore_done=True, horizon=10015)
attach_reset_seed(env)
env.seed(0)
env.reset()
records = []
try:
    for index, row in enumerate(rows):
        ref = row.get('private_pre_execution_snapshot')
        if ref is None:
            continue
        raw = Path(ref['path']).read_bytes()
        assert hashlib.sha256(raw).hexdigest() == ref['sha256']
        saved = pickle.loads(raw)
        env.set_init_state(saved['sim_state'])
        obs = restore_actuators(env, saved['actuator_state'])
        sim = env.env.sim
        residual = float(np.max(np.abs(sim.get_state().flatten()-saved['sim_state'])))
        assert residual < 1e-8
        obj, = [name for name in env.env.obj_body_id if 'cream_cheese' in name]
        body = env.env.obj_body_id[obj]
        geometry = env.env.objects_dict[obj]
        contacts = []
        for contact in sim.data.contact[:sim.data.ncon]:
            names = [mujoco.mj_id2name(sim.model._model, mujoco.mjtObj.mjOBJ_GEOM, int(g))
                for g in (contact.geom1, contact.geom2)]
            if any(name and 'cream_cheese' in name for name in names):
                contacts.append({'geoms': names, 'distance_m': float(contact.dist)})
        records.append({'row': index, 'snapshot': ref, 'restore_max_residual': residual,
            'object_xyz_m': np.asarray(sim.data.body_xpos[body]).tolist(),
            'eef_xyz_m': np.asarray(obs['robot0_eef_pos']).tolist(),
            'request_eef_error_m': float(np.linalg.norm(np.asarray(obs['robot0_eef_pos'])-row['request']['robot']['eef_xyz_m'])),
            'dual_finger_contact': bool(env.env._check_grasp(env.env.robots[0].gripper, geometry.contact_geoms)),
            'contacts': contacts, 'native_success': bool(env.env._check_success()),
            'receipts': [{k:r[k] for k in ('skill','outcome','stop_reason','steps_used')} for r in row['receipts']]})
finally:
    env.close()
report = {'case': case, 'job': '9515_2', 'restoration_source': str(source),
    'choices_sha256': hashlib.sha256(raw_choices).hexdigest(), 'records': records,
    'scope': 'Private restoration diagnosis; no steps, RPC, render, training or control coordinates',
    'controls': 0, 'gpu_used': False, 'runtime_modified': False, 'model_visible': False,
    'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
output = root/'coordination/bounded_skills_20261016/reports/box9515_transport_private_CPU_20261018.json'
with output.open('x') as stream:
    json.dump(report, stream, indent=2)
    stream.write('\n')
for record in records:
    print(json.dumps(record), flush=True)
