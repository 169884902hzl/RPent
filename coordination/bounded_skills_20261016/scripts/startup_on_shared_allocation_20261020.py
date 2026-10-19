# Copyright 2026 Zhilun Hu.
# SPDX-License-Identifier: Apache-2.0
"""Run registered workers with an owned allocation's existing model services."""

import argparse
import hashlib
import importlib.util
import json
import os
import sys
import time
from pathlib import Path
from types import SimpleNamespace


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--preparation', type=Path, required=True)
    parser.add_argument('--parent-output', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--full-batch-index', type=int,
        help='Run this registered full batch on the owned allocation instead of a startup')
    args = parser.parse_args()
    prep = json.loads((args.preparation/'preparation.json').read_bytes())
    assert all(row['exit_code'] == 0 for row in prep['preflights'])
    parent = json.loads((args.parent_output/'launch.json').read_bytes())
    assert os.environ['SLURM_JOB_ID'] == parent['slurm_job_id']
    assert os.environ['CUDA_VISIBLE_DEVICES'] == parent['cuda_visible_devices']
    assert not parent['startup'] and parent['domain'] == 'original'
    old_assignment = json.loads(next(args.parent_output.glob('N*/*/assignment.json')).read_bytes())
    startup = args.full_batch_index is None
    plan_name = 'startup_plan.json' if startup else 'batch_plan.json'
    batch_index = 0 if startup else args.full_batch_index
    batch_plan = json.loads((args.preparation/plan_name).read_bytes())
    batch = batch_plan['batches'][batch_index]
    source = Path(batch['source']).resolve(strict=True)
    sys.path.insert(0, str(source))
    os.environ['LIBERO_TYPE'] = 'standard'
    launcher = Path(prep['launcher']['path'])
    assert hashlib.sha256(launcher.read_bytes()).hexdigest() == prep['launcher']['sha256']
    spec = importlib.util.spec_from_file_location('shared_startup_launcher', launcher)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.bootstrap_source('original', evaluation='hybrid_repair')
    from rpent.utils.rpc.http_rpc import HttpRpcClient
    from scripts.probe_bounded_hybrid_repair import validate_plan

    manifest = Path(batch['manifest']['path'])
    assert hashlib.sha256(manifest.read_bytes()).hexdigest() == batch['manifest']['sha256']
    plan = json.loads(manifest.read_bytes())
    validate_plan(plan)
    os.environ['SOURCE_COMMIT'] = plan['source_commit']
    args.output.mkdir(parents=True)
    started = time.time()
    launch = {'source': str(source), 'source_commit': plan['source_commit'],
        'launcher': prep['launcher'], 'manifest': batch['manifest'], 'indices': batch['indices'],
        'levels': [len(batch['indices'])], 'domain': 'original', 'startup': startup,
        'registered_batch_index': batch_index,
        'slurm_job_id': os.environ['SLURM_JOB_ID'], 'slurm_step_id': os.environ['SLURM_STEP_ID'],
        'cuda_visible_devices': os.environ['CUDA_VISIBLE_DEVICES'],
        'existing_services_from': str(args.parent_output), 'model_server_source_commit': parent['source_commit'],
        'sam_services_started': 0, 'vla_services_started': 0, 'additional_gpu_allocations': 0,
        'training': False, 'scope': 'owned allocation reuse; timings overlap the parent and are not an independent throughput comparison'}
    module.dump(args.output/'launch.json', launch)
    overlap = args.parent_output/('startup_overlap_'+os.environ['SLURM_STEP_ID']+'.json')
    module.dump(overlap, {'startup_output': str(args.output), 'start_time_s': started,
        'planned_extra_workers': len(batch['indices']), 'separate_episode_processes': True})
    endpoints = {'sam3': HttpRpcClient(old_assignment['sam3_url']),
        'vla': HttpRpcClient(old_assignment['vla_url'])}
    run_args = SimpleNamespace(output=args.output, source=source, manifest=manifest,
        domain='original', startup=startup)
    sampler = module.ResourceSampler(args.output)
    sampler.start()
    try:
        report = module.run_level(run_args, plan, batch['indices'], endpoints, len(batch['indices']), sampler)
    finally:
        sampler.close()
    module.dump(args.output/'summary.json', report)
    proof_name = 'startup_proof.json' if startup else 'full_reuse_completion.json'
    module.dump(args.output/proof_name, {**launch, 'wall_s': time.time()-started,
        'worker_errors': report['worker_errors'],
        'physical_requests': [str(p) for p in args.output.glob('N*/*/**/first_physical*_request.json')]})
    return 0 if report['worker_errors'] == 0 else 1


if __name__ == '__main__':
    raise SystemExit(main())
