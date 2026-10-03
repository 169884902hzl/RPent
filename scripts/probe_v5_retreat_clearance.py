"""Compare retreat paths from one restored original-task physical state."""

import argparse
import copy
import hashlib
import json
from pathlib import Path
import sys
import time


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text())
    from harness_v5_eval import run_episode
    from robots.libero.v5_runtime import V5Executor
    from rpent.utils.daemon import ProcessDaemon, pick_free_port
    from rpent.utils.rpc import wait_for_ready
    from rpent.utils.rpc.http_rpc import HttpRpcClient

    args.output.mkdir(parents=True, exist_ok=False)
    daemons, endpoints, results = [], {}, []
    original_execute, original_retreat = V5Executor.execute, V5Executor.retreat
    active_action = None
    active_case = None
    recorded = False

    def execute(executor, action, card=None):
        nonlocal active_action
        active_action = action
        try:
            return original_execute(executor, action, card)
        finally:
            active_action = None

    def retreat(executor):
        nonlocal recorded
        if recorded or active_action is None or active_action.tool != 'place':
            return original_retreat(executor)
        recorded = True
        rpc = executor.p.env._client
        snapshot = rpc.call('oracle.snapshot', timeout_s=120)
        before = rpc.call('oracle.status', timeout_s=120)
        cached = copy.deepcopy(executor.p._last_obs)
        flags = (executor.p.env._native_terminated, executor.p.env.truncated,
                 executor.toolkit._solved)
        prior_motion = copy.deepcopy(executor.motion_evidence)
        initial_eef = executor.p._last_obs_eef_pos.copy()
        snapshot_path = args.output / (active_case['name'] + '_before_retreat.json')
        snapshot_path.write_text(json.dumps(snapshot, default=lambda x: x.tolist()) + '\n')

        def restore():
            # oracle.restore checks physics and restores controller/gripper
            # commands and counters. Reuse the exact same observed scene.
            rpc.call('oracle.restore', args=[snapshot], timeout_s=120)
            executor.p.env.last_obs = copy.deepcopy(cached)
            executor.p.set_obs(copy.deepcopy(cached))
            executor.p.env._native_terminated, executor.p.env.truncated, executor.toolkit._solved = flags

        pair = {'case': active_case['name'], 'action': active_action.text(),
                'snapshot': {'path': str(snapshot_path), 'sha256': sha(snapshot_path)},
                'initial_eef': initial_eef.tolist(), 'native_predicates_before_label_only': before,
                'view_pose': executor.view_retreat_pose.tolist(), 'arms': []}
        for name, enabled in (('direct_control', False), ('measured_clearance', True)):
            restore()
            executor.retreat_clearance_v1 = enabled
            executor.motion_evidence = []
            start = time.perf_counter()
            error = None
            try:
                original_retreat(executor)
            except Exception as failure:
                error = repr(failure)
            pair['arms'].append({
                'arm': name, 'error': error, 'wall_s': time.perf_counter() - start,
                'motion_evidence': copy.deepcopy(executor.motion_evidence),
                'final_eef': executor.p._last_obs_eef_pos.tolist(),
                'native_predicates_after_label_only': rpc.call('oracle.status', timeout_s=120),
            })
        results.append(pair)
        (args.output / 'pairs.json').write_text(json.dumps(results, indent=2) + '\n')
        # Continue only the declared patch arm. This is a development probe;
        # it never chooses an arm based on the private predicate outcome.
        restore()
        executor.retreat_clearance_v1 = True
        executor.motion_evidence = prior_motion
        return original_retreat(executor)

    V5Executor.execute, V5Executor.retreat = execute, retreat
    episodes = []
    try:
        for name, module, extra in (
            ('sam3', 'robots.libero.v5_sam3_server', []),
            ('vla', 'rpent.robots.components.pi05_vla_server', ['--embodiment', 'libero']),
        ):
            port = pick_free_port()
            daemon = ProcessDaemon(name='retreat_clearance_' + name,
                cmd=[sys.executable, '-m', module, *extra, '--transport', 'http',
                     '--host', '127.0.0.1', '--port', str(port), '--parent-watch'],
                log_path=str(args.output / ('shared_' + name + '.log')))
            daemons.append(daemon)
            endpoints[name] = f'http://127.0.0.1:{port}'
            daemon.start()
        for name, daemon in zip(('sam3', 'vla'), daemons):
            wait_for_ready(HttpRpcClient(endpoints[name]), daemon=daemon, timeout_s=300)
        for case in manifest['cases']:
            active_case, recorded = case, False
            config_path = Path(case['config'])
            if sha(config_path) != case['config_sha256']:
                raise ValueError('registered original config changed')
            cfg = json.loads(config_path.read_text())
            if (cfg['libero_type'] != 'standard' or cfg['provider'] != 'oracle'
                    or cfg['suite'] != 'libero_goal' or cfg['task'] != 2
                    or cfg['seed'] not in (12, 13)):
                raise ValueError('only the registered original cabinet-top placement is diagnosed')
            cfg.update(choice_package=Path(manifest['choice_package']),
                       sam3_endpoint=endpoints['sam3'], vla_endpoint=endpoints['vla'],
                       output_dir=args.output / case['name'], max_decisions=3,
                       motion_trace_v1=True, retreat_clearance_v1=True,
                       native_termination_diagnostic=True)
            try:
                result = run_episode(argparse.Namespace(**cfg))
            except Exception as failure:
                path = cfg['output_dir'] / 'result.json'
                result = json.loads(path.read_text()) if path.exists() else {'error': repr(failure)}
            episodes.append({'case': case, 'result': result, 'paired_retreat_recorded': recorded})
    finally:
        V5Executor.execute, V5Executor.retreat = original_execute, original_retreat
        for daemon in reversed(daemons):
            daemon.stop()
        report = {'scope': 'Original-task development physics probe, not model performance or training labels. Within each pair the simulator/controller/cache state is restored; the original Pi05 prefix is generated afresh.',
                  'manifest_sha256': sha(args.manifest), 'script_sha256': sha(__file__),
                  'pairs': results, 'episodes': episodes, 'new_training_rows': 0,
                  'servo_budget_changed': False, 'waypoint_threshold_m': .02}
        (args.output / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
    if len(results) != len(manifest['cases']):
        raise RuntimeError('not all original cases reached the registered retreat; inspect preserved evidence')


if __name__ == '__main__':
    main()
