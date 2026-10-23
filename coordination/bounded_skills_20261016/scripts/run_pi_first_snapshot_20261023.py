"""Reproduce a retained first attempt and freeze its exact handoff state."""
import argparse
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import pickle
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed


def reference(path):
    path = Path(path)
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def checked(ref):
    path = Path(ref['path'])
    assert reference(path) == ref, str(path)
    return path


def write(path, value):
    with Path(path).open('x') as stream:
        json.dump(value, stream, indent=2, default=lambda x: x.tolist() if hasattr(x, 'tolist') else str(x))


def retry_calls(call, native_done, native_stopped, seed):
    """Continue the same world after failure; never reset or request a choice."""
    attempts = []
    for index in range(2):
        if native_stopped():
            break
        attempts.append(call(index, seed + index*1000000))
        if native_done():
            break
    return attempts


def worker(args, plan):
    row = plan['jobs'][args.worker]
    os.environ['LIBERO_TYPE'] = 'pro' if row['domain'] == 'd2' else 'standard'
    os.environ['LIBERO_CONFIG_PATH'] = str(checked(row['libero_config']).parent)
    sys.path.insert(0, str(args.source))
    # Preserve the frozen import order and solver-state compatibility.
    hooks_path = args.source/'coordination/bounded_skills_20261016/scripts/shared_gpu_episodes_20261019.py'
    spec = importlib.util.spec_from_file_location('pi_only_hooks', hooks_path)
    hooks = importlib.util.module_from_spec(spec); spec.loader.exec_module(hooks)
    hooks.bootstrap_source(row['domain'], evaluation='hybrid_repair')
    hooks.install_d2_restore_compatibility()
    from robots.libero.bounded_hybrid_diagnostic import d2_session, snapshot_digest
    from scripts.probe_bounded_motion import original_session
    from scripts.probe_bounded_hybrid_d2 import SeededPolicy
    from robots.libero.bounded_motion import measured_robot, public_control, settle_osc_hold
    from rpent.skill_package.vla import VLABudget, run_fallback
    from rpent.robots.components.pi05_vla_client import Pi05VLAClient
    from rpent.utils.rpc.http_rpc import HttpRpcClient
    import numpy as np

    case = row['case']; ep = case['episode']; checked(case['bddl'])
    if row['domain'] == 'd2':
        facade, primitives = d2_session(ep, plan['sim_steps'])
    else:
        facade, primitives = original_session(ep['suite'], ep['task'], ep['seed'],
            plan['sim_steps'], rgbd_no_msaa_v1=True)
    started = time.perf_counter()
    try:
        saved = pickle.loads(checked(row['initial_snapshot']).read_bytes())
        physics = saved['physics']
        observed = facade.restore(physics)
        facade._native_success_events = copy.deepcopy(saved.get('private_native_success_events', []))
        primitives.env.last_obs = observed
        flags = saved.get('client_stop_flags', {})
        primitives.env.terminated = bool(flags.get('terminated', False))
        primitives.env.truncated = bool(flags.get('truncated', False))
        primitives.set_obs(observed)
        actual = snapshot_digest(facade.snapshot())
        assert actual == snapshot_digest(physics), 'complete initial state differs'
        assignment = json.loads((args.output/'assignment.json').read_text())
        client = Pi05VLAClient(HttpRpcClient(assignment['vla_url']), embodiment='libero')
        prompt = primitives.env.get_task_language()
        budget = VLABudget(**plan['vla_budget'])
        attempts_path = args.output/'attempts.jsonl'

        def call(index, seed):
            model = SeededPolicy(client, seed, input_ledger=args.output/f'vla_inputs_{index}.jsonl')
            gripper = -1.
            initial = snapshot_digest(facade.snapshot())
            before = primitives.env.execution_budget()['used_sim_steps']
            def predict(text):
                observation = dict(primitives._last_obs)
                observation['task_descriptions'] = text
                observation.setdefault('extra_view_images', None)
                return model.predict(observation, options={'mode': 'eval'})
            def step(action):
                nonlocal gripper
                gripper = float(action[6])
                return public_control(primitives, action)
            def observe():
                robot = measured_robot(primitives)
                return {'completed': bool(primitives.env.terminated), 'outside_region': False,
                    'progress_vector_m': [*robot['eef_xyz_m'], robot['gripper_opening_m']],
                    'evidence': [{'source': 'robot_proprioception_and_native_termination'}]}
            result = run_fallback(prompt=prompt,
                prepare=lambda: {'success': True, 'steps_used': 0, 'mode': 'in_place'},
                predict=predict, step=step, observe=observe,
                native_done=lambda: primitives.env.terminated,
                native_stopped=lambda: primitives.env.terminated or primitives.env.truncated,
                handoff=lambda trace: settle_osc_hold(primitives, gripper) if trace else {'steps_used': 0},
                budget=budget)
            result.update(attempt=index, sampling_seed=seed,
                initial_physics_sha256=initial, final_physics_sha256=snapshot_digest(facade.snapshot()),
                actual_sim_steps=primitives.env.execution_budget()['used_sim_steps']-before,
                native_success=bool(primitives.env.terminated), native_truncated=bool(primitives.env.truncated),
                vla_inference_calls=model.calls, parameters={'mode': 'task', 'preparation': 'in_place',
                    'prompt_style': 'full_task'}, prompt=prompt)
            captured = {'physics': facade.snapshot(),
                'private_native_success_events': copy.deepcopy(facade._native_success_events),
                'client_stop_flags': {'terminated': primitives.env.terminated, 'truncated': primitives.env.truncated},
                'gripper_command': gripper, 'model_visible': False, 'training': False}
            attempt_endpoint = args.output/f'private_attempt{index}.pkl'
            attempt_endpoint.write_bytes(pickle.dumps(captured, protocol=5))
            result['attempt_endpoint'] = reference(attempt_endpoint)
            expected = row['expected_first_endpoint_sha256']
            result['retained_endpoint_matches'] = result['final_physics_sha256'] == expected
            if not result['retained_endpoint_matches']:
                raise RuntimeError('same-seed first attempt differs from retained physical endpoint')
            with attempts_path.open('a') as stream:
                stream.write(json.dumps(result, default=lambda x:x.tolist() if hasattr(x,'tolist') else str(x))+'\n')
            return result

        attempts = [call(0, row['policy_seed'])]
        endpoint = args.output/'private_endpoint.pkl'
        endpoint.write_bytes(pickle.dumps(facade.snapshot(), protocol=5))
        result = {'case': case, 'arm_id': row['arm_id'], 'domain': row['domain'],
            'source_commit': plan['source_commit'], 'entry_sha256': plan['entry_sha256'],
            'success': bool(primitives.env.terminated), 'native_truncated': bool(primitives.env.truncated),
            'sim_steps': sum(a['actual_sim_steps'] for a in attempts),
            'initial_snapshot': row['initial_snapshot'], 'initial_physics_sha256': actual,
            'endpoint': reference(endpoint), 'attempts': len(attempts),
            'attempt_records': reference(attempts_path), 'policy_seed': row['policy_seed'],
            'vla_inference_calls': sum(a['vla_inference_calls'] for a in attempts),
            'recovery_budget': 0, 'attempt_endpoint': attempts[0]['attempt_endpoint'],
            'retained_endpoint_matches': attempts[0]['retained_endpoint_matches'], 'decision_model_calls': 0, 'oracle_choices_used': 0,
            'private_goal_queries_used': 0, 'own_skill_calls': 0, 'SAM_calls': 0,
            'parameters': {'mode': 'task', 'preparation': 'in_place', 'prompt_style': 'full_task'},
            'requested_task_text': prompt, 'vla_budget': plan['vla_budget'],
            'wall_s': time.perf_counter()-started, 'training': False, 'confirmation': False,
            'scope': 'same captured initial state; no reset between attempts; no semantic selector'}
        assert result['sim_steps'] and result['vla_inference_calls'], 'no physical policy call'
        write(args.output/'summary.json', result)
    finally:
        facade.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--worker', type=int)
    parser.add_argument('--episode-concurrency', type=int, default=8)
    args = parser.parse_args()
    args.source = args.source.resolve(strict=True)
    plan = json.loads(args.manifest.read_text())
    assert not plan['training'] and not plan['confirmation'] and plan['recovery_budget'] == 0
    assert reference(Path(__file__))['sha256'] == plan['entry_sha256']
    if args.worker is not None:
        return worker(args, plan)
    sys.path.insert(0, str(args.source))
    os.environ['PYTHONPATH'] = str(args.source)
    os.chdir(args.source)
    from rpent.utils.daemon import ProcessDaemon, pick_free_port
    from rpent.utils.rpc import wait_for_ready
    from rpent.utils.rpc.http_rpc import HttpRpcClient
    args.output.mkdir(parents=True, exist_ok=True)
    port = pick_free_port()
    url = f'http://127.0.0.1:{port}'
    daemon = ProcessDaemon(name='pi_only', cmd=[sys.executable, '-m',
        'rpent.robots.components.pi05_vla_server', '--embodiment', 'libero', '--transport', 'http',
        '--host', '127.0.0.1', '--port', str(port), '--parent-watch'], log_path=str(args.output/'vla.log'))
    def episode(index):
        pointer = args.output/f'closed_{index:03d}.json'
        if pointer.exists():
            checked(json.loads(pointer.read_text()))
            return str(pointer)
        output = args.output/f'case{index:03d}'
        if output.exists():
            output.rename(args.output/f'interrupted_{index:03d}_{time.time_ns()}')
        output.mkdir(exist_ok=False)
        write(output/'assignment.json', {'vla_url': url})
        command = [sys.executable, str(Path(__file__).resolve()), '--source', str(args.source),
            '--manifest', str(args.manifest), '--output', str(output), '--worker', str(index)]
        with (output/'worker.log').open('x') as log:
            subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, check=True)
        write(pointer, reference(output/'summary.json'))
        return str(pointer)
    try:
        daemon.start()
        wait_for_ready(HttpRpcClient(url), daemon=daemon, timeout_s=600)
        with ThreadPoolExecutor(max_workers=args.episode_concurrency) as pool:
            pending = [pool.submit(episode, index) for index in range(len(plan['jobs']))]
            for future in as_completed(pending):
                print(json.dumps({'closed': future.result()}), flush=True)
    finally:
        daemon.stop()


if __name__ == '__main__':
    main()
