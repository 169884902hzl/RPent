"""Compare retreat servo scaling from explicitly registered original snapshots."""

import argparse
import hashlib
import json
from pathlib import Path
import sys
import time

import numpy as np


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    registration = json.loads(args.manifest.read_text())
    source = Path(registration['report']['path'])
    assert sha(source) == registration['report']['sha256']
    previous = json.loads(source.read_text())
    args.output.mkdir(parents=True, exist_ok=False)
    from robots.libero.tools import LiberoPrimitives
    from robots.libero.v5_env_client import V5SkillEnvClient
    from rpent.utils.daemon import ProcessDaemon, pick_free_port
    from rpent.utils.rpc import wait_for_ready
    from rpent.utils.rpc.http_rpc import HttpRpcClient

    pairs = []
    for pair in previous['pairs']:
        snapshot_path = Path(pair['snapshot']['path'])
        assert sha(snapshot_path) == pair['snapshot']['sha256']
        snapshot = json.loads(snapshot_path.read_text())
        # The saved report used plain JSON lists; RPC expects the typed arrays
        # originally returned by oracle.snapshot.
        snapshot['sim_state'] = np.asarray(snapshot['sim_state'])
        snapshot['counters'] = {k: np.asarray(v) if isinstance(v, list) else v
                                for k, v in snapshot['counters'].items()}
        for robot in snapshot['actuator_state']['robots']:
            for gripper in robot['grippers'].values():
                gripper['current_action'] = np.asarray(gripper['current_action'])
            for fields in robot['controllers'].values():
                for key, value in fields.items():
                    if isinstance(value, list):
                        fields[key] = np.asarray(value)
        meta = snapshot['task']
        assert (meta['suite'], meta['task']) == ('libero_goal', 2)
        assert meta['seed'] in (12, 13)
        port = pick_free_port()
        daemon = ProcessDaemon(name='saved_retreat_controller', cmd=[sys.executable,
            '-m', 'robots.libero.v5_oracle_server', '--suite', meta['suite'],
            '--task', str(meta['task']), '--seed', str(meta['seed']),
            '--max-episode-steps', str(meta['max_episode_steps']),
            '--port', str(port), '--parent-watch'],
            log_path=str(args.output / (pair['case'] + '_env.log')))
        rpc = HttpRpcClient(f'http://127.0.0.1:{port}')
        daemon.start()
        try:
            wait_for_ready(rpc, daemon=daemon, timeout_s=300)
            env = V5SkillEnvClient(rpc, expected_meta=meta)
            primitives = LiberoPrimitives(env, None, None, lambda: None)
            primitives.reset()
            contract = rpc.call('oracle.controller_contract', timeout_s=120)
            (args.output/(pair['case']+'_controller.json')).write_text(
                json.dumps(contract, indent=2, default=lambda value: value.tolist())+'\n')
            controllers = [c for c in contract['robots'][0].values()
                           if len(c.get('output_max', [])) == 6]
            assert len(controllers) == 1
            controller = controllers[0]
            scales = np.asarray(controller['output_max'], dtype=float)
            assert np.allclose(controller['input_max'], 1)
            assert np.allclose(controller['input_min'], -1)
            assert np.allclose(controller['output_min'], -scales)
            assert np.allclose(scales[3:], scales[3])
            orientation = pair['initial_robot_orientation']
            targets = [m['target_xyz'] for m in pair['arms'][0]['motion_evidence']]
            assert targets
            result = {'case': pair['case'], 'snapshot': pair['snapshot'],
                      'loaded_controller_contract': contract, 'arms': [],
                      'waypoints': targets, 'max_steps_per_waypoint': 80,
                      'waypoint_acceptance_m': .02}
            for name, rotation_scale in [('direct_control', None),
                    ('initial_orientation_legacy_scale', .10),
                    ('initial_orientation_loaded_scale', float(scales[3]))]:
                observed = rpc.call('oracle.restore', args=[snapshot], timeout_s=120)
                env.last_obs = observed
                env._native_terminated = False
                env.truncated = False
                primitives.set_obs(observed)
                motions = []
                start = time.perf_counter()
                with env.complete_skill():
                    for target in targets:
                        if rotation_scale is None:
                            motion = primitives.move_to(target, gripper=0,
                                step_clip=.025, max_steps=80)
                        else:
                            motion = primitives.move_pose(target, gripper=0,
                                target_pitch=orientation['pitch'], target_yaw=orientation['yaw'],
                                step_clip=.025, max_steps=80,
                                rotation_action_scale=rotation_scale)
                        motions.append({**motion, 'target_xyz': target,
                                        'rotation_action_scale': rotation_scale})
                        if motion['final_dist_m'] > .02:
                            break
                result['arms'].append({'arm': name, 'wall_s': time.perf_counter()-start,
                    'motion_evidence': motions,
                    'all_waypoints_reached': len(motions) == len(targets)
                        and all(m['final_dist_m'] <= .02 for m in motions),
                    'native_predicates_after_label_only': rpc.call('oracle.status', timeout_s=120)})
                (args.output/(pair['case']+'_result.json')).write_text(
                    json.dumps(result, indent=2, default=lambda value: value.tolist())+'\n')
            pairs.append(result)
        finally:
            daemon.stop()
    report = {'scope': 'Original-task same-saved-physics/controller snapshot development probe; no new Pi05 prefix, no training labels.',
        'manifest_sha256': sha(args.manifest), 'script_sha256': sha(__file__),
        'source_report': registration['report'], 'pairs': pairs,
        'new_training_rows': 0, 'runtime_defaults_changed': False,
        'servo_budget_changed': False, 'waypoint_acceptance_m': .02}
    (args.output/'report.json').write_text(
        json.dumps(report, indent=2, default=lambda value: value.tolist())+'\n')
    print(json.dumps({'report': str(args.output/'report.json'), 'sha256': sha(args.output/'report.json'),
                     'results': {p['case']: {a['arm']: a['all_waypoints_reached'] for a in p['arms']} for p in pairs}}))


if __name__ == '__main__':
    main()
