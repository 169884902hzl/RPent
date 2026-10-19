"""Run isolated episode processes against one owned SAM3 service per GPU job.

This launcher imports immutable skill/planning code. Its D2-only snapshot
compatibility hook restores solver warmstart after observation rebuilding.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import threading
import time
import traceback
from pathlib import Path


def dump(path, value):
    Path(path).write_text(json.dumps(value, indent=2) + '\n')


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def percentile(values, quantile):
    if not values:
        return None
    values = sorted(values)
    at = (len(values)-1)*quantile
    lo = int(at)
    hi = min(lo+1, len(values)-1)
    return values[lo] + (values[hi]-values[lo])*(at-lo)


class TimedRPC:
    """Keep each episode's transport and latency log private to its process."""
    def __init__(self, client, log):
        self.client, self.log = client, log
        self._base_url = client._base_url

    def call(self, method, args=(), kwargs=None, *, timeout_s=None):
        started = time.perf_counter()
        error = None
        try:
            return self.client.call(method, args=args, kwargs=kwargs, timeout_s=timeout_s)
        except BaseException as exc:
            error = type(exc).__name__
            raise
        finally:
            self.log.write(json.dumps({'method': method, 'wall_s': time.perf_counter()-started,
                'error': error, 'pid': os.getpid()})+'\n')
            self.log.flush()


def bootstrap_source(domain):
    if domain=='d2':
        # The frozen environment module sets/checks its GL bootstrap before
        # importing MuJoCo. Load it before the diagnostic's helper imports.
        import robots.libero.env_server


def install_d2_restore_compatibility():
    """Preserve saved solver input after the diagnostic rebuilds observations.

    MuJoCo forward rewrites qacc_warmstart. Restoring it last changes neither
    the observation nor a control, and keeps the frozen strict snapshot check.
    This hook is private to the owned D2 launcher, never an action/skill patch.
    """
    from functools import wraps
    from robots.libero import v5_branch_state

    original = v5_branch_state.restore_actuators

    @wraps(original)
    def restore(wrapper, saved):
        observed = original(wrapper, saved)
        wrapper.env.sim.data.qacc_warmstart[:] = saved['data']['qacc_warmstart']
        return observed

    v5_branch_state.restore_actuators = restore


def worker(args):
    assignment = json.loads(args.assignment.read_bytes())
    bootstrap_source(assignment['domain'])
    from rpent.utils.rpc.http_rpc import HttpRpcClient
    from scripts.probe_bounded_feasibility import episode, probe_config

    manifest = Path(assignment['manifest']['path'])
    assert digest(manifest) == assignment['manifest']['sha256']
    plan = json.loads(manifest.read_bytes())
    case = plan['cases'][assignment['case_index']]
    assert case == assignment['case']
    output = args.assignment.parent
    started = time.perf_counter()
    result = None
    try:
        with (output/'sam3_requests.jsonl').open('x') as ledger:
            endpoints = {'sam3': TimedRPC(HttpRpcClient(assignment['sam3_url']), ledger)}
            if assignment.get('vla_url'):
                endpoints['vla'] = HttpRpcClient(assignment['vla_url'])
            if assignment['domain'] == 'original':
                ref = plan['base_config']
                assert digest(ref['path']) == ref['sha256']
                config = probe_config(json.loads(Path(ref['path']).read_bytes()))
                # This study changes episode concurrency only. Do not quietly
                # turn the earlier candidate-worker experiment on or off.
                assert config.get('prefix_consequence_workers', 1) == 1
                assert config.get('request_consequence_workers', 1) == 1
                result = episode(case, 'oracle_k4', endpoints, output/(case['name']+'_oracle_k4'),
                                 config, startup=assignment['startup'])
            else:
                install_d2_restore_compatibility()
                from scripts.probe_bounded_hybrid_d2 import evaluate_case
                result = evaluate_case(case, endpoints, output/case['name'], plan,
                                       startup=assignment['startup'])
        status = result['status']
        if assignment['startup'] and status != 'startup_physical':
            raise RuntimeError('same-launcher startup produced no physical request')
        dump(output/'worker_summary.json', {'case':case, 'result':result,
            'wall_s':time.perf_counter()-started, 'pid':os.getpid(), 'exit_code':0,
            'source_commit':plan['source_commit'], 'independent_process_and_egl':True})
        return 0
    except BaseException as exc:
        dump(output/'worker_summary.json', {'case':case, 'result':result,
            'status':'startup_error' if assignment['startup'] else 'worker_error',
            'error':type(exc).__name__, 'message':str(exc), 'traceback':traceback.format_exc(),
            'wall_s':time.perf_counter()-started, 'pid':os.getpid(), 'exit_code':1,
            'source_commit':plan['source_commit']})
        raise


class ResourceSampler:
    """Observe only this job's process tree and allocated GPU."""
    def __init__(self, output):
        import psutil
        self.psutil = psutil
        self.root = psutil.Process()
        self.output = output
        self.stop = threading.Event()
        self.thread = threading.Thread(target=self.run, daemon=True)
        self.stage = 'services_starting'
        self.rows = []

    def run(self):
        previous, before, cpu_seen = None, time.monotonic(), {}
        gpu = os.environ.get('SLURM_JOB_GPUS', os.environ.get('CUDA_VISIBLE_DEVICES', '0')).split(',')[0]
        with (self.output/'resources.jsonl').open('x') as ledger:
            while not self.stop.is_set():
                rss = 0
                processes = [self.root, *self.root.children(recursive=True)]
                for process in processes:
                    try:
                        value = process.cpu_times()
                        cpu_seen[process.pid] = value.user+value.system
                        rss += process.memory_info().rss
                    except (self.psutil.NoSuchProcess, self.psutil.AccessDenied):
                        continue
                now = time.monotonic()
                total = sum(cpu_seen.values())
                row = {'time_s':time.time(), 'stage':self.stage, 'rss_process_sum_bytes':rss,
                    'cpu_cores':max(0., (total-previous)/(now-before)) if previous is not None else 0.,
                    'process_count':len(processes)}
                previous, before = total, now
                query = subprocess.run(['nvidia-smi','-i',gpu,
                    '--query-gpu=index,uuid,utilization.gpu,memory.used,memory.total',
                    '--format=csv,noheader,nounits'], text=True,capture_output=True)
                if query.returncode == 0:
                    fields=query.stdout.strip().split(', ')
                    row.update(gpu_index=fields[0], gpu_uuid=fields[1],
                        gpu_utilization_percent=float(fields[2]), gpu_memory_used_mib=float(fields[3]),
                        gpu_memory_total_mib=float(fields[4]))
                else:
                    row['gpu_query_error']=query.stderr.strip()
                self.rows.append(row)
                ledger.write(json.dumps(row)+'\n'); ledger.flush()
                self.stop.wait(2)

    def start(self):
        self.thread.start()

    def close(self):
        self.stop.set(); self.thread.join()

    def summary(self, stage):
        rows=[row for row in self.rows if row['stage']==stage]
        def peak(key):
            return max((row[key] for row in rows if key in row), default=None)
        utilization=[r['gpu_utilization_percent'] for r in rows if 'gpu_utilization_percent' in r]
        return {'samples':len(rows), 'cpu_peak_cores':peak('cpu_cores'),
            'rss_process_sum_peak_bytes':peak('rss_process_sum_bytes'),
            'gpu_memory_peak_mib':peak('gpu_memory_used_mib'),
            'gpu_utilization_mean_percent':sum(utilization)/len(utilization) if utilization else None,
            'gpu_utilization_p95_percent':percentile(utilization,.95),
            'scope':'job process-tree RSS sum; shared pages may be counted more than once; allocated GPU only'}


def run_level(args, plan, indices, endpoints, n, sampler):
    directory=args.output/f'N{n}'
    directory.mkdir()
    stage=f'{args.output.name}/N{n}'
    sampler.stage=stage
    start=time.perf_counter()
    waiting=list(enumerate(indices))
    active, completed=[],[]
    urls={key:client._base_url for key,client in endpoints.items()}
    with (directory/'episodes.jsonl').open('x') as ledger:
        while waiting or active:
            while waiting and len(active)<n:
                order,index=waiting.pop(0)
                case=plan['cases'][index]
                output=directory/f'{order:03d}_{case["name"]}'
                output.mkdir()
                assignment={'domain':args.domain,'case_index':index,'case':case,
                    'manifest':{'path':str(args.manifest),'sha256':digest(args.manifest)},
                    'sam3_url':urls['sam3'],'vla_url':urls.get('vla'),'startup':args.startup}
                path=output/'assignment.json'; dump(path,assignment)
                log=(output/'worker.log').open('x')
                command=[sys.executable,'-u',str(Path(__file__).resolve()),'--source',str(args.source),
                         '--worker','--assignment',str(path)]
                process=subprocess.Popen(command,stdout=log,stderr=subprocess.STDOUT,cwd=args.source,
                    env={**os.environ,'PYTHONPATH':str(args.source)})
                active.append((process,log,output))
            remaining=[]
            for process,log,output in active:
                code=process.poll()
                if code is None:
                    remaining.append((process,log,output));continue
                log.close()
                summary=output/'worker_summary.json'
                row=json.loads(summary.read_bytes()) if summary.exists() else {
                    'status':'startup_error','exit_code':code,'worker_log':str(output/'worker.log')}
                row.update(process_exit_code=code,worker_summary=str(summary),level_n=n)
                completed.append(row)
                ledger.write(json.dumps(row)+'\n');ledger.flush()
                print(json.dumps({'n':n,'completed':len(completed),'total':len(indices),
                    'case':row.get('case',{}).get('name'),'exit_code':code}),flush=True)
            active=remaining
            if active:
                time.sleep(.2)
    wall=time.perf_counter()-start
    latencies=[]
    for path in directory.glob('*/sam3_requests.jsonl'):
        latencies.extend(row['wall_s'] for line in path.open()
            if (row:=json.loads(line))['error'] is None and row['method'].startswith('sam3.'))
    result_key='success' if args.domain=='original' else 'actual_full_replay_success'
    successes=sum((row.get('result') or {}).get(result_key) is True for row in completed)
    failures=sum(row['process_exit_code']!=0 for row in completed)
    valid=sum((row.get('result') or {}).get('status')=='physical_result' for row in completed)
    report={'n':n,'registered_episodes':len(indices),'finished_processes':len(completed),
        'physical_episodes':valid,'successful_episodes':successes,'worker_errors':failures,
        'wall_s':wall,'completed_episodes_per_hour':valid*3600/wall,
        'sam3_requests':len(latencies),'sam3_request_p50_s':percentile(latencies,.5),
        'sam3_request_p95_s':percentile(latencies,.95),'resources':sampler.summary(stage),
        'source_commit':plan['source_commit'],'startup':args.startup,'training':False}
    dump(directory/'summary.json',report)
    print(json.dumps(report),flush=True)
    return report


def sequence(path):
    """Read the actual public choices, without changing their grouping."""
    return [row['decision']['candidate_ids'] for line in Path(path).open()
        if (row:=json.loads(line)).get('decision')]


def edit_distance(left, right):
    previous=list(range(len(right)+1))
    for i,a in enumerate(left,1):
        current=[i]
        for j,b in enumerate(right,1):
            current.append(min(current[-1]+1,previous[j]+1,previous[j-1]+(a!=b)))
        previous=current
    return previous[-1]


def compare_three(study, root, selected, serial_root=None):
    rows=[]
    for index,reference in enumerate(study['consistency_cases']):
        name=reference['case']['name']
        serial=(serial_root or root)/'measurements/N1'/f'{index:03d}_{name}'
        parallel=root/'consistency'/f'N{selected}'/f'{index:03d}_{name}'
        historical=Path(reference['choices']['path'])
        assert digest(historical)==reference['choices']['sha256']
        a=json.loads((serial/'worker_summary.json').read_bytes())['result']
        b=json.loads((parallel/'worker_summary.json').read_bytes())['result']
        serial_choices=next(serial.glob('*oracle_k4/choices.jsonl'))
        parallel_choices=next(parallel.glob('*oracle_k4/choices.jsonl'))
        old_sequence,serial_sequence,parallel_sequence=map(sequence,(historical,serial_choices,parallel_choices))
        baseline=edit_distance(old_sequence,serial_sequence)
        difference=edit_distance(serial_sequence,parallel_sequence)
        old=reference['historical_result']
        success_baseline=int(old['success']!=a['success'])
        success_difference=int(a['success']!=b['success'])
        steps_baseline=abs(old['sim_steps']-a['sim_steps'])
        steps_difference=abs(a['sim_steps']-b['sim_steps'])
        rows.append({'case':reference['case'],'historical_sequence':old_sequence,
            'serial_sequence':serial_sequence,'parallel_sequence':parallel_sequence,
            'choice_sequence_edit_baseline':baseline,'choice_sequence_edit_parallel':difference,
            'success_baseline_difference':success_baseline,'success_parallel_difference':success_difference,
            'simulation_step_baseline_difference':steps_baseline,'simulation_step_parallel_difference':steps_difference,
            'serial_result':a,'parallel_result':b,
            'within_serial_baseline':difference<=baseline and success_difference<=success_baseline
                and steps_difference<=steps_baseline})
    return {'cases':rows,'all_three_within_serial_baseline':all(row['within_serial_baseline'] for row in rows),
        'definition':'parallel choice-sequence edit distance, final success mismatch and sim-step delta must each not exceed historical-to-fresh-serial differences'}


def selected_parallel_n(reports):
    parallel=[r for r in reports if r['n']>1]
    best=max(r['completed_episodes_per_hour'] for r in parallel)
    return min(r['n'] for r in parallel if r['completed_episodes_per_hour']>=best/1.1)


def study_result(reports, consistency, source_commit, count, serial_reference=None):
    selected=selected_parallel_n(reports)
    serial=next(r['completed_episodes_per_hour'] for r in reports if r['n']==1)
    chosen=next(r for r in reports if r['n']==selected)
    return {'levels':reports,'selected_n':selected,'serial_episodes_per_hour':serial,
        'parallel_episodes_per_hour':chosen['completed_episodes_per_hour'],
        'measured_speedup':chosen['completed_episodes_per_hour']/serial,
        'consistency':consistency,'throughput_improved':chosen['completed_episodes_per_hour']>serial,
        'adoption_ready':consistency['all_three_within_serial_baseline']
            and chosen['completed_episodes_per_hour']>serial,
        'source_commit':source_commit,'plateau_fraction':.10,
        'serial_reference':str(serial_reference) if serial_reference else None,
        'training':False,'workload':f'{count} registered original development states; not an all-category rate estimate'}


def run_study(args, plan, study, endpoints, sampler):
    from copy import copy
    root=args.output
    startup=copy(args);startup.output=root/'startup';startup.output.mkdir();startup.startup=True
    checked=run_level(startup,plan,study['indices'][:4],endpoints,4,sampler)
    if checked['worker_errors']:
        raise RuntimeError('shared-service real startup failed; no full study admitted')
    actual=copy(args);actual.output=root/'measurements';actual.output.mkdir();actual.startup=False
    reports=[]
    for n in ((4,8,12) if args.serial_reference else (1,4,8,12)):
        report=run_level(actual,plan,study['indices'],endpoints,n,sampler)
        reports.append(report)
        if report['worker_errors']:
            raise RuntimeError('study worker failed; preserve its records and repair before continuing')
    # Register a 10% throughput plateau before reading any measured outcome.
    for n in (16,20):
        if reports[-1]['completed_episodes_per_hour']<1.1*reports[-2]['completed_episodes_per_hour']:
            break
        reports.append(run_level(actual,plan,study['indices'],endpoints,n,sampler))
        if reports[-1]['worker_errors']:
            raise RuntimeError('study worker failed')
    selected=selected_parallel_n(reports)
    verify=copy(actual);verify.output=root/'consistency';verify.output.mkdir()
    # Keep the chosen per-GPU load while comparing the three registered cases.
    comparison=run_level(verify,plan,study['indices'],endpoints,selected,sampler)
    if comparison['worker_errors']:
        raise RuntimeError('parallel consistency replay worker failed')
    if args.serial_reference:
        serial_summary=args.serial_reference/'measurements/N1/summary.json'
        # Finish GPU ownership now. The login-node finalizer joins the two
        # actual measurements; compute nodes cannot query Slurm accounting.
        return {'levels':reports,'selected_n':selected,
            'gpu_measurements_complete':True,'offline_finalization_required':True,
            'awaiting_external_serial':not serial_summary.exists(),
            'serial_reference':str(args.serial_reference),'adoption_ready':False,
            'source_commit':plan['source_commit'],'training':False}
    consistency=compare_three(study,root,selected,args.serial_reference)
    return study_result(reports,consistency,plan['source_commit'],len(study['indices']),args.serial_reference)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path)
    parser.add_argument('--batch-plan',type=Path,
        help='Registered source/manifest/indices for this Slurm array task')
    parser.add_argument('--batch-index',type=int)
    parser.add_argument('--worker',action='store_true')
    parser.add_argument('--assignment',type=Path)
    parser.add_argument('--manifest',type=Path)
    parser.add_argument('--domain',choices=('original','d2'),default='original')
    parser.add_argument('--indices',default='0,1,2,3')
    parser.add_argument('--levels',default='4,8,12')
    parser.add_argument('--output',type=Path)
    parser.add_argument('--startup',action='store_true')
    parser.add_argument('--preflight',action='store_true')
    parser.add_argument('--study-plan',type=Path)
    parser.add_argument('--serial-reference',type=Path,
        help='Reuse a concurrently running identical N1 workload on another allocated GPU')
    args=parser.parse_args()
    if args.batch_plan:
        batches=json.loads(args.batch_plan.read_bytes())
        index=args.batch_index if args.batch_index is not None else int(os.environ['SLURM_ARRAY_TASK_ID'])
        batch=batches['batches'][index]
        args.source=Path(batch['source'])
        args.manifest=Path(batch['manifest']['path'])
        assert digest(args.manifest)==batch['manifest']['sha256']
        args.domain=batch['domain']
        args.indices=','.join(map(str,batch['indices']))
        args.levels=str(batches['selected_n'])
        os.environ['SOURCE_COMMIT']=batch['source_commit']
        os.environ['LIBERO_TYPE']='standard' if args.domain=='original' else 'pro'
    if args.source is None:
        parser.error('--source or --batch-plan is required')
    args.source=args.source.resolve(strict=True)
    os.environ['PYTHONPATH']=str(args.source)
    os.chdir(args.source)
    sys.path.insert(0,str(args.source))
    if args.worker:
        return worker(args)
    bootstrap_source(args.domain)
    from scripts.probe_bounded_feasibility import services, probe_config
    from scripts.v5_probe_preflight import load_pinned_manifest, validate_registered_states
    import psutil
    args.manifest=args.manifest.resolve(strict=True)
    indices=[int(value) for value in args.indices.split(',')]
    levels=[int(value) for value in args.levels.split(',')]
    assert levels and all(n>0 for n in levels)
    study=json.loads(args.study_plan.read_bytes()) if args.study_plan else None
    if study:
        assert study['manifest']=={'path':str(args.manifest),'sha256':digest(args.manifest)}
        assert study['source']==str(args.source) and study['source_commit']==os.environ['SOURCE_COMMIT']
        assert len(study['consistency_cases'])==3 and study['plateau_fraction']==.10
        indices=study['indices']
    if args.serial_reference:
        assert study,'External N1 reference requires a registered study'
        args.serial_reference=args.serial_reference.resolve(strict=True)
        serial_launch=json.loads((args.serial_reference/'launch.json').read_bytes())
        assert serial_launch['source']==str(args.source)
        assert serial_launch['source_commit']==study['source_commit']
        assert serial_launch['manifest']==study['manifest']
        assert serial_launch['indices']==indices and serial_launch['domain']=='original'
    if args.domain=='original':
        _,plan,base=load_pinned_manifest(args.manifest)
        config=probe_config(base)
        assert config.get('prefix_consequence_workers',1)==1
        assert config.get('request_consequence_workers',1)==1
        if plan.get('permanent_exclusions'):
            from scripts.bounded_state_exclusions import check_exclusions
            check_exclusions([plan['cases'][i] for i in indices],plan['permanent_exclusions'])
    else:
        from robots.libero.bounded_hybrid_diagnostic import validate_d2_episode
        plan=json.loads(args.manifest.read_bytes())
        assert len(plan['cases'])==40 and not plan['training'] and not plan['confirmation']
        for case in plan['cases']:
            validate_d2_episode(case['episode'])
            assert digest(case['bddl']['path'])==case['bddl']['sha256']
    assert indices and all(0<=i<len(plan['cases']) for i in indices)
    validate_registered_states([plan['cases'][i] for i in indices])
    os.environ['SOURCE_COMMIT']=plan['source_commit']
    if args.preflight:
        print(json.dumps({'preflight':'passed','n_cases':len(indices),'levels':levels,
            'source_commit':plan['source_commit'],'launcher_sha256':digest(__file__),
            'candidate_concurrency':'serial','psutil_version':psutil.__version__}),flush=True)
        return 0
    args.output=args.output.resolve()
    args.output.mkdir(parents=True,exist_ok=False)
    dump(args.output/'launch.json',{'source':str(args.source),'source_commit':plan['source_commit'],
        'launcher':{'path':str(Path(__file__).resolve()),'sha256':digest(__file__)},
        'manifest':{'path':str(args.manifest),'sha256':digest(args.manifest)},
        'indices':indices,'levels':levels,'domain':args.domain,'startup':args.startup,
        'serial_reference':str(args.serial_reference) if args.serial_reference else None,
        'slurm_job_id':os.environ.get('SLURM_JOB_ID'),'cuda_visible_devices':os.environ.get('CUDA_VISIBLE_DEVICES'),
        'cpu_affinity':sorted(os.sched_getaffinity(0)),'sam_services_per_gpu_job':1,
        'episode_isolation':'fresh exec process, fresh simulator/EGL/RNG/IK per episode','training':False})
    sampler=ResourceSampler(args.output);sampler.start()
    try:
        service_started=time.perf_counter()
        with services(args.output,vla=args.domain=='d2') as endpoints:
            service_startup_s=time.perf_counter()-service_started
            if study:
                report=run_study(args,plan,study,endpoints,sampler)
                report['service_startup_s']=service_startup_s
                if report.get('offline_finalization_required'):
                    dump(args.output/'measurement_summary.json',report)
                    return 0
                dump(args.output/'study_summary.json',report)
                return 0 if report['adoption_ready'] else 2
            reports=[run_level(args,plan,indices,endpoints,n,sampler) for n in levels]
    finally:
        sampler.close()
    dump(args.output/'summary.json',{'levels':reports,'training':False})
    if any(report['worker_errors'] for report in reports):
        return 1
    return 0


if __name__=='__main__':
    raise SystemExit(main())
