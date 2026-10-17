from pathlib import Path
import hashlib
import json
import os
import pickle
import sys

os.environ.update(CUDA_VISIBLE_DEVICES='', LIBERO_TYPE='standard', OPENBLAS_NUM_THREADS='1',
                  MUJOCO_GL='egl', PYOPENGL_PLATFORM='egl')
root = Path('/public/home/sunyihan/rpent_libero_eval')
sys.path.insert(0, str(root/'source_bounded_cee33e8_20261018'))
import numpy as np
from libero.libero.envs.env_wrapper import ControlEnv
from robots.libero.v5_reset_seed import attach_reset_seed
from robots.libero.v5_branch_state import restore_actuators
from robots.libero.v5_grasp_truth import contact_sample

directory = next((root/'results/bounded_skills/feasibility_20261017/job8111_20').glob('*oracle*'))
path = directory/'choices.jsonl'
rows = [json.loads(line) for line in path.open()]
row_index = int(sys.argv[1]) if len(sys.argv) > 1 else 2
row = rows[row_index]
manifest = json.loads((root/'results/bounded_skills/feasibility_20261017/preparation/original20_manifest_cee33e8_calibrated.json').read_text())
episode = {'case': next(c for c in manifest['cases'] if directory.name == c['name']+'_oracle_k4')}
reference = row['private_pre_execution_snapshot']
raw = Path(reference['path']).read_bytes()
assert hashlib.sha256(raw).hexdigest() == reference['sha256']
saved = pickle.loads(raw)
env = ControlEnv(bddl_file_name=episode['case']['bddl']['path'], use_camera_obs=False,
    has_renderer=False, has_offscreen_renderer=False, camera_names=[], ignore_done=True, horizon=10015)
attach_reset_seed(env)
env.seed(0)
env.reset()
samples = []
try:
    name = next(name for name in env.env.objects_dict if 'alphabet_soup' in name)
    env.set_init_state(saved['sim_state'])
    restore_actuators(env, saved['actuator_state'])
    flat_error = float(np.max(np.abs(env.env.sim.get_state().flatten()-saved['sim_state'])))
    assert flat_error < 1e-8
    initial = contact_sample(env.env, name)
    controls = row['execution_details'][0]['execution']['trace']
    for index, control in enumerate(controls):
        observation, _, _, _ = env.step(np.asarray(control['action'], dtype=np.float32))
        truth = contact_sample(env.env, name)
        error = float(np.max(np.abs(np.asarray(observation['robot0_eef_pos'])-control['after']['eef_xyz_m'])))
        samples.append({'index': index, 'public_eef_replay_error_m': error,
            'public_opening_m': control['after']['gripper_opening_m'], 'private_truth': truth})
finally:
    env.close()
report = {'scope': 'CPU replay of saved original-scene controls for private contact diagnosis only; not a new task result',
    'training_allowed': False, 'renderer_used': False, 'gpu_used': False,
    'private_labels_used_for_control': False, 'source_commit': 'cee33e8', 'row': row_index,
    'snapshot': reference, 'flat_state_restore_error': flat_error,
    'choices_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
    'initial_private_truth': initial, 'samples': samples,
    'max_public_eef_replay_error_m': max(s['public_eef_replay_error_m'] for s in samples),
    'first_without_dual_contact': next((s['index'] for s in samples if not s['private_truth']['dual_finger_contact']), None),
    'first_non_gripper_support': next((s['index'] for s in samples if s['private_truth']['all_non_gripper_contact_geoms']), None)}
output = root/f'coordination/bounded_skills_20261016/reports/box8111_row{row_index}_contact_replay_private_CPU_20261018.json'
output.write_text(json.dumps(report, indent=2)+'\n')
print(json.dumps({k: v for k, v in report.items() if k not in ('samples', 'initial_private_truth')}, indent=2))
for index in sorted({0, len(samples)-1, *[max(0, (report['first_without_dual_contact'] or 0)+delta) for delta in (-2, -1, 0, 1, 2)]}):
    print(json.dumps({'index':index,'eef_error_m':samples[index]['public_eef_replay_error_m'],'dual':samples[index]['private_truth']['dual_finger_contact'],'support':samples[index]['private_truth']['all_non_gripper_contact_geoms']}))
