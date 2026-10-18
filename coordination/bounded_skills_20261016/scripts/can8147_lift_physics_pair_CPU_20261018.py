"""Pair old/new measured route screens at a saved original-scene contact.

The MuJoCo state is private restoration/diagnosis only. Control sees the same
saved public RGB-D and fresh proprioception. No rendering or GPU is used.
"""
# ruff: noqa: E402 -- select source and CPU before simulator imports
import hashlib
import json
import os
import pickle
import runpy
import sys
from pathlib import Path
from types import SimpleNamespace

os.environ.update(CUDA_VISIBLE_DEVICES='', LIBERO_TYPE='standard', OPENBLAS_NUM_THREADS='1')
root = Path('/public/home/sunyihan/rpent_libero_eval')
sys.path.insert(0, str(root/'source_bounded_8e49152_20261018'))
import numpy as np
from libero.libero.envs.env_wrapper import ControlEnv

from robots.libero.bounded_motion import SmoothMotion, measured_robot
from robots.libero.bounded_screen import PublicRouteScreen
from robots.libero.bounded_self_filter import gripper_at_measured_fingers
from robots.libero.v5_branch_state import restore_actuators
from robots.libero.v5_grasp_kinematics import PublicPoseScreen
from robots.libero.v5_grasp_truth import contact_sample
from robots.libero.v5_reset_seed import attach_reset_seed

script = root/'coordination/bounded_skills_20261016/scripts/can8147_contact_membership_CPU_20261018.py'
sys.argv = [str(script), 'dev']
public = runpy.run_path(str(script), run_name='saved_public_reconstruction')
adapter, row = public['adapter'], public['row']
base = root/'results/bounded_skills/feasibility_20261017'
plan = json.loads((base/'preparation/original20_manifest_8e49152_fused_contact.json').read_text())
case = next(c for c in plan['cases'] if c['name'] == 'box_transfer_libero_object_t0_s1')
ref = row['private_pre_execution_snapshot']
raw = Path(ref['path']).read_bytes()
assert hashlib.sha256(raw).hexdigest() == ref['sha256']
saved = pickle.loads(raw)
env = ControlEnv(bddl_file_name=case['bddl']['path'], use_camera_obs=False,
    has_renderer=False, has_offscreen_renderer=False, camera_names=[], ignore_done=True, horizon=10015)
attach_reset_seed(env)
env.seed(case['episode']['seed'])
env.reset()
results = []
try:
    for version in ('old', 'fused_contact'):
        env.set_init_state(saved['sim_state'])
        observation = restore_actuators(env, saved['actuator_state'])
        residual = float(np.max(np.abs(env.env.sim.get_state().flatten()-saved['sim_state'])))
        assert residual < 1e-8
        facade = SimpleNamespace(terminated=False, truncated=False, observation=observation, used=0)
        facade.raw_obs = lambda: facade.observation
        facade.execution_budget = lambda: {'used_sim_steps': facade.used,
            'remaining_sim_steps': 10000-row['sim_steps_before']-facade.used}
        samples = [contact_sample(env.env, 'alphabet_soup_1')]
        def step(action):
            observation, _, done, _ = env.step(np.asarray(action, dtype=np.float32))
            facade.observation = observation
            facade.used += 1
            facade.terminated = bool(done)
            samples.append(contact_sample(env.env, 'alphabet_soup_1'))
        primitives = SimpleNamespace(env=facade, _step_env=step)
        robot = measured_robot(primitives)
        geometry = gripper_at_measured_fingers(adapter.geometry, robot['finger_positions_m'])
        ik = PublicPoseScreen(adapter.robot_xml, robot['joint_positions_rad'], robot['eef_xyz_m'],
            robot['eef_quat_xyzw'], adapter.geometry['site_offset_in_gripper_m'], warm_start=True)
        if version == 'old':
            prefix = 'bounded_screen_e35_1_'
            points = public['load'](row['public_geometry_evidence'][prefix+'scene']['path'])
            target = public['load'](row['public_geometry_evidence'][prefix+'target']['path'])
        else:
            points, target = public['screen'].points, public['screen'].target
        screen = PublicRouteScreen(points, geometry, ik, opening=robot['gripper_opening_m'],
            contact_points=target, contact_allowed=True,
            initial_pose={'xyz_m': robot['eef_xyz_m'], 'quat_xyzw': robot['eef_quat_xyzw']})
        goal = np.array(robot['eef_xyz_m'])+np.array([0., 0., .10])
        execution = SmoothMotion(primitives, screen).run([{'xyz_m': goal.tolist(),
            'quat_xyzw': robot['eef_quat_xyzw']}], gripper=1.)
        end = samples[-1]
        tail = [s for s in samples if s['sim_time'] >= end['sim_time']-.5]
        relative = np.asarray([s['relative_com_tcp'] for s in tail])
        plane = samples[0]['original_support_plane_z_m']
        result = {'method': version, 'flat_state_restore_residual': residual,
            'public_initial_eef_m': robot['eef_xyz_m'], 'controls': facade.used,
            'stop_reason': execution['stop_reason'], 'executed': execution['executed'],
            'endpoint_error_m': execution.get('endpoint_error_m'),
            'private_body_rise_m': float(end['target_com_xyz'][2]-samples[0]['target_com_xyz'][2]),
            'tail_samples': len(tail), 'tail_duration_s': end['sim_time']-tail[0]['sim_time'],
            'tail_dual_contact_count': sum(s['dual_finger_contact'] for s in tail),
            'tail_non_gripper_contact_count': sum(bool(s['all_non_gripper_contact_geoms']) for s in tail),
            'tail_min_support_clearance_m': min(s['lower_extent_m']-plane for s in tail),
            'tail_max_relative_com_drift_m': float(np.linalg.norm(relative-relative[0], axis=1).max()),
            'execution': execution, 'private_contact_samples': samples}
        results.append(result)
        print(json.dumps({k:v for k,v in result.items() if k not in ('execution', 'private_contact_samples')}), flush=True)
finally:
    env.close()
output = root/'coordination/bounded_skills_20261016/reports/can8147_lift_physics_pair_CPU_20261018.json'
output.write_text(json.dumps({'scope': 'saved-state CPU physics diagnosis; not full task or confirmation score',
    'source_commit': plan['source_commit'], 'training': False, 'gpu_used': False, 'renderer_used': False,
    'private_labels_used_for_control': False, 'case': case, 'snapshot': ref,
    'public_choices_prefix_sha256': hashlib.sha256(public['choices'].read_bytes()).hexdigest(),
    'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), 'results': results}, indent=2)+'\n')
