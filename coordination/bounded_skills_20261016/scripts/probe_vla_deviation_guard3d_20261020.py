"""Measure the deviation handoff with explicit, unscored OSC fault injection.

The first block is genuine pi0.5. Subsequent blocks move away from the measured
source with a fixed small OSC delta. These artifacts never provide policy
success labels, training examples, history, memory, or confirmation evidence.
"""

import argparse
import copy
import hashlib
import importlib
import importlib.util
import json
import os
import sys
from pathlib import Path


def reference(path):
    path = Path(path).resolve(strict=True)
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


class GuardMeasured(Exception):
    def __init__(self, report):
        self.report = report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--commit', required=True)
    parser.add_argument('--original-manifest', type=Path, required=True)
    parser.add_argument('--case-name', required=True)
    parser.add_argument('--parent-output', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--preflight', action='store_true')
    args = parser.parse_args()
    source = args.source.resolve(strict=True)
    sys.path.insert(0, str(source))
    os.environ['LIBERO_TYPE'] = 'standard'
    os.environ['SOURCE_COMMIT'] = args.commit
    importlib.import_module('robots.libero.env_server')
    import numpy as np

    from robots.libero.bounded_motion import measured_robot
    from rpent.utils.rpc.http_rpc import HttpRpcClient
    from scripts import probe_bounded_hybrid_repair as evaluator

    registry = args.output/'plan.json'
    if args.preflight:
        old = json.loads(args.original_manifest.read_bytes())
        case = copy.deepcopy(next(c for c in old['cases'] if c['name'] == args.case_name))
        assert case['diagnostic']['domain'] == 'original'
        assert case['diagnostic']['subtask_mode'] == 'pick'
        case['diagnostic']['budget'] = {'blocks': 44, 'no_progress_blocks': None,
            'controls_per_check': 1, 'minimum_progress_m': .005, 'max_controls': 220}
        plan = {**old, 'source_commit': args.commit, 'cases': [case], 'training': False,
            'confirmation': False, 'source': str(source), 'parent_output': str(args.parent_output.resolve()),
            'original_manifest': reference(args.original_manifest), 'probe_script': reference(__file__),
            'launcher_hooks': reference(source/'coordination/bounded_skills_20261016/scripts/shared_gpu_episodes_20261019.py'),
            'fault_injection': {'after_real_blocks': 1, 'osc_translation_norm': .4,
                'direction': '3d_away_from_current_public_source', 'rotation': 'zero',
                'gripper': 'retain_last_command'}, 'admission': 'exclude_all_probe_artifacts_from_training_history_memory_and_policy_scores'}
        evaluator.validate_plan(plan)
        args.output.mkdir(parents=True)
        registry.write_text(json.dumps(plan, indent=2)+'\n')
        print(json.dumps({'preflight': 'passed', 'plan': reference(registry)}))
        return 0
    plan = json.loads(registry.read_bytes())
    assert plan['source'] == str(source) and plan['source_commit'] == args.commit
    for key in ('original_manifest', 'probe_script', 'launcher_hooks'):
        assert reference(plan[key]['path']) == plan[key]
    hook_spec = importlib.util.spec_from_file_location('frozen_shared_hooks', plan['launcher_hooks']['path'])
    hooks = importlib.util.module_from_spec(hook_spec)
    hook_spec.loader.exec_module(hooks)
    hooks.install_d2_restore_compatibility()
    hooks.install_d2_spawn_bootstrap()
    hooks.install_d2_request_compatibility(evaluator.probe)
    parent = json.loads((args.parent_output/'launch.json').read_bytes())
    assert parent['slurm_job_id'] == os.environ['SLURM_JOB_ID']
    assert parent['cuda_visible_devices'] == os.environ['CUDA_VISIBLE_DEVICES']
    assignment = json.loads(next(args.parent_output.glob('N*/*/assignment.json')).read_bytes())
    endpoints = {key: HttpRpcClient(assignment[key+'_url']) for key in ('sam3', 'vla')}
    original_trial = evaluator.run_trial

    def trial(facade, adapter, policy, timings, spec, method, seed, output, request, **kwargs):
        if method != 'call_vla':
            return original_trial(facade, adapter, policy, timings, spec, method, seed, output, request, **kwargs)
        original_predict = adapter.p.model.predict
        adapter_type = type(adapter)
        original_call = adapter_type.call_vla
        fault = {'predict_calls': 0, 'real_pi_blocks': 0, 'injected_blocks': 0}

        def call(current_adapter, parameters):
            fault['initial_source_xyz_m'] = list(current_adapter.scene.entities[parameters['anchor_id']].xyz)
            return original_call(current_adapter, parameters)

        def predict(*values, **options):
            fault['predict_calls'] += 1
            if fault['predict_calls'] == 1:
                actions = np.asarray(original_predict(*values, **options))
                fault['real_pi_blocks'] = 1
                fault['real_block_controls'] = len(actions)
                return actions
            current = measured_robot(adapter.p)
            direction = np.asarray(current['eef_xyz_m'])-fault['initial_source_xyz_m']
            norm = float(np.linalg.norm(direction))
            if norm <= 1e-9:
                raise ValueError('registered source coincides with EEF in this fault probe')
            command = np.r_[direction/norm*plan['fault_injection']['osc_translation_norm'],
                np.zeros(3), adapter.gripper_command]
            fault['injected_blocks'] += 1
            return np.repeat(command[None], fault['real_block_controls'], axis=0)

        adapter_type.call_vla, adapter.p.model.predict = call, predict
        try:
            result, endpoint = original_trial(facade, adapter, policy, timings, spec,
                method, seed, output, request, **kwargs)
        finally:
            adapter_type.call_vla, adapter.p.model.predict = original_call, original_predict
        execution = next(detail['execution'] for line in Path(result['choices']['path']).open()
            for detail in json.loads(line)['execution_details']
            if 'skill_stop_reason' in detail.get('execution', {}))
        evaluator.probe.restore_checkpoint(facade, adapter, policy, endpoint)
        next_request = adapter.request(k=1)
        reason = execution['skill_stop_reason']
        handoff = execution.get('handoff', {})
        distances = [c['progress_vector_m'][-1] for c in execution.get('checks', [])]
        report = {'version': 'call-vla-deviation-interface/2', 'source_commit': args.commit,
            'plan': reference(registry), 'fault_injection': fault,
            'guard_passed': reason == 'left_target_region' and handoff.get('completed') is True,
            'stop_reason': reason, 'max_public_distance_m': max(distances),
            'handoff': {k: handoff.get(k) for k in ('completed', 'settled', 'steps_used', 'reason')},
            'first_next_request_generated': bool(next_request['candidates']),
            'trial': reference(output/'summary.json'), 'policy_success': None,
            'training': False, 'confirmation': False, 'model_visible': False,
            'scope': 'one real pi block followed by explicit OSC fault injection; interface check only'}
        raise GuardMeasured(report)

    evaluator.run_trial = trial
    try:
        evaluator.evaluate_case(plan['cases'][0], endpoints, args.output/'episode', plan)
    except GuardMeasured as completed:
        (args.output/'interface_summary.json').write_text(json.dumps(completed.report, indent=2)+'\n')
        print(json.dumps(completed.report))
        return 0 if completed.report['guard_passed'] else 1
    finally:
        evaluator.run_trial = original_trial
    raise RuntimeError('no delegated branch reached the registered deviation probe')


if __name__ == '__main__':
    raise SystemExit(main())
