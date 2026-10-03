"""Compare actual original-task wrist actuation gains without images or a policy."""

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import time
from types import SimpleNamespace

import numpy as np

from scripts.probe_v5_traced_motion_cpu import HeadlessAdapter


def probe(suite_name, task, seed, output, arm):
    from libero.libero.benchmark import get_benchmark
    from libero.libero.envs.env_wrapper import ControlEnv
    from robots.libero.tools import LiberoPrimitives

    suite = get_benchmark(suite_name)()
    init = suite.get_task_init_states(task)[seed]
    env = None
    started = time.monotonic()
    try:
        env = ControlEnv(bddl_file_name=suite.get_task_bddl_file_path(task), use_camera_obs=False,
                         has_offscreen_renderer=False, has_renderer=False, camera_names=[],
                         initialization_noise=None, ignore_done=True, horizon=10015)
        env.seed(seed)
        env.reset()
        raw = env.set_init_state(init)
        for _ in range(15):
            raw, _, _, _ = env.step(np.array([0, 0, 0, 0, 0, 0, -1.]))
        robot = env.env.robots[0]
        parts = getattr(robot, 'part_controllers', None)
        controllers = parts if parts is not None else {'arm': robot.controller}
        arm_parts = [(name, item) for name, item in controllers.items()
                     if np.asarray(getattr(item, 'output_max', [])).shape == (6,)]
        if len(arm_parts) != 1:
            raise ValueError('wrist diagnostic needs one measured six-axis arm controller')
        part_name, controller = arm_parts[0]
        actual_scale = float(np.asarray(controller.output_max)[5])
        input_max = float(np.asarray(controller.input_max)[5])
        if not actual_scale > 0 or input_max != 1:
            raise ValueError('wrist diagnostic requires a positive scale with normalized input_max=1')
        start_position = np.array(raw['robot0_eef_pos'], copy=True)
        with output.open('x') as stream:
            adapter = HeadlessAdapter(env, raw, stream)
            if arm == 'scaled':
                native_step = adapter.step

                def calibrated_step(action):
                    action = np.array(action, copy=True)
                    action[5] *= .10 / actual_scale
                    return native_step(action)

                adapter.step = calibrated_step
            primitives = LiberoPrimitives(adapter, None, None, lambda: None)
            primitives.set_obs(adapter.wrap(raw))
            if arm == 'coupled_pose':
                result = primitives.move_pose(start_position.tolist(), target_yaw=math.pi/2,
                                              rotation_action_scale=actual_scale, gripper=-1,
                                              max_steps=150, ori_tol=.02)
            elif arm == 'runtime_hold':
                from robots.libero.v5_runtime import V5Executor
                if actual_scale != .5:
                    raise ValueError('runtime wrist experiment expects the validated 0.5 yaw scale')
                executor = V5Executor(SimpleNamespace(primitives=primitives), SimpleNamespace(),
                                      wrist_position_hold_v1=True)
                receipt = {}
                reached = executor.stage_wrist(math.pi/2, receipt)
                result = {**executor.motion_evidence[-1], 'stage_reached': reached,
                          'receipt': receipt}
            else:
                result = primitives.rotate_wrist(target_yaw=math.pi/2, gripper=-1, max_steps=150)
            from scipy.spatial.transform import Rotation
            rotation = Rotation.from_quat(adapter.raw['robot0_eef_quat']).as_matrix()
            yaw = math.atan2(rotation[1, 0], rotation[0, 0])
            stream.flush()
            return {'suite': suite_name, 'task': task, 'seed': seed, 'arm': arm,
                    'actual_controller_output_scale': actual_scale, 'controller': type(controller).__name__,
                    'controller_part': part_name,
                    'legacy_rotation_denominator': .10, 'result': result,
                    'max_steps': 150, 'actual_control_steps': adapter.steps,
                    'final_yaw_error_rad': (math.pi/2-yaw+math.pi) % (2*math.pi)-math.pi,
                    'position_displacement_m': float(np.linalg.norm(primitives._last_obs_eef_pos-start_position)),
                    'contacts': dict(adapter.contacts), 'wall_s': time.monotonic()-started,
                    'trace': str(output), 'trace_sha256': hashlib.sha256(output.read_bytes()).hexdigest()}
    finally:
        if env is not None:
            env.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--arms', nargs='+', choices=('legacy', 'scaled', 'coupled_pose', 'runtime_hold'),
                        default=('legacy', 'scaled', 'coupled_pose'))
    args = parser.parse_args()
    if os.environ.get('LIBERO_TYPE') != 'standard':
        raise ValueError('this diagnostic is original-task only')
    args.output.mkdir(parents=True, exist_ok=False)
    records = []
    for suite in ('libero_spatial', 'libero_object', 'libero_goal', 'libero_10'):
        for arm in args.arms:
            trace = args.output / f'{suite}_task0_init10_{arm}.jsonl'
            records.append(probe(suite, 0, 10, trace, arm))
    report = {'scope': 'Headless original wrist control diagnosis; no perception, VLA, model score or training rows.',
              'records': records, 'new_training_rows': 0,
              'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    (args.output/'report.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(records))


if __name__ == '__main__':
    main()
