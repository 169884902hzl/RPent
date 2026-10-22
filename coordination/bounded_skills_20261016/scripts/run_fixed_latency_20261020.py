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


def pending_cases(output, indices):
    """Resume completed cases while retaining every interrupted attempt."""
    pending = []
    for index in indices:
        pointer = output / f'closed_{index:03d}.json'
        if pointer.exists():
            row = json.loads(pointer.read_bytes())
            if hashlib.sha256(Path(row['summary']).read_bytes()).hexdigest() != row['sha256']:
                raise ValueError('completed latency case changed')
            continue
        directory = output / f'case{index:03d}'
        prior = [directory / 'summary.json', *output.glob(f'case{index:03d}_attempt*/summary.json')]
        completed = next((path for path in prior if path.exists()
            and json.loads(path.read_bytes()).get('status') in {'physical_result', 'oracle_rule_uncovered'}), None)
        if completed:
            write(pointer, {'summary': str(completed),
                'sha256': hashlib.sha256(completed.read_bytes()).hexdigest()})
            continue
        attempt = 0
        while directory.exists():
            attempt += 1
            directory = output / f'case{index:03d}_attempt{attempt}'
        pending.append((index, directory))
    return pending


def require_physical_startup(result):
    """Admit both bounded and saved-VLA startup reports with real controls."""
    if result.get('status') == 'startup_physical':
        receipts = result.get('first_physical', {}).get('receipts', [])
        steps = sum(receipt['steps_used'] for receipt in receipts)
    elif result.get('status') == 'physical_result':
        steps = sum(trial.get('sim_steps', 0) for trial in result.get('trials', []))
    else:
        steps = 0
    if steps <= 0:
        raise RuntimeError('startup ended without a completed physical request')


def capture_failed_support_routes(output):
    """Keep exact public lift-screen inputs for CPU regression diagnosis.

    Opt-in diagnostic runs only. Serialization time remains in their timing;
    latency comparison runs leave this disabled.
    """
    import gzip
    import pickle
    from robots.libero.bounded_screen import PublicRouteScreen
    from robots.libero.bounded_skills import MeasuredSkillAdapter
    original=PublicRouteScreen.__call__
    captured=0
    directory=output/'failed_support_routes'
    def call(screen,*positional,**kwargs):
        nonlocal captured
        frame = sys._getframe(1)
        while frame is not None:
            owner = frame.f_locals.get('self')
            if isinstance(owner, MeasuredSkillAdapter) and frame.f_code.co_name == '_execute_one':
                break
            frame = frame.f_back
        raw=(pickle.dumps((screen,positional,kwargs),protocol=5)
            if frame is not None and captured<8 and getattr(screen,'support_separation',False) else None)
        result=original(screen,*positional,**kwargs)
        if raw is not None and not result['passed']:
            directory.mkdir(exist_ok=True)
            path=directory/f'{captured:02d}.pkl.gz'
            path.write_bytes(gzip.compress(raw,compresslevel=1,mtime=0))
            public_context = None
            while frame is not None:
                owner = frame.f_locals.get('self')
                if isinstance(owner, MeasuredSkillAdapter):
                    context = public_support_replay_inputs(owner,
                        frame.f_locals.get('payload_reference'))
                    context['caller'] = frame.f_code.co_name
                    data = pickle.dumps(context, protocol=5)
                    context_path = directory/f'{captured:02d}_public.pkl.gz'
                    context_path.write_bytes(gzip.compress(data,compresslevel=1,mtime=0))
                    public_context = {'path': str(context_path),
                        'uncompressed_sha256': hashlib.sha256(data).hexdigest()}
                    break
                frame = frame.f_back
            write(directory/f'{captured:02d}.json',dict(input=str(path),
                input_sha256=hashlib.sha256(raw).hexdigest(),result=result,
                public_context=public_context,
                source='public_rgbd_static_robot_geometry_and_proprioception',
                training=False,private_truth_used=False))
            captured+=1
        del frame
        return result
    PublicRouteScreen.__call__=call


def public_support_replay_inputs(adapter, payload_reference=None):
    """Save current public depth/ownership inputs without querying physics/RPC."""
    import copy
    import numpy as np
    from robots.libero.bounded_motion import measured_robot

    state = adapter.ex.toolkit._state
    attached = next((screen for key, screen in adapter._screen_cache.items()
        if len(key) > 2 and key[0] == adapter.active and key[1] is True
            and len(getattr(screen, 'payload', []))), None)
    return {'capture_step': state.latest_step, 'robot': measured_robot(adapter.p),
        'worlds': {camera: np.array(state.load(camera+'_world_high.npz'), copy=True)
            for camera in ('agentview', 'wrist')},
        'entities': copy.deepcopy(adapter.scene.entities),
        'active_anchor': adapter.active,
        'verified_held_anchor': adapter.held,
        'grasp_reference': copy.deepcopy(adapter.grasp_reference),
        'contact_plans': copy.deepcopy(adapter.plans),
        'committed_grasps': copy.deepcopy(adapter.committed_grasps),
        'measurement_clouds': copy.deepcopy(adapter.scene.measurement_clouds),
        'payload_reference': copy.deepcopy(payload_reference),
        'cached_attachment_geometry': ({'scene': attached.points.copy(),
            'target': attached.target.copy(), 'payload_local': attached.payload.copy()}
            if attached is not None else None),
        'latency_stage': getattr(adapter, '_latency_stage', None),
        'sensor_interface': type(adapter.p.env).__module__+'.'+type(adapter.p.env).__name__,
        'source': 'current_public_rgbd_and_proprioception_only',
        'physics_steps': 0, 'rpc_calls': 0, 'training': False}


def common_start(args, facade, adapter, policy, probe):
    """Share complete integration/controller/RNG state across source processes."""
    if getattr(args,'common_starts',None) is None:
        return None
    import pickle
    root=args.common_starts
    root.mkdir(parents=True,exist_ok=True)
    # Restore probes use the same canonical case state as the scored arm.
    # Startup aliases existed only for cases previously used as shard heads.
    prefix = 'startup' if args.startup and args.initial_mode == 'create' else 'state'
    path=root/f'{prefix}_{args.worker:03d}.pkl'
    if args.initial_mode=='create' and not path.exists():
        probe.save_checkpoint(facade,adapter,policy,path)
    if not path.exists():
        raise ValueError('shared baseline initial state is missing: '+str(path))
    saved=pickle.loads(path.read_bytes())
    integration=saved['physics']['actuator_state'].get('integration')
    if integration is None:
        raise ValueError('strict pair requires mjSTATE_INTEGRATION; legacy hash cannot be repaired')
    # Share physics, not a different source's adapter, cached plans or schema.
    # Each arm must measure the common state through its own implementation.
    own_runtime=probe.capture_runtime(adapter,policy)
    probe.restore_checkpoint(facade,adapter,policy,saved)
    probe.restore_runtime(adapter,policy,own_runtime)
    expected=probe.snapshot_digest(saved['physics'])
    actual=probe.snapshot_digest(facade.snapshot())
    evidence={'checkpoint':str(path),'checkpoint_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
        'expected_complete_initial_sha256':expected,'actual_complete_initial_sha256':actual,
        'integration_sha256':integration['sha256'],'source_role':args.initial_mode,
        'public_runtime_source':'current arm; baseline public caches are not imported'}
    if actual!=expected:
        raise ValueError('complete integration/controller/RNG initial state differs; pair not admitted')
    # Physics was deliberately replaced while retaining this arm's runtime.
    # Its prior capture cannot certify unchanged anchors at the common state.
    adapter._incremental_previous_robot = None
    adapter.refresh()
    evidence['post_public_refresh_complete_sha256']=probe.snapshot_digest(facade.snapshot())
    write(args.output/'common_initial_verified.json',evidence)
    if evidence['post_public_refresh_complete_sha256']!=expected:
        raise ValueError('public refresh changed complete initial state; pair not admitted')
    return evidence


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

    if os.environ.get('EXEC_CAPTURE_FAILED_SUPPORT')=='1':
        capture_failed_support_routes(args.output)

    hooks.install_d2_request_compatibility(probe)
    runtime_options = plan.get('runtime_options', {})
    scene_options = plan.get('scene_options', {})
    artifact_options = plan.get('artifact_options', {})
    tracking_stats = {}
    if scene_options:
        probe.BOUNDED_SCENE_FLAGS = {**probe.BOUNDED_SCENE_FLAGS, **scene_options}
    if runtime_options or scene_options or artifact_options:
        original_runtime = probe.runtime
        from contextlib import contextmanager

        @contextmanager
        def configured_runtime(*positional, **kwargs):
            kwargs.update(artifact_options)
            with original_runtime(*positional, **kwargs) as runtime:
                for key, value in runtime_options.items():
                    setattr(runtime[1], key, value)
                try:
                    yield runtime
                finally:
                    scene = runtime[1].scene
                    if getattr(scene,'rgbd_mask_tracking_v1',False):
                        tracker=scene.rpc
                        tracking_stats.update(full_queries=tracker.full_queries,
                            tracked_queries=tracker.tracked_queries,exact_reuses=tracker.exact_reuses,
                            events=list(tracker.events))
        probe.runtime = configured_runtime
        original_restore = probe.restore_checkpoint

        def configured_restore(facade, adapter, policy, saved):
            result = original_restore(facade, adapter, policy, saved)
            for key, value in runtime_options.items():
                setattr(adapter, key, value)
            for key, value in scene_options.items():
                setattr(adapter.scene,key,value)
            if scene_options.get('rgbd_mask_tracking_v1') and not hasattr(adapter.scene,'_mask_tracking_history'):
                adapter.scene._mask_tracking_history={'entries':{},'frames':{}}
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
                if args.common_starts is not None:
                    original_trial=probe.trial
                    def paired_trial(*positional,**keywords):
                        facade,adapter,policy=positional[:3]
                        evidence=common_start(args,facade,adapter,policy,probe)
                        values=list(positional)
                        values[8]=adapter.request(k=4)
                        result,endpoint=original_trial(*values,**keywords)
                        result['common_initial']=evidence
                        return result,endpoint
                    probe.trial=paired_trial
                result = repair.evaluate_case(row['case'], endpoints, args.output/'episode',
                    {'evaluation':'hybrid_repair', 'training':False, 'confirmation':False,
                     'source_commit':plan['baseline_commit'], 'schema6_source':plan.get('schema6_source',False),
                     'cases':[row['case']]}, startup=args.startup)
            else:
                (args.output/'episode').mkdir()
                result = bounded_episode(args, row, endpoints, probe)
            result['registered_runtime_options'] = runtime_options
            result['registered_scene_options'] = scene_options
            result['registered_artifact_options'] = artifact_options
            if tracking_stats:
                write(args.output/'tracking_events.json',tracking_stats)
                result['perception_tracking_counts']={key:value for key,value in tracking_stats.items() if key!='events'}
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
        common_initial=common_start(args,facade,adapter,policy,probe)
        initial_snapshot = facade.snapshot()
        import pickle
        (args.output/'private_initial_physics.pkl').write_bytes(pickle.dumps(initial_snapshot,protocol=5))
        initial_physics_sha256 = probe.snapshot_digest(initial_snapshot)
        for index in range(getattr(args,'decision_limit',160)):
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
            detail_start = len(adapter.details)
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
                'execution_details': adapter.details[detail_start:],
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
            if not decision['candidate_ids'] or any((r['skill'] == 'finish' or r['skill'] == 'ask_help' and r['outcome'] == 'rejected') for r in receipts):
                break
        return {'case':case, 'status':'physical_result', 'schema_version':VERSION,
            'success':bool(adapter.p.env.terminated or facade._native_success_events),
            'registered_predicate':facade.goal_status(), 'decisions':len(loops),
            'sim_steps':adapter.p.env.execution_budget()['used_sim_steps'],
            'wall_s':time.perf_counter()-started, 'timings':timings.summary(time.perf_counter()-timings.started),
            'source_commit':os.environ.get('SOURCE_COMMIT'), 'training':False,
            'initial_physics_sha256': initial_physics_sha256,
            'common_initial':common_initial,
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
    parser.add_argument('--common-starts',type=Path)
    parser.add_argument('--initial-mode',choices=('create','restore'))
    parser.add_argument('--indices', type=int, nargs='+',
        help='Registered indices; omitted means all 32, in registration order')
    args=parser.parse_args()
    if (args.common_starts is None)!=(args.initial_mode is None):
        raise ValueError('common-starts and initial-mode must be provided together')
    if args.common_starts is not None:
        args.common_starts=args.common_starts.resolve()
    args.source=args.source.resolve(strict=True)
    args.manifest=args.manifest.resolve(strict=True)
    plan=json.loads(args.manifest.read_bytes())
    assert len(plan['cases'])==32 and not plan['training'] and not plan['confirmation']
    assert str(args.source)==plan['baseline_source']
    indices = args.indices if args.indices is not None else list(range(32))
    if not indices or len(set(indices)) != len(indices) or any(not 0 <= i < 32 for i in indices):
        raise ValueError('indices must be unique registered state indices')
    if args.common_starts is not None and args.initial_mode == 'restore':
        for index in indices:
            if not (args.common_starts/f'state_{index:03d}.pkl').is_file():
                raise ValueError(f'canonical shared initial state is missing: state_{index:03d}.pkl')
    options = plan.get('runtime_options', {})
    if (set(options) - {'lazy_planning_v1', 'registration_query_workers'}
            or ('lazy_planning_v1' in options and type(options['lazy_planning_v1']) is not bool)
            or ('registration_query_workers' in options and (
                type(options['registration_query_workers']) is not int or options['registration_query_workers'] < 1))):
        raise ValueError('unregistered latency runtime options')
    scene_options = plan.get('scene_options', {})
    if (set(scene_options)-{'rgbd_mask_tracking_v1'}
            or any(type(value) is not bool for value in scene_options.values())):
        raise ValueError('unregistered latency scene options')
    artifact_options = plan.get('artifact_options', {})
    if (set(artifact_options)-{'artifact_compression_level'}
            or any(type(value) is not int or not 0 <= value <= 9
                   for value in artifact_options.values())):
        raise ValueError('unregistered latency artifact options')
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
    for key in ('PI05_CHECKPOINT_PATH','SAM3_CHECKPOINT_PATH'):
        value=os.environ.get(key)
        if not value:
            raise ValueError(key+' must be set before startup/preflight')
        if not Path(value).is_absolute():
            raise ValueError(key+' must use an absolute path')
        Path(value).resolve(strict=True)
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
    args.output.mkdir(parents=True,exist_ok=True)
    pending = pending_cases(args.output, indices)
    if not pending:return 0
    write(args.output/f'launch_{time.time_ns()}.json',{'manifest':str(args.manifest),'source':str(args.source),
        'source_commit':plan['baseline_commit'],'slurm_job_id':os.environ.get('SLURM_JOB_ID'),
        'cuda_visible_devices':os.environ.get('CUDA_VISIBLE_DEVICES'),'episode_concurrency':1,
        'comparison_scope':'N1 only; no throughput claim','training':False})
    service_args=SimpleNamespace(source=args.source,output=args.output,
        sam3_entry=Path(plan['paired_protocol']['sam_entry']['path']))
    env=dict(os.environ,SOURCE_COMMIT=plan['baseline_commit'])
    with hooks.owned_services(service_args,services,vla=True) as endpoints:
        for startup,index,output in [(True,pending[0][0],args.output/f'startup_{time.time_ns()}')]+(
                [] if args.startup_only else [(False,i,path) for i,path in pending]):
            output.mkdir()
            write(output/'assignment.json',{key+'_url':client._base_url for key,client in endpoints.items()})
            command=[sys.executable,str(Path(__file__).resolve()),'--manifest',str(args.manifest),
                '--source',str(args.source),'--output',str(output),'--worker',str(index)]
            if args.common_starts is not None:
                command.extend(['--common-starts',str(args.common_starts),'--initial-mode',args.initial_mode])
            if startup: command.append('--startup')
            with (output/'worker.log').open('x')as log:
                result=subprocess.run(command,env=env,stdout=log,stderr=subprocess.STDOUT)
            if result.returncode:
                raise RuntimeError(f'latency worker {index} failed; see {output}/worker.log')
            if startup:
                require_physical_startup(json.loads((output/'summary.json').read_bytes()))
            if not startup:
                write(args.output/f'closed_{index:03d}.json', {'summary':str(output/'summary.json'),
                    'sha256':hashlib.sha256((output/'summary.json').read_bytes()).hexdigest()})
            print(json.dumps({'index':index,'startup':startup,'closed':str(output/'summary.json')}),flush=True)
    return 0


if __name__=='__main__':
    raise SystemExit(main())
