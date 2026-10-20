"""Capture public prompt binding after recovery, before any VLA inference."""

import argparse
import hashlib
import importlib
import importlib.util
import json
import os
import sys
from dataclasses import asdict
from pathlib import Path


class Captured(Exception):
    def __init__(self, report):
        self.report = report


def ref(path):
    path = Path(path).resolve(strict=True)
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--failed-worker', type=Path, required=True)
    parser.add_argument('--parent-output', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--preflight', action='store_true')
    args = parser.parse_args()
    sys.path.insert(0, str(args.source.resolve(strict=True)))
    os.environ['LIBERO_TYPE'] = 'standard'
    importlib.import_module('robots.libero.env_server')
    from scripts import probe_bounded_hybrid_repair as evaluator

    worker = json.loads(args.failed_worker.read_bytes())
    plan = {'evaluation': 'hybrid_repair', 'source_commit': worker['source_commit'],
        'cases': [worker['case']], 'training': False, 'confirmation': False}
    evaluator.validate_plan(plan)
    registry = args.output/'plan.json'
    if args.preflight:
        args.output.mkdir(parents=True)
        plan.update(failed_worker=ref(args.failed_worker), script=ref(__file__),
            source=str(args.source.resolve()), training=False,
            scope='public binding capture only; no VLA predictions or policy labels')
        registry.write_text(json.dumps(plan, indent=2)+'\n')
        print(json.dumps({'preflight': 'passed', 'plan': ref(registry)}))
        return 0
    saved = json.loads(registry.read_bytes())
    assert saved['script'] == ref(__file__) and saved['failed_worker'] == ref(args.failed_worker)
    hooks_path = args.source/'coordination/bounded_skills_20261016/scripts/shared_gpu_episodes_20261019.py'
    spec = importlib.util.spec_from_file_location('binding_capture_hooks', hooks_path)
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
    from robots.libero.bounded_skills import MeasuredSkillAdapter
    from robots.libero.v5_subtasks import pi05_instance_description, SubtaskBindingError

    original = MeasuredSkillAdapter.call_vla

    def capture(adapter, parameters):
        entity = adapter.scene.entities[parameters['anchor_id']]
        report = {'parameters': parameters, 'selected': asdict(entity),
            'entities': [asdict(e) for e in adapter.scene.entities.values()],
            'public_anchors': adapter.anchors(), 'source_commit': saved['source_commit'],
            'capture_step': adapter.ex.toolkit._state.latest_step,
            'execution_budget': adapter.p.env.execution_budget(),
            'training': False, 'confirmation': False, 'policy_success': None}
        try:
            report['prompt_description'] = pi05_instance_description(
                entity, adapter.scene.entities, adapter.scene.view_axes)
            report['binding_error'] = None
        except SubtaskBindingError as exc:
            report['binding_error'] = str(exc)
        raise Captured(report)

    MeasuredSkillAdapter.call_vla = capture
    try:
        endpoints = {k: HttpRpcClient(assignment[k+'_url']) for k in ('sam3', 'vla')}
        evaluator.evaluate_case(worker['case'], endpoints, args.output/'episode', plan)
    except Captured as completed:
        completed.report['plan'] = ref(registry)
        (args.output/'public_binding.json').write_text(json.dumps(completed.report, indent=2)+'\n')
        print(json.dumps(completed.report))
        return 0
    finally:
        MeasuredSkillAdapter.call_vla = original
    raise RuntimeError('no VLA call reached the public binding boundary')


if __name__ == '__main__':
    raise SystemExit(main())
