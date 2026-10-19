"""Registered same-state handoff/stop diagnostics, separate from D2 whole cases."""
from __future__ import annotations

import json
import pickle
import time
from pathlib import Path

from rpent.skill_package.vla import VLABudget
from scripts import probe_bounded_hybrid_d2 as probe
from scripts.probe_bounded_motion import write


def validate_plan(plan):
    from robots.libero.bounded_hybrid_diagnostic import validate_d2_episode
    if (plan.get('evaluation') != 'hybrid_repair' or plan['training'] or plan['confirmation']
            or not plan['cases']):
        raise ValueError('expected an isolated development repair plan')
    for case in plan['cases']:
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


def run_trial(facade, adapter, policy, timings, spec, method, seed, output, request):
    start_event, started = len(timings.events), time.perf_counter()
    result, endpoint = probe.trial(facade, adapter, policy, timings, spec, method,
        seed, output, request)
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
            spec, request = old['subtask'], saved['request']
            result, endpoint = run_trial(facade, adapter, policy, timings, spec, 'call_vla',
                old['trial_seed'], output / 'replay', request)
            old_execution, new_execution = vla_execution(old), vla_execution(result)
            old_trace = old_execution['trace'] if old_execution else []
            new_trace = new_execution['trace'] if new_execution else []
            common = min(len(old_trace), len(new_trace))
            result['paired_replay'] = {'old_summary': diagnostic['old_summary'],
                'same_initial_physics': result['initial_physics_sha256'] == old['initial_physics_sha256'],
                'same_initial_request': result['request_sha256'] == old['request_sha256'],
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
            matches = [s for s in subtask_plan if s['mode'] == diagnostic['subtask_mode']]
            if not matches:
                report = {'case':case, 'status':'oracle_rule_uncovered', 'unsupported':unsupported,
                    'reason':'requested_original_subtask_not_in_existing_progress_rules', 'training':False}
                write(output / 'summary.json', report)
                return report
            spec = matches[0]
            adapter.vla_budget = budget
            request = adapter.request(k=4)
            saved, _ = probe.save_checkpoint(facade, adapter, policy, output / 'private_branchpoint.pkl', request)
            trials = []
            methods = ['call_vla'] if startup else ['self', 'call_vla', 'call_vla', 'call_vla']
            for index, method in enumerate(methods):
                probe.restore_checkpoint(facade, adapter, policy, saved)
                adapter.vla_budget = budget
                row, _ = run_trial(facade, adapter, policy, timings, spec, method,
                    diagnostic['trial_seed_base']+index*1000, output / f'{method}_{index}', request)
                trials.append(row)
            continuation = None
        else:
            raise ValueError('unsupported repair diagnostic')
        report = {'case':case, 'status':'physical_result', 'evaluation':'hybrid_repair',
            'scope':'subtask diagnostic; not a D2 whole-episode score', 'trials':trials,
            'continuation':continuation, 'source_commit':plan['source_commit'],
            'training':False, 'confirmation':False, 'actual_full_replay_success':None}
        write(output / 'summary.json', report)
        return report
