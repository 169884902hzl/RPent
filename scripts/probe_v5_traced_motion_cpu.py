"""Replay traced original-task control actions without rendering or a VLA model."""

import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import time

import numpy as np


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class HeadlessAdapter:
    def __init__(self, env, raw, output):
        self.env, self.raw = env, raw
        self.terminated = self.truncated = self.return_all_frames = False
        self.contacts = Counter()
        self.steps = 0
        self.output = output

    @staticmethod
    def wrap(raw):
        from scipy.spatial.transform import Rotation
        return {'states': np.concatenate((raw['robot0_eef_pos'],
                                          Rotation.from_quat(raw['robot0_eef_quat']).as_rotvec(),
                                          raw['robot0_gripper_qpos']))}

    def step(self, action):
        self.raw, reward, done, info = self.env.step(action)
        self.steps += 1
        contacts = []
        model, data = self.env.sim.model, self.env.sim.data
        for contact in data.contact[:data.ncon]:
            names = [model.geom_id2name(int(g)) for g in (contact.geom1, contact.geom2)]
            is_robot = [bool(n and ('robot0' in n or 'gripper0' in n)) for n in names]
            if is_robot[0] != is_robot[1]:
                pair = ' <> '.join(str(n) for n in names)
                self.contacts[pair] += 1
                contacts.append({'geoms': names, 'distance_m': float(contact.dist)})
        record = {'step': self.steps, 'action': np.asarray(action).tolist(),
                  'eef_xyz': self.raw['robot0_eef_pos'].tolist(),
                  'eef_quat': self.raw['robot0_eef_quat'].tolist(),
                  'gripper_qpos': self.raw['robot0_gripper_qpos'].tolist(),
                  'robot_contacts': contacts, 'native_done': bool(done)}
        self.output.write(json.dumps(record) + '\n')
        # This diagnostic executes a finite recorded sequence, never a task
        # evaluation. Native completion is logged without cutting the prefix.
        return self.wrap(self.raw), reward, False, False, info

    def raw_obs(self):
        return self.raw


def replay(config, event, output, arm):
    from libero.libero.benchmark import get_benchmark
    from libero.libero.envs.env_wrapper import ControlEnv
    from robots.libero.tools import LiberoPrimitives

    suite = get_benchmark(config['suite'])()
    bddl = suite.get_task_bddl_file_path(config['task'])
    init = suite.get_task_init_states(config['task'])[config['seed']]
    start, env = time.monotonic(), None
    try:
        env = ControlEnv(bddl_file_name=bddl, use_camera_obs=False,
                         has_offscreen_renderer=False, has_renderer=False,
                         horizon=10015, ignore_done=True, camera_names=[], initialization_noise=None)
        env.seed(config['seed'])
        env.reset()
        raw = env.set_init_state(init)
        for _ in range(15):
            raw, _, _, _ = env.step(np.array([0, 0, 0, 0, 0, 0, -1.], dtype=float))
        expected = np.array(event['robot_measurement']['eef_xyz'])
        initial_delta = float(np.linalg.norm(raw['robot0_eef_pos'] - expected))
        if initial_delta > .002:
            raise ValueError('initial proprioception differs from registered prefix by more than2mm')
        motions = event['motion_evidence']
        last_move = max(i for i, item in enumerate(motions) if item['name'] == 'move_to')
        results = []
        with (output / (arm + '_steps.jsonl')).open('x') as stream:
            adapter = HeadlessAdapter(env, raw, stream)
            primitive = LiberoPrimitives(adapter, None, None, lambda: None)
            primitive.set_obs(adapter.wrap(raw))
            for i, item in enumerate(motions):
                recorded_start = item.get('start_eef_pos')
                start_delta = float(np.linalg.norm(primitive._last_obs_eef_pos - recorded_start)) if recorded_start is not None else None
                if item['name'] == 'move_to':
                    if 'gripper_command' not in item:
                        raise ValueError('traced servo has no actual gripper command')
                    budget = item['max_steps'] * (4 if arm == 'extended_final_servo' and i == last_move else 1)
                    result = primitive.move_to(item['target_xyz'], gripper=item['gripper_command'], max_steps=budget)
                elif item['name'] == 'vla_act_chunk':
                    actions = item['actions']
                    if len(actions) != item['executed_action_count']:
                        raise ValueError('VLA executed action prefix count differs')
                    for action in actions:
                        primitive._step_env(np.array(action))
                    result = {'name': item['name'], 'executed_action_count': len(actions),
                              'final_eef_pos': primitive._last_obs_eef_pos.tolist()}
                else:
                    raise ValueError('unsupported recorded motion; do not approximate: ' + item['name'])
                endpoint_delta = float(np.linalg.norm(
                    primitive._last_obs_eef_pos - np.array(item['final_eef_pos'])))
                results.append({'motion_index': i, 'recorded_motion': item, 'replay': result,
                                'recorded_start_delta_m': start_delta, 'recorded_endpoint_delta_m': endpoint_delta})
            robot = env.env.robots[0]
            return {'arm': arm, 'initial_eef_delta_m': initial_delta,
                    'motions': results, 'robot_contacts': dict(adapter.contacts),
                    'executed_steps': adapter.steps, 'arm_qpos': env.sim.data.qpos[robot._ref_joint_pos_indexes].tolist(),
                    'arm_joint_limits': env.sim.model.jnt_range[robot._ref_joint_indexes].tolist(),
                    'wall_s': time.monotonic() - start, 'error': None}
    finally:
        if env is not None:
            env.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--motion-report', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    if os.environ.get('LIBERO_TYPE') != 'standard':
        parser.error('headless prefix diagnosis requires original LIBERO')
    args.output.mkdir(parents=True, exist_ok=False)
    results, raised, identity = [], None, {}
    try:
        report = json.loads(args.motion_report.read_text())
        if len(report['cases']) != 1:
            raise ValueError('diagnostic expects exactly one registered original prefix')
        case = report['cases'][0]
        if not case['reached_registered_prefix_end']:
            raise ValueError('registered high-level prefix did not complete')
        trace = Path(case['choices']['path'])
        if sha(trace) != case['choices']['sha256']:
            raise ValueError('recorded motion trace changed')
        rows = [json.loads(line) for line in trace.read_text().splitlines() if line.strip()]
        if len(rows) != 1 or rows[0]['selected'] != 'grasp(e24,direct)':
            raise ValueError('registered first original grasp differs')
        if not any(x['name'] == 'vla_act_chunk' for x in rows[0]['motion_evidence']):
            raise ValueError('original grasp did not reach VLA; do not call it contact-prefix reproduction')
        config = json.loads((trace.parent / 'config.json').read_text())
        if config['libero_type'] != 'standard' or config['suite'] != 'libero_10' or config['task'] != 3 or config['seed'] != 37:
            raise ValueError('registered original scene identity changed')
        identity = {'motion_report_sha256': sha(args.motion_report),
                    'choices_path': str(trace), 'choices_sha256': sha(trace),
                    'suite': config['suite'], 'task': config['task'], 'init': config['seed']}
        for arm in ('recorded_budget', 'extended_final_servo'):
            result = replay(config, rows[0], args.output, arm)
            results.append(result)
            (args.output / 'report_partial.json').write_text(json.dumps(results, indent=2) + '\n')
    except Exception as error:
        import traceback
        raised = {'error': repr(error), 'traceback': traceback.format_exc()}
    result = {
        'scope': 'Headless replay of actual traced Pi05 actions and servo targets; independent physical diagnosis, not task/model scores or new training labels. Extended final servo is a diagnostic arm, not an adopted fix.',
        'identity': identity, 'results': results, 'exception': raised,
        'script_sha256': sha(__file__), 'new_training_rows': 0,
        'state_or_candidate_format_modified': False,
    }
    path = args.output / 'report.json'
    path.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'report': str(path), 'sha256': sha(path), 'exception': raised,
                      'results': [{'arm': x['arm'], 'steps': x['executed_steps'],
                                   'contacts': sum(x['robot_contacts'].values())} for x in results]}), flush=True)
    if raised:
        raise RuntimeError('traced-motion CPU probe incomplete; inspect preserved report')


if __name__ == '__main__':
    main()
