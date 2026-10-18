"""Inspect saved original-scene contact states without sending any controls."""
# ruff: noqa: E402 -- select the recorded immutable source and CPU first
import hashlib
import json
import os
import pickle
import sys
from pathlib import Path

os.environ.update(CUDA_VISIBLE_DEVICES='', LIBERO_TYPE='standard', OPENBLAS_NUM_THREADS='1')
root = Path('/public/home/sunyihan/rpent_libero_eval')
sys.path.insert(0, str(root / 'source_bounded_7e2e869_20261018'))
import mujoco
import numpy as np
from libero.libero.envs.bddl_utils import robosuite_parse_problem
from libero.libero.envs.env_wrapper import ControlEnv

from robots.libero.v5_branch_state import restore_actuators
from robots.libero.v5_reset_seed import attach_reset_seed

base = root / 'results/bounded_skills/feasibility_20261017'
manifest = base / 'preparation/original20_manifest_7e2e869_contact_extent.json'
plan = json.loads(manifest.read_text())
results = []
for job, token in [('8117_160', 'plate'), ('8147_21', 'alphabet'), ('8145_60', 'mug')]:
    path = next((base / ('job' + job)).glob('*oracle*/choices.jsonl'))
    captured = path.read_bytes()
    rows = [json.loads(line) for line in captured.splitlines()]
    case = next(c for c in plan['cases'] if c['name'] + '_oracle_k4' == path.parent.name)
    goals = robosuite_parse_problem(case['bddl']['path'])['goal_state']
    env = ControlEnv(bddl_file_name=case['bddl']['path'], use_camera_obs=False,
        has_renderer=False, has_offscreen_renderer=False, camera_names=[], ignore_done=True, horizon=10015)
    attach_reset_seed(env)
    env.seed(0)
    env.reset()
    states = []
    try:
        for row in rows:
            if 'private_pre_execution_snapshot' not in row:
                states.append({'row': row['index'], 'not_reconstructed': 'selector_error_before_physical_request',
                    'error': row.get('error'), 'chosen': [], 'private_bodies': {},
                    'private_contacts': [], 'lift_screen_failures': []})
                continue
            ref = row['private_pre_execution_snapshot']
            raw = Path(ref['path']).read_bytes()
            assert hashlib.sha256(raw).hexdigest() == ref['sha256']
            saved = pickle.loads(raw)
            env.set_init_state(saved['sim_state'])
            restore_actuators(env, saved['actuator_state'])
            sim = env.env.sim
            residual = float(np.max(np.abs(sim.get_state().flatten() - saved['sim_state'])))
            assert residual < 1e-8
            model = sim.model._model
            contacts = []
            for contact_index, contact in enumerate(sim.data.contact[:sim.data.ncon]):
                names = [mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_GEOM, int(g))
                         for g in (contact.geom1, contact.geom2)]
                if any(name and token in name.lower() for name in names):
                    force = np.zeros(6)
                    mujoco.mj_contactForce(model, sim.data._data, contact_index, force)
                    contacts.append({'geoms': names, 'distance_m': float(contact.dist),
                        'position_m': np.asarray(contact.pos).tolist(), 'force_contact_frame': force.tolist()})
            bodies = {name: np.asarray(sim.data.body_xpos[identity]).tolist()
                      for name, identity in env.env.obj_body_id.items() if token in name.lower()}
            chosen = [c for c in row['request']['candidates'] if c['id'] in row['decision']['candidate_ids']]
            screens = [{k: d[k] for k in ('skill', 'parameters', 'reason', 'at', 'counts',
                'target_counts', 'payload_counts') if k in d}
                for d in row['candidate_screen_diagnostics'] if d.get('skill') == 'lift']
            anchors = [a for a in row['request']['anchors'] if token in a.get('label', a.get('name', '')).lower()]
            states.append({'row': row['index'], 'snapshot': ref, 'restore_max_residual': residual,
                'private_bodies': bodies, 'private_contacts': contacts,
                'private_goals': [{'goal': goal, 'satisfied': bool(env.env._eval_predicate(goal))} for goal in goals],
                'public_robot': row['request']['robot'], 'public_source_anchors': anchors,
                'chosen': [{k: c[k] for k in ('skill', 'parameters')} for c in chosen],
                'receipts': [{k: r[k] for k in ('skill', 'outcome', 'stop_reason', 'steps_used')} for r in row['receipts']],
                'lift_screen_failures': screens})
    finally:
        env.close()
    results.append({'job': job, 'choices': {'path': str(path), 'captured_bytes': len(captured),
        'sha256': hashlib.sha256(captured).hexdigest()}, 'states': states})
output = root / 'coordination/bounded_skills_20261016/reports/contact_plate_can_cup_private_CPU_20261018_r2.json'
output.write_text(json.dumps({'scope': 'saved contact diagnosis only; zero controls',
    'gpu_used': False, 'training': False, 'model_visible': False, 'used_for_control': False,
    'results': results}, indent=2) + '\n')
for result in results:
    print('job', result['job'])
    for state in result['states']:
        print(json.dumps({'row': state['row'], 'body': state['private_bodies'],
            'contacts': [c['geoms'] for c in state['private_contacts']],
            'chosen': state['chosen'], 'lift_screen_failures': state['lift_screen_failures']}, separators=(',', ':')))
