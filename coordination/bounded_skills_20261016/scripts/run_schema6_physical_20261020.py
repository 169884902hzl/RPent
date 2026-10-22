"""Resumable schema6 probes with shared services and isolated episode processes."""
import argparse
import copy
import hashlib
import importlib.util
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from types import SimpleNamespace
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED


def write(path, value):
    with Path(path).open('x') as stream:
        json.dump(value, stream, indent=2, default=lambda x:x.tolist() if hasattr(x,'tolist') else str(x))


def hooks(source):
    path=source/'coordination/bounded_skills_20261016/scripts/shared_gpu_episodes_20261019.py'
    spec=importlib.util.spec_from_file_location('schema6_hooks',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def checked(ref):
    path=Path(ref['path'])
    if hashlib.sha256(path.read_bytes()).hexdigest()!=ref['sha256']:
        raise ValueError(f'registered input changed: {path}')
    return path


def move_subtask(probe, facade, adapter, policy, specs, anchor_id):
    """Associate a measured contact part with its existing private goal.

    A door/panel candidate can refer to a measured child of the goal's
    cabinet/microwave anchor. This only selects the diagnostic outcome to
    measure; it creates no candidate or public binding.
    """
    related = {anchor_id}
    entity = adapter.scene.entities.get(anchor_id)
    while entity is not None and entity.part_of and entity.part_of not in related:
        related.add(entity.part_of)
        entity = adapter.scene.entities.get(entity.part_of)
    satisfied = facade.goal_status()['satisfied']
    for subtask in specs:
        if satisfied[subtask['goal_index']]:
            continue
        source, target = probe.bind_subtask(policy, adapter, subtask)
        held = source is not None and adapter.held == source.id
        if subtask['mode'] == 'pick' and held:
            continue
        if ((source is not None and source.id in related)
                or (held and target is not None and target.id in related)):
            return subtask
    return None


def physical_steps(result):
    """Read completed controls from bounded, VLA and full-replay reports."""
    return (sum(r['steps_used'] for r in result.get('first_physical', {}).get('receipts', []))
        or result.get('sim_steps', 0)
        or sum(t.get('sim_steps', 0) for t in result.get('trials', []))
        or sum(t.get('sim_steps', 0) for t in result.get('full_replay', []))
        or sum(r['steps_used'] for arm in result.get('arms', []) for r in arm.get('first_receipts', [])))


def worker(args, plan):
    row=plan['jobs'][args.worker]
    os.environ['LIBERO_TYPE']='pro' if row['kind'] in {'d2', 'd2_replay', 'option_factor', 'a1_preparation'} else 'standard'
    os.environ['LIBERO_GRASP_DIAGNOSTIC_MODELS']=str(args.output/'private_grasp_models')
    helper=hooks(args.source);helper.bootstrap_source('d2')
    helper.install_d2_restore_compatibility()
    from scripts import probe_bounded_hybrid_d2 as probe
    from rpent.utils.rpc.http_rpc import HttpRpcClient
    assignment=json.loads((args.output/'assignment.json').read_bytes())
    endpoints={key:HttpRpcClient(assignment[key+'_url']) for key in ('sam3','vla')}
    helper.install_d2_request_compatibility(probe)
    if row['kind']=='a1_preparation':
        from scripts.probe_bounded_A1_preparation import run_case
        result = run_case(row, plan, endpoints, args.output/'episode', startup=args.startup)
    elif row['kind']=='option_factor':
        from scripts.probe_bounded_option_ceiling import run_case
        result = run_case(row, plan, endpoints, args.output/'episode', startup=args.startup)
    elif row['kind']=='original_fork':
        from scripts import probe_bounded_hybrid_repair as repair
        manifest = json.loads(checked(row['manifest']).read_bytes())
        if row['case']['diagnostic']['domain'] != 'original':
            raise ValueError('original train fork cannot consume D2 or PRO positions')
        manifest['source_commit'] = plan['source_commit']
        result = repair.evaluate_case(row['case'], endpoints, args.output/'episode',
            manifest, startup=args.startup)
    elif row['kind']=='layout_pilot':
        from coordination.bounded_skills_20261016.scripts.run_own_layout_pi_pilot_20261022 import run_case
        result = run_case(row, plan, endpoints, args.output/'episode', startup=args.startup)
    elif row['kind']=='layout_collect':
        from coordination.bounded_skills_20261016.scripts.collect_own_layout_prefixes_20261022 import run_case
        result = run_case(row, plan, endpoints, args.output/'episode', startup=args.startup)
    elif row['kind']=='d2':
        manifest=json.loads(checked(row['manifest']).read_bytes())
        manifest['recovery_budget']=row['recovery_budget']
        manifest['source_commit']=plan['source_commit']
        manifest['schema_version']=plan['schema_version']
        manifest['vla_options_v2']=plan.get('vla_options_v2',False)
        if 'vla_variants' in plan:
            manifest['vla_variants'] = plan['vla_variants']
        manifest['parent_registration']=row['manifest']
        result=probe.evaluate_case(row['case'],endpoints,args.output/'episode',manifest,startup=args.startup)
    elif row['kind']=='d2_replay':
        import pickle
        from robots.libero.bounded_hybrid_paths import select_complete_path, replay_complete_path
        parent = json.loads(checked(row['parent_summary']).read_bytes())
        selection = select_complete_path(parent)
        if selection != row['path_selection']:
            raise ValueError('registered complete-path selection changed')
        initial = pickle.loads(checked(row['parent_initial']).read_bytes())
        with probe.runtime(row['case'], endpoints, args.output/'episode') as (facade, adapter, policy, timings):
            probe.restore_checkpoint(facade, adapter, policy, initial)
            adapter.hybrid_recovery_budget = row['recovery_budget']
            if not adapter.vla_options_v2:
                raise ValueError('saved replay state has no B2 catalog')
            actual = probe.snapshot_digest(facade.snapshot())
            if actual != probe.snapshot_digest(initial['physics']):
                raise ValueError('complete replay did not start from the full captured initial state')
            result = replay_complete_path(probe, facade, adapter, policy, timings,
                selection, row['replay_seed_base'], args.output/'replay')
            result.update(case=row['case'], source_commit=plan['source_commit'],
                parent_summary=row['parent_summary'], parent_initial=row['parent_initial'],
                sampling_source_commit=parent['source_commit'], private_rule_status=parent['status'],
                unsupported=parent.get('unsupported', []),
                initial_physics_sha256=actual, parent_initial_physics_sha256=probe.snapshot_digest(initial['physics']),
                recovery_budget=row['recovery_budget'])
    elif row['kind']=='model':
        from coordination.bounded_skills_20261016.scripts.original_model_closedloop_20261021 import run_episode
        if row['split'] not in {'init_holdout', 'd2_evaluation'} or not plan['evaluation_only']:
            raise ValueError('model probe requires registered evaluation-only identities')
        if row['split'] == 'd2_evaluation':
            from robots.libero.bounded_hybrid_diagnostic import validate_d2_episode
            validate_d2_episode(row['case']['episode'])
        result = run_episode(probe, row['case'], endpoints, args.output/'episode', plan,
            row['k'], startup=args.startup,
            domain='d2' if row['split'] == 'd2_evaluation' else 'original', split=row['split'])
    elif row['kind']=='smoke':
        # This fixed panel checks source startup and a real skill chunk in
        # each category. It is not a task-success or feasibility denominator.
        path=args.source/'coordination/bounded_skills_20261016/scripts/run_fixed_latency_20261020.py'
        spec=importlib.util.spec_from_file_location('schema6_smoke_episode',path)
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        (args.output/'episode').mkdir()
        smoke_args=SimpleNamespace(**(vars(args)|{'startup':True,'common_starts':None,'decision_limit':8}))
        result=module.bounded_episode(smoke_args,{'case':row['case'],'domain':'original'},endpoints,probe)
        module.require_physical_startup(result)
        result.update(panel='fixed10_source_smoke',task_success_evaluation=False,
            source_commit=plan['source_commit'])
    elif row['kind']=='drawer':
        from robots.libero.bounded_oracle import NoPublicOption
        with probe.runtime(row['case'],endpoints,args.output/'episode',domain='original') as (facade,adapter,policy,timings):
            adapter.allow_vla=False
            common,common_ref=probe.save_checkpoint(facade,adapter,policy,args.output/'private_common.pkl')
            arms=[]
            for arm in ('nudge','guarded'):
                probe.restore_checkpoint(facade,adapter,policy,common)
                adapter.guarded_move_v1=arm=='guarded'
                trace=[];started=time.perf_counter()
                initial=probe.snapshot_digest(facade.snapshot())
                while len(trace)<160 and not (adapter.p.env.terminated or adapter.p.env.truncated):
                    request=adapter.request(k=4)
                    try: decision=policy.choose(request)
                    except NoPublicOption: break
                    before=len(adapter.details)
                    receipts=adapter.execute(request,decision)
                    trace.append({'request':request,'decision':decision,'receipts':receipts,'details':adapter.details[before:]})
                    with (args.output/(arm+'_choices.jsonl')).open('a') as stream:
                        stream.write(json.dumps(trace[-1],default=str)+'\n')
                    if any(r['skill'] in {'finish','ask_help'} for r in receipts):break
                    if args.startup and any(r['steps_used']>0 for r in receipts):break
                arms.append({'arm':arm,'success':bool(facade.goal_status()['done']),'decisions':len(trace),
                    'sim_steps':adapter.p.env.execution_budget()['used_sim_steps'],
                    'wall_s':time.perf_counter()-started,'initial_physics_sha256':initial,
                    'max_actions_per_decision':max((len(r['receipts']) for r in trace),default=0)})
            result={'case':row['case'],'arms':arms,'common':common_ref,
                'status':'startup_physical' if args.startup else 'physical_result',
                'sim_steps':sum(a['sim_steps'] for a in arms),
                'timings':timings.summary(time.perf_counter()-timings.started),'training':False}
    else:
        from scripts.probe_bounded_hybrid_repair import restore_original_subtask
        from rpent.skill_package.contract import legal_after
        saved=row['position'];case=row['case']
        with probe.runtime(case,endpoints,args.output/'episode',domain='original') as (facade,adapter,policy,timings):
            adapter.allow_vla=False
            restored=restore_original_subtask(facade,adapter,policy,
                {'physics':saved['snapshot'],'annotation':saved['annotation_state']})
            request=adapter.request(k=4)
            common,common_ref=probe.save_checkpoint(facade,adapter,policy,args.output/'private_common.pkl',request)
            specs,unsupported=probe.split_subtasks(facade.goal_status()['goals'],adapter.ex.instruction)
            source_id=saved['candidate']['parameters']['anchor_id']
            spec=move_subtask(probe,facade,adapter,policy,specs,source_id)
            arms=[]
            for arm in ('default','original_variant'):
                directory=args.output/arm;directory.mkdir()
                probe.restore_checkpoint(facade,adapter,policy,common)
                current=copy.deepcopy(request)
                if arm=='default':
                    candidate=next((c for c in current['candidates'] if c['skill']=='move_to'
                        and c['parameters']=={'anchor_id':source_id}),None)
                else:
                    candidate=adapter._candidate('move_to',saved['candidate']['parameters'])
                    if candidate is not None:current['candidates'].append(candidate)
                adapter.latest_request=current
                initial=probe.snapshot_digest(facade.snapshot());started=time.perf_counter()
                if candidate is None or candidate['id'] not in legal_after(current,[]):
                    arms.append({'arm':arm,'status':'public_option_unavailable','success':None,
                        'initial_physics_sha256':initial});continue
                decision={key:current[key] for key in ('schema_version','observation_id','revision')}
                decision.update(kind='decision',candidate_ids=[candidate['id']])
                receipts=adapter.execute(current,decision)
                write(directory/'first_action.json',{'request':current,'decision':decision,'receipts':receipts,
                    'execution_details':adapter.details})
                continuation=None
                if spec is not None and not args.startup:
                    successor=adapter.request(k=4)
                    continuation,_=probe.trial(facade,adapter,policy,timings,spec,'self',
                        11400000+args.worker*1000,directory/'continuation',successor,decision_limit=159)
                arms.append({'arm':arm,'status':'physical_result','initial_physics_sha256':initial,
                    'success':continuation['success'] if continuation else None,
                    'first_receipts':receipts,'continuation':continuation,'wall_s':time.perf_counter()-started})
            result={'position':saved,'restoration':restored,'common_state':common_ref,'subtask':spec,
                'unsupported':unsupported,'arms':arms,'training':False,
                'status':'startup_physical' if args.startup else 'physical_result'}
    write(args.output/'summary.json',result)
    if args.startup:
        # Real requests, not imports, are required. Native completion is also
        # a physical result, never a reason to forge a successful receipt.
        if physical_steps(result) <= 0:
            raise RuntimeError('startup produced no physical execution evidence')
    return 0


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source',type=Path,required=True)
    p.add_argument('--manifest',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--worker',type=int)
    p.add_argument('--startup',action='store_true')
    p.add_argument('--startup-only',action='store_true')
    p.add_argument('--preflight',action='store_true')
    p.add_argument('--episode-concurrency',type=int,default=1)
    args=p.parse_args();args.source=args.source.resolve(strict=True)
    args.manifest=args.manifest.resolve(strict=True);sys.path.insert(0,str(args.source))
    plan=json.loads(args.manifest.read_bytes())
    if not 1 <= args.episode_concurrency <= 8:raise ValueError('episode concurrency must be1..8')
    if plan['training'] or plan['schema_version']!='bounded-skills/6':raise ValueError('wrong evaluation registration')
    if args.worker is not None:return worker(args,plan)
    for row in plan['jobs']:
        if row.get('kind') in {'layout_pilot', 'layout_collect'}:
            from coordination.bounded_skills_20261016.scripts.run_own_layout_pi_pilot_20261022 import validate_job
            validate_job({**row, 'kind': 'layout_pilot'}, plan)
        for key in ('bddl','grasp_measurement_calibration'):
            if key in row['case']:checked(row['case'][key])
        if 'manifest' in row:checked(row['manifest'])
        if row.get('kind') == 'd2_replay':
            for key in ('parent_summary', 'parent_initial'):
                checked(row[key])
        if 'position' in row:
            for key in ('snapshot','annotation_state'):checked(row['position'][key])
    if args.preflight:
        print(json.dumps({'preflight':'passed','jobs':len(plan['jobs'])}));return 0
    os.environ['PYTHONPATH']=str(args.source);os.chdir(args.source)
    helper=hooks(args.source);helper.bootstrap_source('d2')
    from scripts.probe_bounded_feasibility import services
    args.output.mkdir(parents=True,exist_ok=True)
    service_args=SimpleNamespace(source=args.source,output=args.output,
        sam3_entry=Path(plan['sam_entry']['path']))
    checked(plan['sam_entry'])
    with helper.owned_services(service_args,services,vla=True) as endpoints:
        pending=[]
        for index,row in enumerate(plan['jobs']):
            directory=args.output/f'case{index:03d}'
            closed=args.output/f'closed_{index:03d}.json'
            prior=[directory/'summary.json',*args.output.glob(f'case{index:03d}_attempt*/summary.json')]
            completed=next((path for path in prior if path.exists()),None)
            if closed.exists() or completed is not None:
                if not closed.exists():write(closed,{'summary':str(completed)})
                continue
            if directory.exists():
                attempt=1
                while (args.output/f'case{index:03d}_attempt{attempt}').exists():attempt+=1
                directory=args.output/f'case{index:03d}_attempt{attempt}'
            pending.append((index,directory,closed))
        if not pending:return 0
        startup=args.output/f'startup_{time.time_ns()}';startup.mkdir()
        write(startup/'assignment.json',{k+'_url':v._base_url for k,v in endpoints.items()})
        command=[sys.executable,str(Path(__file__).resolve()),'--source',str(args.source),
            '--manifest',str(args.manifest),'--output',str(startup),'--worker',str(pending[0][0]),'--startup']
        with (startup/'worker.log').open('x') as stream:
            subprocess.run(command,stdout=stream,stderr=subprocess.STDOUT,check=True)
        if args.startup_only:
            print(json.dumps({'startup':'physical_passed','proof':str(startup/'summary.json')}),flush=True)
            return 0

        def run_case(item):
            index,directory,closed=item
            directory.mkdir()
            write(directory/'assignment.json',{k+'_url':v._base_url for k,v in endpoints.items()})
            command=[sys.executable,str(Path(__file__).resolve()),'--source',str(args.source),
                '--manifest',str(args.manifest),'--output',str(directory),'--worker',str(index)]
            with (directory/'worker.log').open('x') as stream:
                subprocess.run(command,stdout=stream,stderr=subprocess.STDOUT,check=True)
            write(closed,{'summary':str(directory/'summary.json'),
                'sha256':hashlib.sha256((directory/'summary.json').read_bytes()).hexdigest()})
            print(json.dumps({'index':index,'closed':str(directory/'summary.json')}),flush=True)
        # Threads only own child-process launch/wait; each episode uses a
        # fresh Python process, RNG, EGL context and IK state. Candidate
        # planning inside an episode remains serial, as in the N8 study.
        waiting=iter(pending)
        with ThreadPoolExecutor(max_workers=args.episode_concurrency) as pool:
            active={pool.submit(run_case,item) for item in
                [next(waiting,None) for _ in range(args.episode_concurrency)] if item is not None}
            while active:
                done,active=wait(active,return_when=FIRST_COMPLETED)
                for future in done:future.result()
                for _ in done:
                    item=next(waiting,None)
                    if item is not None:active.add(pool.submit(run_case,item))
    return 0


if __name__=='__main__':raise SystemExit(main())
