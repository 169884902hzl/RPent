"""Fill unused episode slots inside our existing Slurm GPU allocation.

Reuse its SAM server. Own only the added VLA server and fresh episode workers;
never stop or reconfigure the parent job, SAM, or another project's service.
"""
import argparse
import importlib.util
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from types import SimpleNamespace


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--batch-plan', type=Path, required=True)
    parser.add_argument('--batch-index', type=int, required=True)
    parser.add_argument('--launcher', type=Path, required=True)
    parser.add_argument('--sam3-url', required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--owner-job', required=True)
    parser.add_argument('--startup', action='store_true')
    args = parser.parse_args()
    owner = subprocess.check_output(['scontrol', 'show', 'job', args.owner_job, '-o'], text=True)
    if (os.environ.get('SLURM_JOB_ID') != args.owner_job.split('_')[0]
            or 'JobName=rd-bounded-' not in owner or 'JobState=RUNNING' not in owner
            or f'({os.getuid()})' not in owner or ' NodeList=node02 ' not in owner):
        raise RuntimeError('requires our own existing bounded-skills Slurm allocation')
    batches = json.loads(args.batch_plan.resolve(strict=True).read_bytes())
    batch = batches['batches'][args.batch_index]
    args.output = args.output.resolve()
    args.output.mkdir()
    source = Path(batch['source']).resolve(strict=True)
    sys.path.insert(0, str(source))
    os.chdir(source)
    os.environ.update(PYTHONPATH=str(source), SOURCE_COMMIT=batch['source_commit'],
        LIBERO_TYPE='standard' if batch['domain'] == 'original' else 'pro')
    spec = importlib.util.spec_from_file_location('pinned_shared_launcher', args.launcher.resolve(strict=True))
    launcher = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(launcher)
    assert launcher.digest(batch['manifest']['path']) == batch['manifest']['sha256']
    plan = json.loads(Path(batch['manifest']['path']).read_bytes())
    launcher.bootstrap_source(batch['domain'], evaluation=plan.get('evaluation'))
    from rpent.utils.daemon import ProcessDaemon, pick_free_port
    from rpent.utils.rpc import wait_for_ready
    from rpent.utils.rpc.http_rpc import HttpRpcClient

    port = pick_free_port()
    vla = ProcessDaemon(name='bounded_owned_slot_vla', cmd=[sys.executable, '-m',
        'rpent.robots.components.pi05_vla_server', '--embodiment', 'libero',
        '--transport', 'http', '--host', '127.0.0.1', '--port', str(port), '--parent-watch'],
        log_path=str(args.output/'vla.log'))
    endpoints = {'sam3': HttpRpcClient(args.sam3_url), 'vla': HttpRpcClient(f'http://127.0.0.1:{port}')}
    launch = {'source': str(source), 'source_commit': batch['source_commit'],
        'manifest': batch['manifest'], 'indices': batch['indices'], 'startup': args.startup,
        'owner_allocation': os.environ['SLURM_JOB_ID'],
        'owner_array_task': os.environ.get('SLURM_ARRAY_TASK_ID'),
        'shared_sam3_url': args.sam3_url, 'launcher': str(args.launcher),
        'launcher_sha256': launcher.digest(args.launcher),
        'launch_script_sha256': launcher.digest(Path(__file__)),
        'gpu': os.environ.get('CUDA_VISIBLE_DEVICES'), 'training': False,
        'scope': 'additional isolated workers in our own allocation; parent work remains separate'}
    launcher.dump(args.output/'launch.json', launch)
    sampler = launcher.ResourceSampler(args.output)
    sampler.start()
    try:
        started = time.perf_counter()
        vla.start()
        wait_for_ready(endpoints['vla'], daemon=vla, timeout_s=600)
        wait_for_ready(endpoints['sam3'], timeout_s=60)
        run_args = SimpleNamespace(output=args.output, source=source,
            domain=batch['domain'], manifest=Path(batch['manifest']['path']), startup=args.startup)
        report = launcher.run_level(run_args, plan, batch['indices'], endpoints,
            batches['selected_n'], sampler)
        report['wall_with_added_vla_startup_s'] = time.perf_counter()-started
        launcher.dump(args.output/'summary.json', report)
    finally:
        sampler.close()
        vla.stop()
    if report['worker_errors']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
