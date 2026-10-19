"""Read saved plate contacts and displacement for diagnosis; issue no controls."""
# ruff: noqa: E402 -- pin the original-task source and disable GPU before imports
import hashlib
import json
import os
import pickle
import sys
from pathlib import Path

os.environ.update(CUDA_VISIBLE_DEVICES='', LIBERO_TYPE='standard', OPENBLAS_NUM_THREADS='1')
root = Path('/public/home/sunyihan/rpent_libero_eval')
base = root/'coordination/bounded_skills_20261016'
receipt = json.loads((base/'reports/chunk_v3_directional_contact_20261018_full_submission.json').read_text())
sys.path.insert(0, receipt['snapshot'])
import mujoco
import numpy as np
from libero.libero.envs.env_wrapper import ControlEnv
from robots.libero.v5_branch_state import restore_actuators
from robots.libero.v5_reset_seed import attach_reset_seed

manifest = json.loads(Path(receipt['manifest']['path']).read_text())
results = []
for index in (160, 161):
    job = f"{receipt['job']}_{index}"
    case = manifest['cases'][index]
    directory, = (root/'results/bounded_skills/feasibility_20261017'/('job'+job)).glob('*oracle_k4')
    choices = directory/'choices.jsonl'
    raw = choices.read_bytes()
    rows = [json.loads(line) for line in raw.splitlines(keepends=True) if line.endswith(b'\n')]
    env = ControlEnv(bddl_file_name=case['bddl']['path'], use_camera_obs=False,
        has_renderer=False, has_offscreen_renderer=False, camera_names=[], ignore_done=True, horizon=10015)
    attach_reset_seed(env)
    env.seed(0)
    env.reset()
    records = []
    try:
        for row in rows:
            reference = row.get('private_pre_execution_snapshot')
            if reference is None:
                continue
            state_raw = Path(reference['path']).read_bytes()
            assert hashlib.sha256(state_raw).hexdigest() == reference['sha256']
            state = pickle.loads(state_raw)
            env.set_init_state(state['sim_state'])
            restore_actuators(env, state['actuator_state'])
            sim = env.env.sim
            residual = float(np.max(np.abs(sim.get_state().flatten()-state['sim_state'])))
            assert residual < 1e-8
            contacts = []
            for contact in sim.data.contact[:sim.data.ncon]:
                names = [mujoco.mj_id2name(sim.model._model, mujoco.mjtObj.mjOBJ_GEOM, int(g))
                         for g in (contact.geom1, contact.geom2)]
                if any(name and 'plate' in name.lower() for name in names):
                    contacts.append({'geoms': names, 'position_m': np.asarray(contact.pos).tolist(),
                                     'distance_m': float(contact.dist)})
            records.append({'index': row['index'], 'sim_steps_before': row['sim_steps_before'],
                'snapshot': reference, 'restore_max_error': residual,
                'private_plate_positions': {name: np.asarray(sim.data.body_xpos[bid]).tolist()
                    for name, bid in env.env.obj_body_id.items() if 'plate' in name.lower()},
                'private_contacts': contacts, 'private_task_success': bool(env.env._check_success()),
                'receipts': [{key: r[key] for key in ('skill', 'outcome', 'stop_reason', 'steps_used')}
                    for r in row['receipts']]})
    finally:
        env.close()
    results.append({'job': job, 'case': case, 'choices': {'path': str(choices),
        'captured_bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}, 'records': records})
output = base/'reports/plate9576_private_contacts_interim_r1_CPU_20261018.json'
with output.open('x') as stream:
    json.dump({'source': receipt['snapshot'], 'results': results,
        'scope': 'private posthoc diagnosis only; not runtime inputs or controls',
        'gpu_used': False, 'controls': 0, 'model_visible': False, 'training': False,
        'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}, stream, indent=2)
    stream.write('\n')
print(json.dumps({'output': str(output), 'jobs': [{'job': r['job'], 'rows': len(r['records']),
    'positions': [s['private_plate_positions'] for s in r['records']]} for r in results]}))
