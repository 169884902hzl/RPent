"""Same full initial states, native feedback, and persistent 40-decision loops."""
import argparse
import copy
import importlib.util
import json
import os
from pathlib import Path
import pickle
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from types import SimpleNamespace


def reference(path):
    import hashlib
    path = Path(path)
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def checked(value):
    path = Path(value['path'])
    assert reference(path)['sha256'] == value['sha256'], path
    return path


def write(path, value):
    path = Path(path)
    with path.open('x') as stream:
        json.dump(value, stream, indent=2, default=lambda x: x.tolist() if hasattr(x, 'tolist') else str(x))


def module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec); spec.loader.exec_module(value)
    return value


def worker(args, plan):
    row = plan['jobs'][args.worker]
    domain = row.get('domain', 'original')
    os.environ['LIBERO_TYPE'] = 'pro' if domain == 'd2' else 'standard'
    os.environ['LIBERO_CONFIG_PATH'] = str(checked(row['libero_config']).parent)
    os.environ['LIBERO_GRASP_DIAGNOSTIC_MODELS'] = str(args.output/'private_grasp_models')
    sys.path.insert(0, str(args.source))
    hooks = module(args.source/'coordination/bounded_skills_20261016/scripts/shared_gpu_episodes_20261019.py', 'feedback_hooks')
    hooks.bootstrap_source(domain, evaluation='hybrid_repair'); hooks.install_d2_restore_compatibility()
    from scripts import probe_bounded_hybrid_d2 as probe
    from rpent.utils.rpc.http_rpc import HttpRpcClient
    assignment = json.loads((args.output/'assignment.json').read_bytes())
    endpoints = {key: HttpRpcClient(assignment[key+'_url']) for key in ('sam3', 'vla')}
    episode = args.output/'episode'; episode.mkdir()
    case = row['case']
    from scripts.probe_bounded_hybrid_repair import constructed_original_start
    constructed = constructed_original_start(case, plan) if 'own_layout' in case.get('diagnostic', {}) else None
    with probe.runtime(case, endpoints, episode, domain=domain, constructed_start=constructed) as (facade, adapter, policy, timings):
        if row['kind'] == 'episode':
            result = run_episode(args, plan, row, probe, facade, adapter, policy, timings)
        else:
            result = run_contact_panel(args, plan, row, probe, facade, adapter, policy, timings)
    write(args.output/'summary.json', result)


def run_episode(args, plan, row, probe, facade, adapter, policy, timings):
    from robots.libero.bounded_success_loop import enable, choose, native_success
    from rpent.skill_package.feedback import TaskAlreadySucceeded
    from rpent.skill_package.vla import VLABudget
    saved = pickle.loads(checked(row['initial_snapshot']).read_bytes())
    probe.restore_checkpoint(facade, adapter, policy, saved)
    initial = probe.snapshot_digest(facade.snapshot())
    assert initial == probe.snapshot_digest(saved['physics'])
    arm = row['arm']
    level_b = arm == 'oracle_AB'
    adapter.permissive_preparation_options = row.get('permissive_options', False)
    adapter.adaptive_contact_skills = row.get('adaptive_contact_skills', False)
    adapter.verify_instance_class_v10 = row.get('verify_instance_class', False)
    enable(adapter, facade, level_b=level_b, permissive=row.get('permissive', False))
    adapter.vla_budget = VLABudget(**plan['vla_budget'])
    original_model = adapter.p.model
    seeded = probe.SeededPolicy(original_model, row['policy_seed'], input_ledger=args.output/'vla_inputs.jsonl')
    adapter.p.model = seeded
    original_steps = adapter.p.env.execution_budget()['used_sim_steps']
    records = []
    reason = 'decision_budget'
    started = time.perf_counter()
    with (args.output/'choices.jsonl').open('x') as stream:
        for index in range(40):
            if adapter.p.env.execution_budget()['remaining_sim_steps'] <= 0 or adapter.p.env.truncated:
                reason = 'environment_budget'; break
            try:
                request_started = time.perf_counter()
                request = adapter.request(k=row['k'])
                request_wall = time.perf_counter()-request_started
            except TaskAlreadySucceeded:
                reason = 'native_task_success_before_decision'; break
            decision_started = time.perf_counter()
            decision, selection = choose(probe, facade, adapter, policy, request,
                only_pi=arm == 'pi_A', measured_path=row.get('oracle_measured_path', []))
            decision_wall = time.perf_counter()-decision_started
            if decision is None:
                reason = 'no_legal_option'; break
            detail_start = len(adapter.details)
            execution_started = time.perf_counter()
            receipts = adapter.execute(request, decision)
            execution_wall = time.perf_counter()-execution_started
            record = {'index': index, 'request': request, 'decision': decision,
                'selector': selection, 'receipts': receipts,
                'request_wall_s': request_wall, 'decision_wall_s': decision_wall,
                'execution_wall_s': execution_wall, 'details': adapter.details[detail_start:]}
            stream.write(json.dumps(record, default=lambda x:x.tolist() if hasattr(x, 'tolist') else str(x))+'\n')
            stream.flush(); records.append({k:v for k,v in record.items() if k not in {'request','details'}})
            # Every failure/no-progress returns here; neither receipts nor
            # private subtask verdicts terminate the world or reset it.
            if adapter.p.env.terminated:
                reason = 'native_success_during_execution'; break
    success = native_success(facade)
    wall = time.perf_counter()-started
    endpoint = args.output/'private_endpoint.pkl'; endpoint.write_bytes(pickle.dumps(facade.snapshot(), protocol=5))
    return {'case': row['case'], 'domain': row['domain'], 'arm_id': row['arm_id'],
        'arm': arm, 'status': 'physical_result', 'success': success,
        'decisions': len(records), 'sim_steps': adapter.p.env.execution_budget()['used_sim_steps']-original_steps,
        'wall_s': wall, 'stop_reason': reason, 'initial_physics_sha256': initial,
        'initial_snapshot': row['initial_snapshot'], 'endpoint': reference(endpoint),
        'feedback': {'task_success': True, 'subgoal_status': level_b},
        'native_success_reads_before_decision': adapter.success_feedback.reads,
        'budget': {'decisions': 40, 'sim_steps': 10000, 'recovery_budget': None},
        'policy_seed': row['policy_seed'], 'source_commit': plan['source_commit'],
        'choices': reference(args.output/'choices.jsonl'), 'permissive_measured_anchor': row.get('permissive', False),
        'decision_records': records, 'training': False, 'confirmation': False,
        'oracle_kind': None if arm == 'pi_A' else 'private_rule_selector_with_prior_measured_method_preferences',
        'oracle_not_exhaustive_mathematical_bound': True,
        'vla_inference_calls': seeded.calls, 'human_available': False}


def run_contact_panel(args, plan, row, probe, facade, adapter, policy, timings):
    import numpy as np
    from scripts.probe_bounded_hybrid_repair import restore_original_subtask
    from robots.libero.bounded_success_loop import enable, native_success
    from robots.libero.bounded_vla_staged import prepare
    from robots.libero.bounded_adaptive_contact import run as adaptive_contact
    from robots.libero.bounded_motion import public_control
    from rpent.skill_package.vla import VLABudget
    from rpent.skill_package.feedback import TaskAlreadySucceeded
    from rpent.skill_package.contract import legal_after

    case = row['case']; diagnostic = case['diagnostic']
    restored = restore_original_subtask(facade, adapter, policy, row['saved_start'])
    adapter.vla_options_v2 = True
    adapter.vla_budget = VLABudget(**diagnostic['budget'])
    adapter._incremental_touched.update(adapter.scene.entities)
    adapter.refresh()
    if row.get('common_checkpoint'):
        common_ref = row['common_checkpoint']
        common = pickle.loads(checked(common_ref).read_bytes())
        probe.restore_checkpoint(facade, adapter, policy, common)
    else:
        common, common_ref = probe.save_checkpoint(facade, adapter, policy, args.output/'private_common.pkl')
    expected = probe.snapshot_digest(common['physics'])
    specs, unsupported = probe.split_subtasks(facade.goal_status()['goals'], adapter.ex.instruction)
    spec = next((s for s in specs if s['goal_index'] == diagnostic['goal_index']
                 and s['mode'] == diagnostic['subtask_mode']), None)
    if spec is None:
        return {'case':case,'status':'unknown','reason':'registered_subtask_uncovered',
                'unsupported':unsupported,'trials':[],'training':False}
    trials = []
    original_model = adapter.p.model
    for repeat in range(row.get('repeats', 3)):
        for arm in (('screened', 'permissive') if row['kind'] == 'n2' else ('adaptive_contact',)):
            probe.restore_checkpoint(facade, adapter, policy, common)
            assert probe.snapshot_digest(facade.snapshot()) == expected
            adapter.permissive_preparation_options = row.get('permissive_options', False)
            adapter.adaptive_contact_skills = row.get('permissive_options', False)
            enable(adapter, facade, permissive=arm == 'permissive')
            source, target = probe.bind_subtask(policy, adapter, spec)
            if source is None and spec['mode'] in {'open', 'close'}:
                from robots.libero.bounded_adaptive_contact import unique_handle_parent
                source = unique_handle_parent(adapter.scene.entities, spec['mode'])
                if source is not None:
                    policy.binding._bindings[spec['source_symbol']] = source.id
            if source is None or spec['target_symbol'] and target is None:
                trials.append({'arm':arm,'repeat':repeat,'status':'unknown','reason':'public_binding_missing'})
                continue
            directory = args.output/f'{arm}_{repeat}'; directory.mkdir()
            adapter.p.model = probe.SeededPolicy(original_model, row['policy_seed']+repeat*1000,
                input_ledger=directory/'vla_inputs.jsonl') if row['kind']=='n2' else adapter.p.model
            started = time.perf_counter()
            before_steps = adapter.p.env.execution_budget()['used_sim_steps']
            parameters = {'anchor_id':source.id,'mode':spec['mode'], 'preparation':'measured_anchor'}
            if target is not None:parameters['target_id'] = target.id
            before = facade.grasp_contacts()
            native_contacts = []
            original_step = adapter.p._step_env
            def metrology_step(action):
                original_step(action)
                native_contacts.append(facade.grasp_contacts())
            adapter.p._step_env = metrology_step
            try:
                try:adapter.request(k=4)
                except TaskAlreadySucceeded:pass
                if row['kind'] == 'n2':
                    detail = prepare(adapter, parameters)
                else:
                    detail = execute_new_contact(probe, facade, adapter, policy, spec, source, target)
            finally:
                adapter.p._step_env = original_step
            after = facade.grasp_contacts()
            metric = contact_metrics(before, after, native_contacts, spec['source_symbol'])
            policy_result = None
            if row['kind']=='n2' and detail.get('success') and not (adapter.p.env.terminated or adapter.p.env.truncated):
                policy_result = adapter.call_vla({**parameters,'preparation':'in_place'})
            status = facade.goal_status()
            record = {'arm':arm,'repeat':repeat,'status':'physical_result','complete_initial_sha256':expected,
                'success':bool(status['satisfied'][spec['goal_index']]),'native_success':native_success(facade),
                'sim_steps':adapter.p.env.execution_budget()['used_sim_steps']-before_steps,
                'wall_s':time.perf_counter()-started,'preparation_or_skill':detail,
                'policy_result':policy_result,'metrics':metric,'private_truth_used_for_control':False}
            write(directory/'result.json',record)
            trials.append({key:record[key] for key in ('arm','repeat','status','complete_initial_sha256',
                'success','native_success','sim_steps','wall_s','metrics')} | {
                'stop_reason':detail.get('stop_reason', detail.get('reason')),
                'endpoint_error_m':detail.get('endpoint_error_m'),'record':reference(directory/'result.json')})
    return {'case':case,'status':'physical_result','kind':row['kind'],'trials':trials,
        'common':common_ref,'source_commit':plan['source_commit'],'training':False,
        'source_split':'train' if row['kind']=='skill' else 'development_panel',
        'confirmation':False,'PRO':False,'D2':False}


def execute_new_contact(probe, facade, adapter, policy, spec, source, target):
    """Reuse public approach/gripper skills before the new feedback motion."""
    import numpy as np
    from robots.libero.bounded_adaptive_contact import run
    from robots.libero.bounded_oracle import NoPublicOption
    from rpent.skill_package.feedback import TaskAlreadySucceeded
    adapter.allow_vla = False
    setup = []
    if getattr(adapter, 'permissive_preparation_options', False):
        request = adapter.request(k=1)
        options = [c for c in request['candidates'] if c['parameters'].get('preparation') == 'measured_anchor_permissive'
            and c['skill'] == ('push_to' if spec['mode'] == 'push' else 'open_close_articulated')
            and c['parameters'].get('anchor_id') == source.id]
        if spec['mode'] == 'push':
            options = [c for c in options if c['parameters'].get('target_id') == target.id]
        else:
            contact = adapter.plans.get(source.id, {})
            normal = contact.get('surface_measurement', {}).get('normal_xyz')
            if normal is None:
                normal = contact.get('handle_measurement', {}).get('pose', {}).get('approach_normal_xyz', [0., -1., 0.])
            axis = int(np.argmax(np.abs(normal)))
            sign = int((1 if spec['mode'] == 'open' else -1)*np.sign(normal[axis]))
            options = [c for c in options if c['parameters'].get('axis') == 'xyz'[axis] and c['parameters'].get('direction') == sign]
        if not options:
            return {'success': False, 'steps_used': 0, 'stop_reason': 'public_composite_contact_unavailable', 'setup': []}
        choice = {'schema_version': request['schema_version'], 'kind': 'decision', 'revision': request['revision'],
            'observation_id': request['observation_id'], 'candidate_ids': [options[0]['id']]}
        index = len(adapter.details)
        receipts = adapter.execute(request, choice)
        physical = adapter.details[index:]
        detail = next((d['execution'] for d in physical if d.get('candidate_id') == options[0]['id']), {})
        return {**detail, 'selected_request': request, 'selected_decision': choice, 'selected_receipts': receipts}
    for _ in range(8):
        try:request = adapter.request(k=1)
        except TaskAlreadySucceeded:return {'success':True,'stop_reason':'native_success','setup':setup}
        try:decision = policy.choose(request)
        except NoPublicOption:return {'success':False,'stop_reason':'no_public_contact_option','setup':setup}
        c = next(c for c in request['candidates'] if c['id'] == decision['candidate_ids'][0])
        if c['skill'] in {'guarded_move','nudge'}:
            axis = 'xyz'.index(c['parameters']['axis'])
            direction = np.zeros(3)
            direction[axis] = c['parameters'].get('direction', np.sign(c['parameters'].get('distance_m', 1.)))
            key = c['parameters'].get('anchor_id') or adapter.active or source.id
            parameters = {'anchor_id':key,'direction':direction.tolist()}
            if target is not None:parameters['target_id'] = target.id
            detail = run(adapter, parameters, push=spec['mode']=='push')
            return {**detail,'setup':setup,'skill':'push_to' if spec['mode']=='push' else 'open_close_articulated',
                'parameters':parameters}
        receipts = adapter.execute(request,decision);setup.extend(receipts)
        if any(r['outcome'] != 'success' for r in receipts):
            return {'success':False,'stop_reason':'contact_setup_failed','setup':setup}
    return {'success':False,'stop_reason':'contact_setup_decision_budget','setup':setup}


def contact_metrics(before, after, samples, source_symbol):
    import numpy as np
    def hand_pairs(contacts):
        result = {}
        for row in contacts:
            a,b = row['geom1'] or '',row['geom2'] or ''
            if ('gripper' in a)==('gripper' in b):continue
            hand,other = (a,b) if 'gripper' in a else (b,a)
            if other.startswith(('robot','gripper')):continue
            pair=hand+' / '+other
            result[pair]=min(result.get(pair,1.),row['distance_m'])
        return result
    baseline=hand_pairs(before['contacts']);depths={}
    for sample in samples:
        for pair,distance in hand_pairs(sample['contacts']).items():
            if distance < min(-1e-6,baseline.get(pair,0.)-1e-6):
                depths[pair]=min(depths.get(pair,1.),distance)
    movement={}
    for name,obj in before['objects'].items():
        current=after['objects'].get(name)
        if name!=source_symbol and current:
            movement[name]=float(np.linalg.norm(np.asarray(current['xyz'])-obj['xyz']))
    return {'new_or_deeper_contacts_gt_1um':depths,
        'new_or_deeper_contacts_gt_1mm':{k:v for k,v in depths.items()
            if v < min(-.001,baseline.get(k,0.)-.001)},
        'non_target_object_displacement_m':movement,
        'max_non_target_displacement_m':max(movement.values(),default=0.),
        'samples':len(samples),'position_reference':'body_origin_displacement',
        'metrology_only_not_read_by_controller':True}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--worker', type=int)
    args = parser.parse_args(); args.source = args.source.resolve()
    sys.path.insert(0, str(args.source)); plan = json.loads(args.manifest.read_bytes())
    if args.worker is not None:
        return worker(args, plan)
    args.output.mkdir(parents=True, exist_ok=True)
    helper = module(args.source/'coordination/bounded_skills_20261016/scripts/shared_gpu_episodes_20261019.py', 'launch_hooks')
    helper.bootstrap_source('d2')
    from scripts.probe_bounded_feasibility import services
    service_args = SimpleNamespace(source=args.source, output=args.output, sam3_entry=checked(plan['sam_entry']))
    os.environ['PYTHONPATH'] = str(args.source); os.chdir(args.source)
    with helper.owned_services(service_args, services, vla=True) as endpoints:
        def run(index):
            closed = args.output/f'closed_{index:03d}.json'
            if closed.exists():
                checked(json.loads(closed.read_bytes())); return
            directory = args.output/f'case{index:03d}'
            if directory.exists():
                directory.rename(args.output/f'interrupted_{index:03d}_{time.time_ns()}')
            directory.mkdir()
            write(directory/'assignment.json', {key+'_url':value._base_url for key,value in endpoints.items()})
            command = [sys.executable, str(Path(__file__).resolve()), '--source', str(args.source),
                       '--manifest', str(args.manifest), '--output', str(directory), '--worker', str(index)]
            with (directory/'worker.log').open('x') as stream:
                subprocess.run(command, stdout=stream, stderr=subprocess.STDOUT, check=True)
            write(closed, reference(directory/'summary.json'))
            print(json.dumps({'closed':index}), flush=True)
        with ThreadPoolExecutor(max_workers=8) as pool:
            for future in as_completed([pool.submit(run, i) for i in range(len(plan['jobs']))]):
                future.result()


if __name__ == '__main__':
    main()
