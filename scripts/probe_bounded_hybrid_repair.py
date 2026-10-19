"""Registered same-state handoff/stop diagnostics, separate from D2 whole cases."""
from __future__ import annotations

import copy
import json
import pickle
import time
from pathlib import Path

from rpent.skill_package.vla import VLABudget
from scripts import probe_bounded_hybrid_d2 as probe
from scripts.probe_bounded_motion import write


def migrate_replay_header(adapter, request):
    """Admit the unchanged v3 catalog for a v4 observation-scope diagnostic.

    V4 only extends the mode enum; all original fields retain their meaning.
    This explicitly changes the version header, never poses/options/screens.
    """
    from rpent.skill_package import VERSION

    if request['schema_version'] != 'bounded-skills/3' or VERSION != 'bounded-skills/4':
        raise ValueError('only the registered public v3-to-v4 header migration is supported')
    request = copy.deepcopy(request)
    cached = copy.deepcopy(adapter.latest_request)
    if request != cached:
        raise ValueError('saved request differs from its restored cache')
    request['schema_version'] = cached['schema_version'] = VERSION
    adapter.latest_request = cached
    return request


def validate_plan(plan):
    from robots.libero.bounded_hybrid_diagnostic import validate_d2_episode
    if (plan.get('evaluation') != 'hybrid_repair' or plan['training'] or plan['confirmation']
            or not plan['cases']):
        raise ValueError('expected an isolated development repair plan')
    for case in plan['cases']:
        probe.load_public_gripper_calibration(case['grasp_measurement_calibration'])
        diagnostic = case['diagnostic']
        if diagnostic['domain'] == 'd2':
            validate_d2_episode(case['episode'])
        elif diagnostic['domain'] == 'original':
            ep = case['episode']
            suites = {'libero_spatial': 10, 'libero_object': 10, 'libero_goal': 10,
                'libero_10': 10, 'libero_90': 90}
            if ep['suite'] not in suites or not 0 <= ep['task'] < suites[ep['suite']]:
                raise ValueError('original fork requires an original40/90 task')
        else:
            raise ValueError('unregistered diagnostic domain')
        VLABudget(**diagnostic['budget'])
        for key in ('old_summary', 'branchpoint'):
            if key in diagnostic and probe.reference(diagnostic[key]['path']) != diagnostic[key]:
                raise ValueError('registered replay input changed')


def first_self_chunk(facade, adapter, policy, spec, output):
    """Actually continue with bounded skills after the VLA/control handoff."""
    from robots.libero.bounded_oracle import NoPublicOption
    from rpent.skill_package.contract import legal_after
    started = time.perf_counter()
    before = adapter.p.env.execution_budget()['used_sim_steps']
    request = adapter.request(k=4)
    write(output / 'first_self_request.json', request)
    original = policy.rpc
    policy.rpc = probe.SubtaskRPC(facade, spec)
    try:
        try:
            decision = policy.choose(request)
        except NoPublicOption as exc:
            return {'request_generated': True, 'legal_n': len(legal_after(request, [])),
                'status': 'no_public_option', 'message': str(exc), 'wall_s': time.perf_counter()-started}
        if any(next(c for c in request['candidates'] if c['id'] == cid)['skill'] == 'call_vla'
               for cid in decision['candidate_ids']):
            raise ValueError('self continuation must use bounded skills')
        receipts = adapter.execute(request, decision)
        result = {'request_generated': True, 'legal_n': len(legal_after(request, [])),
            'status': 'executed', 'decision': decision, 'receipts': receipts,
            'sim_steps': adapter.p.env.execution_budget()['used_sim_steps']-before,
            'wall_s': time.perf_counter()-started}
        write(output / 'first_self_chunk.json', result)
        return result
    finally:
        policy.rpc = original


def run_trial(facade, adapter, policy, timings, spec, method, seed, output, request, *, decision_limit=160):
    start_event, started = len(timings.events), time.perf_counter()
    result, endpoint = probe.trial(facade, adapter, policy, timings, spec, method,
        seed, output, request, decision_limit=decision_limit)
    result['wall_time_breakdown'] = timings.summary(time.perf_counter()-started, start_event=start_event)
    write(output / 'summary.json', result)
    return result, endpoint


def vla_execution(result):
    for line in Path(result['choices']['path']).open():
        for detail in json.loads(line)['execution_details']:
            execution = detail.get('execution', {})
            if 'skill_stop_reason' in execution:
                return execution
    return None


def evaluate_case(case, endpoints, output, plan, *, startup=False):
    output.mkdir()
    diagnostic = case['diagnostic']
    budget = VLABudget(**diagnostic['budget'])
    with probe.runtime(case, endpoints, output, domain=diagnostic['domain']) as (facade, adapter, policy, timings):
        if diagnostic['kind'] == 'replay':
            old = json.loads(Path(diagnostic['old_summary']['path']).read_bytes())
            saved = pickle.loads(Path(diagnostic['branchpoint']['path']).read_bytes())
            probe.restore_checkpoint(facade, adapter, policy, saved)
            adapter.vla_budget = budget
            adapter.targeted_vla_measurement_v1 = diagnostic.get('targeted_vla_measurement_v1', False)
            spec, request = old['subtask'], saved['request']
            if diagnostic.get('migrate_v3_header_to_v4', False):
                request = migrate_replay_header(adapter, request)
            result, endpoint = run_trial(facade, adapter, policy, timings, spec, 'call_vla',
                old['trial_seed'], output / 'replay', request)
            old_execution, new_execution = vla_execution(old), vla_execution(result)
            old_trace = old_execution['trace'] if old_execution else []
            new_trace = new_execution['trace'] if new_execution else []
            common = min(len(old_trace), len(new_trace))
            result['paired_replay'] = {'old_summary': diagnostic['old_summary'],
                'same_initial_physics': result['initial_physics_sha256'] == old['initial_physics_sha256'],
                'same_legacy_captured_physics': result['initial_legacy_captured_physics_sha256'] == old['initial_physics_sha256'],
                'historical_observation_phase_available': 'observation_state' in saved['physics']['actuator_state'],
                'same_initial_request': result['request_sha256'] == old['request_sha256'],
                'same_request_except_schema': {k:v for k,v in request.items() if k != 'schema_version'}
                    == {k:v for k,v in saved['request'].items() if k != 'schema_version'},
                'public_request_schema_migration': diagnostic.get('migrate_v3_header_to_v4', False),
                'old_controls':len(old_trace), 'new_controls':len(new_trace),
                'common_controls':common,
                'first_action_mismatch':next((i for i in range(common)
                    if old_trace[i]['action'] != new_trace[i]['action']), None)}
            write(output / 'replay/summary.json', result)
            probe.restore_checkpoint(facade, adapter, policy, endpoint)
            subtask_plan, _ = probe.split_subtasks(facade.goal_status()['goals'], adapter.ex.instruction)
            next_spec = spec
            if result['success'] is True:
                position = next(i for i, value in enumerate(subtask_plan) if value['id'] == spec['id'])
                if position+1 < len(subtask_plan):
                    next_spec = subtask_plan[position+1]
            continuation = (first_self_chunk(facade, adapter, policy, next_spec, output)
                if not (adapter.p.env.terminated or adapter.p.env.truncated) else {'status':'native_stop'})
            trials = [result]
        elif diagnostic['kind'] == 'original_fork':
            subtask_plan, unsupported = probe.split_subtasks(facade.goal_status()['goals'], adapter.ex.instruction)
            matches = [s for s in subtask_plan if s['mode'] == diagnostic['subtask_mode']
                and s['goal_index'] == diagnostic.get('goal_index', 0)]
            if not matches:
                report = {'case':case, 'status':'oracle_rule_uncovered', 'unsupported':unsupported,
                    'reason':'requested_original_subtask_not_in_existing_progress_rules', 'training':False}
                write(output / 'summary.json', report)
                return report
            spec = matches[0]
            adapter.vla_budget = budget
            adapter.targeted_vla_measurement_v1 = diagnostic.get('targeted_vla_measurement_v1', False)
            prefix = []
            prefix_decisions = 0
            position = subtask_plan.index(spec)
            for index, prerequisite in enumerate(subtask_plan[:position]):
                if facade.goal_status()['satisfied'][prerequisite['goal_index']]:
                    continue
                request = adapter.request(k=4)
                row, endpoint = run_trial(facade, adapter, policy, timings, prerequisite, 'self',
                    diagnostic['trial_seed_base']+500000000+1000*index,
                    output/f'prefix_{index:02d}_{prerequisite["mode"]}', request,
                    decision_limit=max(0, 160-prefix_decisions))
                prefix.append(row)
                prefix_decisions += row['decisions']
                probe.restore_checkpoint(facade, adapter, policy, endpoint)
                if row['success'] is not True:
                    report = {'case': case, 'status': 'prefix_not_reached', 'prefix': prefix,
                        'requested_subtask': spec, 'trials': [], 'training': False,
                        'confirmation': False, 'source_commit': plan['source_commit'],
                        'reason': 'bounded_prefix_failed_before_registered_fork'}
                    write(output/'summary.json', report)
                    return report
            request = adapter.request(k=4)
            saved, _ = probe.save_checkpoint(facade, adapter, policy, output / 'private_branchpoint.pkl', request)
            trials = []
            # Trial identities/seeds are fixed independently of scheduling.
            # Diagnose fallback contact before a slow bounded-self branch.
            methods = ([(1, 'call_vla')] if startup else
                [(1, 'call_vla'), (2, 'call_vla'), (3, 'call_vla'), (0, 'self')])
            for index, method in methods:
                probe.restore_checkpoint(facade, adapter, policy, saved)
                adapter.vla_budget = budget
                adapter.targeted_vla_measurement_v1 = diagnostic.get('targeted_vla_measurement_v1', False)
                row, _ = run_trial(facade, adapter, policy, timings, spec, method,
                    diagnostic['trial_seed_base']+index*1000, output / f'{method}_{index}', request,
                    decision_limit=max(0, 160-prefix_decisions))
                trials.append(row)
            continuation = None
        else:
            raise ValueError('unsupported repair diagnostic')
        report = {'case':case, 'status':'physical_result', 'evaluation':'hybrid_repair',
            'scope':'subtask diagnostic; not a D2 whole-episode score', 'trials':trials,
            'continuation':continuation, 'source_commit':plan['source_commit'],
            'training':False, 'confirmation':False, 'actual_full_replay_success':None}
        if diagnostic['kind'] == 'original_fork':
            report['prefix'] = prefix
        write(output / 'summary.json', report)
        return report
