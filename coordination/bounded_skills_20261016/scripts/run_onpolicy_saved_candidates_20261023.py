"""Share services while each frozen query uses its own original source/process."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import time


def ref(path):
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x') as stream:
        json.dump(value, stream, indent=2)


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def worker(args, plan):
    job = plan['jobs'][args.worker]
    source = Path(job['execution_source'])
    sys.path.insert(0, str(source))
    os.chdir(source)
    os.environ.update(LIBERO_TYPE='standard', MUJOCO_GL='egl', PYOPENGL_PLATFORM='egl',
        LIBERO_GRASP_DIAGNOSTIC_MODELS=str(args.output/'private_grasp_models'))
    helper = load_module('query_source_hooks', source/'coordination/bounded_skills_20261016/scripts/shared_gpu_episodes_20261019.py')
    helper.bootstrap_source('d2')
    helper.install_d2_restore_compatibility()
    from scripts import probe_bounded_hybrid_d2 as probe
    from scripts.probe_bounded_hybrid_repair import constructed_original_start
    from rpent.utils.rpc.http_rpc import HttpRpcClient

    producer = plan['measurement_producer']
    assert ref(Path(producer['path'])) == producer
    measure = load_module('frozen_candidate_measurement', Path(producer['path']))
    assignment = json.loads((args.output/'assignment.json').read_bytes())
    endpoints = {key: HttpRpcClient(assignment[key+'_url']) for key in ('sam3', 'vla')}
    row = job['query']
    constructed = constructed_original_start(job['case'], plan)
    episode = args.output/'episode'
    episode.mkdir(exist_ok=True)
    trials = []
    with probe.runtime(job['case'], endpoints, episode, domain='original',
            constructed_start=constructed) as (facade, adapter, policy, timings):
        for repeat in range(1 if args.startup else 3):
            target = episode/f'trial{repeat}'
            seed = job['noise_seed_base']+repeat*1000
            summaries = [target/'summary.json', *episode.glob(f'trial{repeat}_attempt*/summary.json')]
            prior = next((p for p in summaries if p.exists()), None)
            if prior is not None:
                result = json.loads(prior.read_bytes())
                assert result['seed'] == seed and result['binding'] == row['binding']
            else:
                if target.exists():
                    attempt = 1
                    while (episode/f'trial{repeat}_attempt{attempt}').exists():
                        attempt += 1
                    target = episode/f'trial{repeat}_attempt{attempt}'
                result = measure.evaluate_candidate_at_saved_state(row, probe, facade, adapter,
                    policy, target, seed)
                prior = target/'summary.json'
                result = json.loads(prior.read_bytes())
            trials.append({'result': result, 'summary': ref(prior)})
    report = {'query_id': row['query_id'], 'record_id': row['record_id'],
        'binding': row['binding'], 'case': job['case'], 'candidate': row['candidate'],
        'status': 'startup_physical' if args.startup else 'physical_result',
        'trials': trials, 'execution_source': str(source), 'measurement_producer': producer,
        'training_admission': False, 'confirmation': False, 'PRO': False, 'D2': False}
    if args.startup and not any(t['result']['sim_steps'] for t in trials):
        raise RuntimeError('selected-candidate startup did not execute physics')
    write(args.output/'summary.json', report)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--worker', type=int)
    parser.add_argument('--startup', action='store_true')
    args = parser.parse_args()
    plan = json.loads(args.manifest.read_bytes())
    assert plan['evaluation_only'] and not plan['training'] and not plan['PRO'] and not plan['D2']
    config = Path(os.environ['LIBERO_CONFIG_PATH'])/'config.yaml'
    assert ref(config) == plan['libero_config']
    if args.worker is not None:
        return worker(args, plan)
    args.output.mkdir(parents=True, exist_ok=True)
    service_source = Path(plan['jobs'][0]['execution_source'])
    sys.path.insert(0, str(service_source))
    os.chdir(service_source)
    helper = load_module('query_service_hooks', service_source/'coordination/bounded_skills_20261016/scripts/shared_gpu_episodes_20261019.py')
    helper.bootstrap_source('d2')
    from scripts.probe_bounded_feasibility import services
    from types import SimpleNamespace

    service_output = args.output/f'services_{time.time_ns()}'
    service_output.mkdir()
    service_args = SimpleNamespace(source=service_source, output=service_output,
        sam3_entry=Path(plan['sam_entry']['path']))
    assert ref(service_args.sam3_entry) == plan['sam_entry']
    with helper.owned_services(service_args, services, vla=True) as endpoints:
        assignment = {key+'_url': value._base_url for key, value in endpoints.items()}
        startup = args.output/'physical_startup'
        if not (startup/'summary.json').exists():
            if startup.exists():
                startup = args.output/f'physical_startup_attempt{time.time_ns()}'
            startup.mkdir()
            write(startup/'assignment.json', assignment)
            command = [sys.executable, str(Path(__file__).resolve()), '--manifest', str(args.manifest),
                '--output', str(startup), '--worker', '0', '--startup']
            with (startup/'worker.log').open('a') as stream:
                subprocess.run(command, check=True, stdout=stream, stderr=subprocess.STDOUT)
        if args.startup:
            return

        def run(index):
            closed = args.output/f'closed_{index:03d}.json'
            if closed.exists():
                return
            target = args.output/f'query{index:03d}'
            target.mkdir(exist_ok=True)
            assignment_path = target/'assignment.json'
            if assignment_path.exists():
                (target/f'assignment_previous_{time.time_ns()}.json').write_bytes(assignment_path.read_bytes())
                assignment_path.write_text(json.dumps(assignment))
            else:
                write(assignment_path, assignment)
            command = [sys.executable, str(Path(__file__).resolve()), '--manifest', str(args.manifest),
                '--output', str(target), '--worker', str(index)]
            with (target/'worker.log').open('a') as stream:
                subprocess.run(command, check=True, stdout=stream, stderr=subprocess.STDOUT)
            write(closed, {'summary': str(target/'summary.json'),
                'sha256': ref(target/'summary.json')['sha256']})
            print(json.dumps({'closed_query': index}), flush=True)
        with ThreadPoolExecutor(max_workers=8) as pool:
            list(pool.map(run, range(len(plan['jobs']))))


if __name__ == '__main__':
    main()
