"""Private D2 path selection over already measured, isolated branches."""
from __future__ import annotations

import copy
import time


def select_complete_path(summary):
    """Keep locally chosen prefixes and compare their native-complete calls.

    Endpoint native completion is independent of the local subtask verdict.
    A pick may finish by placing the object, with no sustained hold remaining.
    Keep its local verdict and its native-complete path. Conditional products remain sampled
    estimates; the chosen path still needs an independent physical replay.
    """
    prefix, alternatives, prefix_rate = [], [], 1.
    native_fallback = not summary.get('subtasks')
    for row in summary.get('subtasks', []):
        self_trials = [t for t in row['trials'] if t.get('method') == 'self']
        if len(self_trials) == 1 and self_trials[0].get('native_task_success') is True:
            alternatives.append({'choices': copy.deepcopy([*prefix,
                {'subtask': row['subtask'], 'method': 'self'}]),
                'conditional_rate': prefix_rate, 'sampled_native_success': True,
                'terminal_trial_successes': 1, 'terminal_trial_n': 1,
                'terminal_subtask_id': row['subtask']['id']})
        for group in row['selection'].get('variant_groups', []):
            variant = group['variant']
            trials = [trial for trial in row['trials'] if trial.get('vla_variant') == variant]
            # Historical records certify native completion only when that was
            # their explicit outcome contract. Missing endpoint fields stay unknown.
            native = [t.get('native_task_success',
                t['success'] if variant['parameters'].get('mode') == 'task'
                and t.get('truth_source') == 'unchanged_native_task_completion' else None)
                for t in trials]
            if len(trials) != 3 or any(type(value) is not bool for value in native):
                continue
            successes = sum(native)
            if successes:
                terminal = {'subtask': row['subtask'], 'method': 'call_vla',
                    'vla_parameters': variant['parameters'], 'vla_variant': variant['name']}
                alternatives.append({'choices': copy.deepcopy([*prefix, terminal]),
                    'conditional_rate': prefix_rate*successes/3,
                    'sampled_native_success': True, 'terminal_trial_successes': successes,
                    'terminal_trial_n': 3, 'terminal_subtask_id': row['subtask']['id']})
        selection = row['selection']
        if selection['method'] is None:
            native_fallback = True
            break
        choice = {'subtask': row['subtask'], 'method': selection['method']}
        if 'vla_parameters' in selection:
            choice.update(vla_parameters=selection['vla_parameters'], vla_variant=selection['vla_variant'])
        prefix.append(copy.deepcopy(choice))
        prefix_rate *= selection['rate']
        if selection['status'] == 'both_failed':
            break
    local_complete = summary.get('sampled_envelope_native_success')
    local_rate = summary.get('conditional_rate_product')
    selected = {'kind': 'native_instruction' if native_fallback else 'selected_path',
        'choices': prefix, 'conditional_rate': local_rate,
        'sampled_native_success': local_complete, 'reason': 'original_local_path'}
    if alternatives:
        best = max(alternatives, key=lambda path: path['conditional_rate'])
        if (not local_complete or local_rate is None or best['conditional_rate'] > local_rate):
            selected = dict(best, kind='selected_path', reason='measured_native_complete_path')
    return {**selected, 'native_complete_alternatives': alternatives,
        'source_sampled_envelope_native_success': local_complete,
        'source_conditional_rate_product': local_rate,
        'scope': 'sampled prefixes plus native-complete calls; independent replay required; evaluation only'}


def replay_complete_path(probe, facade, adapter, policy, timings, selection, seed_base, output):
    """Execute the chosen complete path once, with new policy seeds."""
    output.mkdir()
    started = time.perf_counter()
    rows, decisions = [], 0
    if selection['kind'] == 'native_instruction':
        rows.append(probe.native_instruction_replay(facade, adapter, policy, timings,
            output/'native_instruction', seed_base))
    else:
        for index, choice in enumerate(selection['choices']):
            with timings.measure('planning.request'):
                request = adapter.request(k=4)
            row, endpoint = probe.trial(facade, adapter, policy, timings, choice['subtask'],
                choice['method'], seed_base+10000*index, output/f'subtask{index:02d}', request,
                decision_limit=max(0, 160-decisions),
                **({'vla_parameters': choice['vla_parameters']} if 'vla_parameters' in choice else {}))
            row['selected_vla_variant'] = choice.get('vla_variant')
            rows.append(row)
            decisions += row['decisions']
            probe.restore_checkpoint(facade, adapter, policy, endpoint)
            if row['success'] is not True:
                break
    return {'status': 'physical_result', 'actual_full_replay_success': bool(facade.goal_status()['done']),
        'full_replay': rows, 'independent_replay_wall_s': time.perf_counter()-started,
        'independent_replay_wall_scope': 'after initial-state restoration; planning, execution and private metrology; no fork sampling or simulator construction',
        'sampled_envelope_native_success': selection['sampled_native_success'],
        'conditional_rate_product': selection['conditional_rate'], 'path_selection': selection,
        'training': False, 'confirmation': False}
