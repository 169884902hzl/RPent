"""Private CPU metrology of saved lift controls; never policy input or score."""
from pathlib import Path
import hashlib
import json
import os
import pickle
import sys

os.environ.update(CUDA_VISIBLE_DEVICES='', LIBERO_TYPE='standard', OPENBLAS_NUM_THREADS='1',
                  MUJOCO_GL='egl', PYOPENGL_PLATFORM='egl')
root = Path('/public/home/sunyihan/rpent_libero_eval')
sys.path.insert(0, str(root/'source_bounded_96679ad_20261017'))
import numpy as np
from libero.libero.envs.env_wrapper import ControlEnv
from robots.libero.v5_reset_seed import attach_reset_seed
from robots.libero.v5_branch_state import restore_actuators
from robots.libero.v5_grasp_truth import contact_sample

base = root/'results/bounded_skills/feasibility_20261017'
directory = next((base/'job8087_2').glob('*oracle*'))
path = directory/'choices.jsonl'
raw_choices = path.read_bytes()
rows = [json.loads(line) for line in raw_choices.decode().splitlines()]
manifest = base/'preparation/original20_manifest_96679ad_calibrated.json'
case = next(c for c in json.loads(manifest.read_text())['cases']
            if c['name'] == directory.name.removesuffix('_oracle_k4'))
env = ControlEnv(bddl_file_name=case['bddl']['path'], use_camera_obs=False,
    has_renderer=False, has_offscreen_renderer=False, camera_names=[], ignore_done=True, horizon=10015)
attach_reset_seed(env)
env.seed(case['episode']['seed'])
env.reset()

def restore(row):
    reference = row['private_pre_execution_snapshot']
    raw = Path(reference['path']).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == reference['sha256']
    saved = pickle.loads(raw)
    env.set_init_state(saved['sim_state'])
    observation = restore_actuators(env, saved['actuator_state'])
    state_error = float(np.max(np.abs(env.env.sim.get_state().flatten()-saved['sim_state'])))
    assert state_error < 1e-8
    return state_error, float(np.linalg.norm(observation['robot0_eef_pos']-np.asarray(row['request']['robot']['eef_xyz_m'])))

results = []
try:
    name = next(name for name in env.env.objects_dict if 'black_bowl' in name)
    restore(rows[0])
    original = contact_sample(env.env, name)
    for row in rows:
        for receipt, detail in zip(row['receipts'], row['execution_details']):
            if receipt['skill'] != 'lift':
                continue
            assert len(row['execution_details']) == 1
            state_error, initial_eef_error = restore(row)
            initial = contact_sample(env.env, name)
            samples, errors = [], []
            for control in detail['execution']['trace']:
                observation, *_ = env.step(np.asarray(control['action'], dtype=np.float32))
                samples.append(contact_sample(env.env, name))
                errors.append(float(np.linalg.norm(observation['robot0_eef_pos']-np.asarray(control['after']['eef_xyz_m']))))
            final = samples[-1]
            tail = [s for s in samples if s['sim_time'] >= final['sim_time']-.5]
            relative = np.asarray([s['relative_com_tcp'] for s in tail])
            plane = original['original_support_plane_z_m']
            summary = {'decision': row['index'], 'public_hold': detail['execution']['public_hold'],
                'public_receipt': receipt['outcome'], 'snapshot': row['private_pre_execution_snapshot'],
                'flat_state_restore_error': state_error, 'initial_eef_record_error_m': initial_eef_error,
                'max_eef_replay_error_m': max(errors), 'controls': len(samples),
                'tail_duration_s': final['sim_time']-tail[0]['sim_time'], 'tail_samples': len(tail),
                'tail_dual_contact_count': sum(s['dual_finger_contact'] for s in tail),
                'tail_non_gripper_contact_count': sum(bool(s['all_non_gripper_contact_geoms']) for s in tail),
                'tail_min_support_clearance_m': min(s['lower_extent_m']-plane for s in tail),
                'tail_max_relative_com_drift_m': float(np.linalg.norm(relative-relative[0], axis=1).max()),
                'initial_private_contact': initial, 'final_private_contact': final, 'samples': samples}
            results.append(summary)
            print(json.dumps({k: v for k, v in summary.items() if k not in
                ('samples', 'initial_private_contact', 'final_private_contact', 'snapshot')}), flush=True)
finally:
    env.close()
report = {'scope': 'CPU saved-control private lift diagnosis; not new task/confirmation score',
    'training_allowed': False, 'renderer_used': False, 'gpu_used': False,
    'private_labels_used_for_control': False, 'source_commit': '96679ad',
    'job': '8087_2', 'case': case, 'choices_prefix_sha256': hashlib.sha256(raw_choices).hexdigest(),
    'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    'original_private_support': original, 'rows': results}
output = root/'coordination/bounded_skills_20261016/reports/bowl8087_2_lift_private_CPU_20261018.json'
output.write_text(json.dumps(report, indent=2)+'\n')
