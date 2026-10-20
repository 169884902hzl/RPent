"""Continue a registered VLA endpoint with bounded skills, without another VLA.

This is a D2 development diagnostic. Its private labels and saved states never
contribute to training, history, memory, or confirmation results.
"""

import argparse
import hashlib
import importlib
import importlib.util
import json
import os
import pickle
import sys
from pathlib import Path


def reference(path):
    path = Path(path).resolve(strict=True)
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--commit', required=True)
    parser.add_argument('--worker', type=Path, required=True)
    parser.add_argument('--parent-output', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--preflight', action='store_true')
    args = parser.parse_args()
    source = args.source.resolve(strict=True)
    sys.path.insert(0, str(source))
    os.environ.update(LIBERO_TYPE='pro', SOURCE_COMMIT=args.commit)
    importlib.import_module('robots.libero.env_server')
    from scripts import probe_bounded_hybrid_repair as evaluator

    worker_path = args.worker/'worker_summary.json'
    worker = json.loads(worker_path.read_bytes())
    assert worker['exit_code'] == 0 and worker['source_commit'] == args.commit
    result = worker['result']
    assert result['training'] is False and result['confirmation'] is False
    trial = result['trials'][0]
    assert trial['method'] == 'call_vla' and trial['success'] is True
    assert reference(trial['endpoint']['path']) == {k: trial['endpoint'][k] for k in ('path', 'sha256')}
    registry = args.output/'plan.json'
    hooks_path = source/'coordination/bounded_skills_20261016/scripts/shared_gpu_episodes_20261019.py'
    if args.preflight:
        args.output.mkdir(parents=True)
        plan = {'source': str(source), 'source_commit': args.commit,
            'worker': reference(worker_path), 'endpoint': trial['endpoint'],
            'hooks': reference(hooks_path), 'script': reference(__file__),
            'decision_limit': 4, 'call_vla_enabled': False, 'training': False,
            'confirmation': False, 'scope': 'D2 saved endpoint bounded continuation only'}
        registry.write_text(json.dumps(plan, indent=2)+'\n')
        print(json.dumps({'preflight': 'passed', 'plan': reference(registry)}))
        return 0
    plan = json.loads(registry.read_bytes())
    assert plan['source_commit'] == args.commit and plan['source'] == str(source)
    for key in ('worker', 'hooks', 'script'):
        assert reference(plan[key]['path']) == plan[key]
    spec = importlib.util.spec_from_file_location('frozen_shared_hooks', hooks_path)
    hooks = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(hooks)
    hooks.install_d2_restore_compatibility()
    hooks.install_d2_spawn_bootstrap()
    hooks.install_d2_request_compatibility(evaluator.probe)
    parent = json.loads((args.parent_output/'launch.json').read_bytes())
    assert parent['slurm_job_id'] == os.environ['SLURM_JOB_ID']
    assert parent['cuda_visible_devices'] == os.environ['CUDA_VISIBLE_DEVICES']
    assignment = json.loads(next(args.parent_output.glob('N*/*/assignment.json')).read_bytes())
    from rpent.utils.rpc.http_rpc import HttpRpcClient

    endpoints = {k: HttpRpcClient(assignment[k+'_url']) for k in ('sam3', 'vla')}
    with evaluator.probe.runtime(worker['case'], endpoints, args.output/'episode') as (facade, adapter, policy, timings):
        checkpoint = pickle.loads(Path(plan['endpoint']['path']).read_bytes())
        evaluator.probe.restore_checkpoint(facade, adapter, policy, checkpoint)
        subtasks, _ = evaluator.probe.split_subtasks(facade.goal_status()['goals'], adapter.ex.instruction)
        position = next(i for i, task in enumerate(subtasks) if task['id'] == trial['subtask']['id'])
        next_task = subtasks[position+1]
        request = adapter.request(k=4)
        row, _ = evaluator.run_trial(facade, adapter, policy, timings, next_task, 'self',
            trial['trial_seed'], args.output/'continuation', request,
            decision_limit=plan['decision_limit'])
        report = {'plan': reference(registry), 'source_commit': args.commit,
            'subtask': next_task, 'trial': row, 'native_success': facade.goal_status()['done'],
            'training': False, 'confirmation': False, 'scope': plan['scope']}
        (args.output/'summary.json').write_text(json.dumps(report, indent=2)+'\n')
        print(json.dumps({k: row[k] for k in ('success', 'reason', 'sim_steps', 'decisions')}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
