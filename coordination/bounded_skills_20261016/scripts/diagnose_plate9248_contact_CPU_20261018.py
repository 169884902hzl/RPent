# Copyright 2026 Zhilun Hu.
# SPDX-License-Identifier: Apache-2.0
"""Inspect privately saved plate contact states without issuing actions."""
# ruff: noqa: E402 -- pin the recorded source and disable GPUs before imports
import argparse
import hashlib
import json
import os
import pickle
import sys
from pathlib import Path

os.environ.update(CUDA_VISIBLE_DEVICES='', LIBERO_TYPE='standard', OPENBLAS_NUM_THREADS='1')
root = Path('/public/home/sunyihan/rpent_libero_eval')
parser = argparse.ArgumentParser()
parser.add_argument('--source', type=Path, default=root/'source_bounded_chunk_v3_support_plane_20261018_ec89f74')
parser.add_argument('--tag', default='original20_support_roundrobin_20261018')
parser.add_argument('--jobs', default='9248_8,9248_19')
parser.add_argument('--rows', default='0,1,2,5,10,20,-1')
parser.add_argument('--output', type=Path,
    default=root/'coordination/bounded_skills_20261016/reports/plate9248_contact_private_CPU_20261018.json')
args = parser.parse_args()
assert not args.output.exists(), 'Preserve the previous physical diagnosis'
source = args.source
os.environ['LIBERO_CONFIG_PATH'] = str(root/'runtime_config')
sys.path.insert(0, str(source))
import mujoco
import numpy as np
from libero.libero.envs.env_wrapper import ControlEnv

from robots.libero.v5_branch_state import restore_actuators
from robots.libero.v5_reset_seed import attach_reset_seed

base = root/'coordination/bounded_skills_20261016'
submission = json.loads((base/'reports'/f'{args.tag}_full_submission.json').read_text())
manifest = json.loads(Path(submission['manifest']['path']).read_text())
results = []
for job in args.jobs.split(','):
    index = int(job.split('_')[1])
    case = manifest['cases'][index]
    assert case['category'] == 'plate_push' and case['episode']['suite'] == 'libero_goal'
    choices = next((root/'results/bounded_skills/feasibility_20261017'/('job'+job)).glob('*oracle*/choices.jsonl'))
    captured = choices.read_bytes()
    rows = [json.loads(line) for line in captured.splitlines()]
    env = ControlEnv(bddl_file_name=case['bddl']['path'], use_camera_obs=False,
        has_renderer=False, has_offscreen_renderer=False, camera_names=[], ignore_done=True, horizon=10015)
    attach_reset_seed(env)
    env.seed(0)
    env.reset()
    records = []
    try:
        selected = {index if index >= 0 else len(rows)+index for index in map(int, args.rows.split(','))}
        for index in sorted(index for index in selected if 0 <= index < len(rows)):
            row = rows[index]
            if 'private_pre_execution_snapshot' not in row:
                continue
            ref = row['private_pre_execution_snapshot']
            raw = Path(ref['path']).read_bytes()
            assert hashlib.sha256(raw).hexdigest() == ref['sha256']
            saved = pickle.loads(raw)
            env.set_init_state(saved['sim_state'])
            restore_actuators(env, saved['actuator_state'])
            sim = env.env.sim
            residual = float(np.max(abs(sim.get_state().flatten()-saved['sim_state'])))
            assert residual < 1e-8
            model, data = sim.model._model, sim.data._data
            plate_geoms, fingers, contacts = [], [], []
            for geom in range(model.ngeom):
                name = mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_GEOM, geom) or ''
                if not model.geom_contype[geom] and not model.geom_conaffinity[geom]:
                    continue
                if 'plate' in name.lower():
                    plate_geoms.append((geom, name))
                if 'finger' in name.lower() and 'gripper' in name.lower():
                    fingers.append((geom, name))
            for contact in sim.data.contact[:sim.data.ncon]:
                pair = [mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_GEOM, int(g))
                        for g in (contact.geom1, contact.geom2)]
                if any(name and 'plate' in name.lower() for name in pair):
                    contacts.append({'geoms': pair, 'distance_m': float(contact.dist),
                        'position_world_m': np.asarray(contact.pos).tolist(),
                        'normal_world': np.asarray(contact.frame).reshape(3, 3)[0].tolist()})
            nearest = None
            for left, left_name in fingers:
                for right, right_name in plate_geoms:
                    points = np.zeros(6)
                    distance = float(mujoco.mj_geomDistance(model, data, left, right, 1., points))
                    if nearest is None or distance < nearest['distance_m']:
                        nearest = {'geoms': [left_name, right_name], 'distance_m': distance}
            ordered = [{key: candidate[key] for key in ('id', 'skill', 'parameters')}
                for cid in row['decision']['candidate_ids'] for candidate in row['request']['candidates']
                if candidate['id'] == cid]
            plate_body = int(model.geom_bodyid[plate_geoms[0][0]])
            records.append({'index': index, 'snapshot': ref, 'restore_max_residual': residual,
                'private_plate_position_world_m': np.asarray(data.xpos[plate_body]).tolist(),
                'private_plate_quat_wxyz': np.asarray(data.xquat[plate_body]).tolist(),
                'public_robot': row['request']['robot'], 'decision_in_execution_order': ordered,
                'plate_contacts': contacts, 'nearest_private_finger_plate_distance': nearest,
                'finger_collision_geoms': fingers, 'plate_collision_geoms': plate_geoms,
                'receipts': [{key: item[key] for key in ('skill', 'outcome', 'stop_reason', 'steps_used')}
                             for item in row.get('receipts', [])]})
    finally:
        env.close()
    results.append({'job': job, 'case': case, 'captured_decisions': len(rows),
        'choices': str(choices), 'choices_sha256_at_capture': hashlib.sha256(captured).hexdigest(),
        'records': records})
output = args.output
with output.open('x') as stream:
    stream.write(json.dumps({'source': str(source), 'results': results,
    'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    'scope': 'private exact-state restoration and forward contact diagnosis; no action commands or rollout',
        'gpu_used': False, 'model_visible': False, 'used_for_control': False, 'training': False}, indent=2)+'\n')
print(json.dumps({'output': str(output), 'results': [{'job': item['job'], 'records': [
    {key: row[key] for key in ('index', 'nearest_private_finger_plate_distance', 'plate_contacts')}
    for row in item['records']]} for item in results]}))
