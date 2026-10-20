"""N1 fixed-state latency baseline; isolated episode processes and owned services."""
import argparse
import hashlib
import importlib.util
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from types import SimpleNamespace


def write(path, value):
    with Path(path).open('x') as stream:
        json.dump(value, stream, indent=2)
        stream.write('\n')


def module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def worker(args, plan):
    sys.path.insert(0, str(args.source))
    hooks = module(args.source/'coordination/bounded_skills_20261016/scripts/shared_gpu_episodes_20261019.py', 'latency_hooks')
    row = plan['cases'][args.worker]
    os.environ['LIBERO_TYPE'] = 'standard' if row['domain'] == 'original' else 'pro'
    os.environ['LIBERO_GRASP_DIAGNOSTIC_MODELS'] = str(args.output/'private_grasp_models')
    hooks.bootstrap_source(row['domain'], evaluation='hybrid_repair')
    hooks.install_d2_restore_compatibility()
    from scripts import probe_bounded_hybrid_d2 as probe
    from robots.libero.bounded_timing import EpisodeTimings
    from robots.libero.bounded_skills import MeasuredSkillAdapter
    from rpent.utils.rpc.http_rpc import HttpRpcClient

    hooks.install_d2_request_compatibility(probe)
    runtime_options = plan.get('runtime_options', {})
    if runtime_options:
        original_runtime = probe.runtime
        from contextlib import contextmanager

        @contextmanager
        def configured_runtime(*positional, **kwargs):
            with original_runtime(*positional, **kwargs) as runtime:
                for key, value in runtime_options.items():
                    setattr(runtime[1], key, value)
                yield runtime
        probe.runtime = configured_runtime
        original_restore = probe.restore_checkpoint

        def configured_restore(facade, adapter, policy, saved):
            result = original_restore(facade, adapter, policy, saved)
            for key, value in runtime_options.items():
                setattr(adapter, key, value)
            return result
        probe.restore_checkpoint = configured_restore
    assignment = json.loads((args.output/'assignment.json').read_bytes())
    endpoints = {key: HttpRpcClient(assignment[key+'_url']) for key in ('sam3', 'vla')}
    rpc = endpoints['sam3']
    original_call = rpc.call
    with (args.output/'sam_calls.jsonl').open('x') as ledger:
        def call(method, args=(), kwargs=None, **options):
            started = time.perf_counter()
            try:
                return original_call(method, args=args, kwargs=kwargs, **options)
            finally:
                kwargs = kwargs or {}
                ledger.write(json.dumps({'method': method, 'prompt': kwargs.get('text_prompt'),
                    'image_sha256': __import__('hashlib').sha256(kwargs.get('image_base64', '').encode()).hexdigest(),
                    'wall_s': time.perf_counter()-started})+'\n')
                ledger.flush()
        rpc.call = call
        old_candidate = MeasuredSkillAdapter._candidate
        candidate_times = []
        def candidate(self, skill, parameters, **options):
            started = time.perf_counter()
            try:
                return old_candidate(self, skill, parameters, **options)
            finally:
                candidate_times.append({'skill':skill,
                    'stage':getattr(self,'_latency_stage','unspecified'),
                    'wall_s':time.perf_counter()-started})
        MeasuredSkillAdapter._candidate = candidate
        try:
            if row['runner'] == 'vla_continuation':
                from scripts import probe_bounded_hybrid_repair as repair
                result = repair.evaluate_case(row['case'], endpoints, args.output/'episode',
                    {'evaluation':'hybrid_repair', 'training':False, 'confirmation':False,
                     'source_commit':plan['baseline_commit'], 'cases':[row['case']]}, startup=args.startup)
            else:
                (args.output/'episode').mkdir()
                result = bounded_episode(args, row, endpoints, probe)
            result['registered_runtime_options'] = runtime_options
            write(args.output/'summary.json', result)
        finally:
            write(args.output/'candidate_times.json', candidate_times)
    return 0


def bounded_episode(args, row, endpoints, probe):
    from rpent.skill_package.contract import VERSION
    from robots.libero.bounded_oracle import NoPublicOption
    loops = []
    stop_reason = None
    started = time.perf_counter()
    case = row['case']
    with probe.runtime(case, endpoints, args.output/'episode', domain=row['domain']) as (facade, adapter, policy, timings):
        adapter.allow_vla = False
        initial_physics_sha256 = probe.snapshot_digest(facade.snapshot())
        for index in range(160):
            if adapter.p.env.terminated or adapter.p.env.truncated:
                break
            begin = time.perf_counter()
            event = len(timings.events)
            adapter._latency_stage = 'catalog'
            with timings.measure('planning.request'):
                request = adapter.request(k=4)
            request_s = time.perf_counter()-begin
            adapter._latency_stage = 'oracle'
            try:
                with timings.measure('decision.oracle'):
                    decision = policy.choose(request)
            except NoPublicOption as exc:
                elapsed = time.perf_counter()-begin
                loops.append({'index': index, 'request_s': request_s,
                    'decision_s': elapsed-request_s, 'execution_s': 0., 'loop_s': elapsed,
                    'request': request, 'decision': None, 'receipts': [],
                    'stop_reason': 'no_public_option', 'message': str(exc),
                    'timings': timings.summary(elapsed, start_event=event)})
                with (args.output/'loops.jsonl').open('a') as stream:
                    stream.write(json.dumps(loops[-1])+'\n')
                stop_reason = 'no_public_option'
                break
            decision_end = time.perf_counter()
            if decision['candidate_ids']:
                adapter._latency_stage = 'selected_execution'
                with timings.measure('execution.chunk'):
                    receipts = adapter.execute(request, decision)
            else:
                receipts = []
            end = time.perf_counter()
            loops.append({'index':index, 'request_s':request_s,
                'decision_s':decision_end-begin-request_s, 'execution_s':end-decision_end,
                'loop_s':end-begin, 'request':request,'decision':decision,'receipts':receipts,
                'request_sha256': hashlib.sha256(json.dumps(request,sort_keys=True,separators=(',',':'),
                    allow_nan=False).encode()).hexdigest(),
                'timings':timings.summary(end-begin, start_event=event)})
            with (args.output/'loops.jsonl').open('a') as stream:
                stream.write(json.dumps(loops[-1])+'\n')
            if args.startup:
                if any(r['steps_used']>0 for r in receipts):
                    return {'status':'startup_physical', 'first_physical':loops[-1],
                        'initial_physics_sha256': initial_physics_sha256, 'training':False}
                if index >= 9:
                    raise RuntimeError('startup did not reach a physical control request')
            if not decision['candidate_ids'] or any(r['skill'] in {'finish','ask_help'} for r in receipts):
                break
        return {'case':case, 'status':'physical_result', 'schema_version':VERSION,
            'success':bool(adapter.p.env.terminated or facade._native_success_events),
            'registered_predicate':facade.goal_status(), 'decisions':len(loops),
            'sim_steps':adapter.p.env.execution_budget()['used_sim_steps'],
            'wall_s':time.perf_counter()-started, 'timings':timings.summary(time.perf_counter()-timings.started),
            'source_commit':os.environ.get('SOURCE_COMMIT'), 'training':False,
            'initial_physics_sha256': initial_physics_sha256,
            'stop_reason': stop_reason,
            'candidate_ids':[loop['decision']['candidate_ids'] if loop['decision'] else None for loop in loops]}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--preflight', action='store_true')
    parser.add_argument('--worker', type=int)
    parser.add_argument('--startup', action='store_true')
    parser.add_argument('--startup-only', action='store_true')
    parser.add_argument('--indices', type=int, nargs='+',
        help='Registered indices; omitted means all 32, in registration order')
    args=parser.parse_args()
    args.source=args.source.resolve(strict=True)
    args.manifest=args.manifest.resolve(strict=True)
    plan=json.loads(args.manifest.read_bytes())
    assert len(plan['cases'])==32 and not plan['training'] and not plan['confirmation']
    assert str(args.source)==plan['baseline_source']
    indices = args.indices if args.indices is not None else list(range(32))
    if not indices or len(set(indices)) != len(indices) or any(not 0 <= i < 32 for i in indices):
        raise ValueError('indices must be unique registered state indices')
    options = plan.get('runtime_options', {})
    if (set(options) - {'lazy_planning_v1', 'registration_query_workers'}
            or ('lazy_planning_v1' in options and type(options['lazy_planning_v1']) is not bool)
            or ('registration_query_workers' in options and (
                type(options['registration_query_workers']) is not int or options['registration_query_workers'] < 1))):
        raise ValueError('unregistered latency runtime options')
    for name in ('parents',):
        for ref in plan.get(name, []):
            if hashlib.sha256(Path(ref['path']).read_bytes()).hexdigest() != ref['sha256']:
                raise ValueError('fixed-state parent registration changed')
    for row in plan['cases']:
        for name in ('bddl','grasp_measurement_calibration'):
            if name in row['case']:
                ref=row['case'][name];assert __import__('hashlib').sha256(Path(ref['path']).read_bytes()).hexdigest()==ref['sha256']
        diagnostic = row['case'].get('diagnostic', {})
        references = [diagnostic[key] for key in ('old_summary', 'branchpoint') if key in diagnostic]
        references.extend(diagnostic.get('original_subtask_start', {}).values())
        for ref in references:
            if hashlib.sha256(Path(ref['path']).read_bytes()).hexdigest() != ref['sha256']:
                raise ValueError('registered saved-state replay input changed')
    sam_entry = plan['paired_protocol']['sam_entry']
    if hashlib.sha256(Path(sam_entry['path']).read_bytes()).hexdigest() != sam_entry['sha256']:
        raise ValueError('registered SAM entry changed')
    if args.preflight:
        sys.path.insert(0,str(args.source))
        os.environ.setdefault('MUJOCO_GL','egl')
        os.environ.setdefault('PYOPENGL_PLATFORM','egl')
        hooks=module(args.source/'coordination/bounded_skills_20261016/scripts/shared_gpu_episodes_20261019.py','latency_preflight_hooks')
        hooks.bootstrap_source('d2')
        from scripts import probe_bounded_hybrid_d2
        from robots.libero.bounded_skills import MeasuredSkillAdapter
        print(json.dumps({'preflight':'passed','states':32,'episode_concurrency':1}),flush=True)
        return 0
    if args.worker is not None:
        return worker(args,plan)
    os.environ['PYTHONPATH'] = str(args.source)
    os.chdir(args.source)
    sys.path.insert(0,str(args.source))
    hooks=module(args.source/'coordination/bounded_skills_20261016/scripts/shared_gpu_episodes_20261019.py','latency_hooks')
    hooks.bootstrap_source('d2')
    from scripts.probe_bounded_feasibility import services
    args.output.mkdir(parents=True)
    write(args.output/'launch.json',{'manifest':str(args.manifest),'source':str(args.source),
        'source_commit':plan['baseline_commit'],'slurm_job_id':os.environ.get('SLURM_JOB_ID'),
        'cuda_visible_devices':os.environ.get('CUDA_VISIBLE_DEVICES'),'episode_concurrency':1,
        'comparison_scope':'N1 only; no throughput claim','training':False})
    service_args=SimpleNamespace(source=args.source,output=args.output,
        sam3_entry=Path(plan['paired_protocol']['sam_entry']['path']))
    env=dict(os.environ,SOURCE_COMMIT=plan['baseline_commit'])
    with hooks.owned_services(service_args,services,vla=True) as endpoints:
        for startup,index in [(True,indices[0])]+([] if args.startup_only else [(False,i) for i in indices]):
            output=args.output/('startup' if startup else f'case{index:03d}')
            output.mkdir()
            write(output/'assignment.json',{key+'_url':client._base_url for key,client in endpoints.items()})
            command=[sys.executable,str(Path(__file__).resolve()),'--manifest',str(args.manifest),
                '--source',str(args.source),'--output',str(output),'--worker',str(index)]
            if startup: command.append('--startup')
            with (output/'worker.log').open('x')as log:
                result=subprocess.run(command,env=env,stdout=log,stderr=subprocess.STDOUT)
            if result.returncode:
                raise RuntimeError(f'latency worker {index} failed; see {output}/worker.log')
            if startup and json.loads((output/'summary.json').read_bytes())['status'] != 'startup_physical':
                raise RuntimeError('startup ended without a completed physical request')
            print(json.dumps({'index':index,'startup':startup,'closed':str(output/'summary.json')}),flush=True)
    return 0


if __name__=='__main__':
    raise SystemExit(main())
