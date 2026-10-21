"""Whole-task completions must survive local subtask ties."""
import copy

from robots.libero.bounded_hybrid_paths import select_complete_path


def summary(local_complete=False):
    variant = {'name': 'full_task', 'parameters': {'mode': 'task', 'preparation': 'in_place'}}
    return {'source_commit': 'sampling-tested', 'status': 'physical_result',
        'sampled_envelope_native_success': local_complete,
        'conditional_rate_product': 1. if local_complete else 0., 'subtasks': [
            {'subtask': {'id': 'g0:pick', 'mode': 'pick'},
                'selection': {'method': 'self', 'rate': 1., 'status': 'measured',
                    'variant_groups': [{'variant': variant}]},
                'trials': [{'vla_variant': variant, 'success': True,
                    'truth_source': 'unchanged_native_task_completion'} for _ in range(3)]},
            {'subtask': {'id': 'g0:on', 'mode': 'on'},
                'selection': {'method': 'self', 'rate': 1. if local_complete else 0.,
                    'status': 'measured' if local_complete else 'both_failed'}, 'trials': []}]}


def test_complete_native_path_beats_a_pick_tie_followed_by_failed_placement():
    source = summary()
    original = copy.deepcopy(source)
    selected = select_complete_path(source)
    assert selected['sampled_native_success'] is True and selected['conditional_rate'] == 1.
    assert len(selected['choices']) == 1
    assert selected['choices'][0]['vla_parameters'] == {'mode': 'task', 'preparation': 'in_place'}
    assert source == original


def test_successful_local_path_keeps_self_preference_on_equal_complete_rates():
    selected = select_complete_path(summary(True))
    assert selected['reason'] == 'original_local_path'
    assert selected['choices'][0]['method'] == 'self'


def test_unknown_or_subtask_only_measurements_cannot_certify_native_completion():
    source = summary()
    source['subtasks'][0]['trials'][1]['success'] = None
    selected = select_complete_path(source)
    assert selected['sampled_native_success'] is False
    source['subtasks'][0]['trials'][1]['success'] = True
    source['subtasks'][0]['trials'][1]['truth_source'] = 'private_sustained_grasp_v3_post_branch_window'
    assert not select_complete_path(source)['native_complete_alternatives']


def test_uncovered_rules_stay_unknown_and_use_native_instruction_replay():
    selected = select_complete_path({'status': 'oracle_rule_uncovered'})
    assert selected['kind'] == 'native_instruction'
    assert selected['sampled_native_success'] is None


def test_complete_replay_passes_selected_parameters_and_independent_seed(tmp_path):
    from contextlib import nullcontext
    from types import SimpleNamespace
    from robots.libero.bounded_hybrid_paths import replay_complete_path

    selection = select_complete_path(summary())
    calls = []
    def trial(*args, **kwargs):
        calls.append((args[5], args[6], kwargs['vla_parameters']))
        return {'decisions': 1, 'sim_steps': 10, 'success': True}, {}
    probe = SimpleNamespace(trial=trial, restore_checkpoint=lambda *_: None)
    result = replay_complete_path(probe, SimpleNamespace(goal_status=lambda: {'done': True}),
        SimpleNamespace(request=lambda **_: {}), object(), SimpleNamespace(measure=lambda *_: nullcontext()),
        selection, 1000000000, tmp_path/'replay')
    assert calls == [('call_vla', 1000000000, {'mode': 'task', 'preparation': 'in_place'})]
    assert result['actual_full_replay_success'] is True
    assert result['full_replay'][0]['selected_vla_variant'] == 'full_task'
