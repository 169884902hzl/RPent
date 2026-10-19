"""Repair diagnostics retain scope and cannot hand control back to VLA."""
from types import SimpleNamespace

import pytest

from scripts.probe_bounded_hybrid_repair import first_self_chunk, validate_plan


def plan():
    return {'evaluation':'hybrid_repair', 'training':False, 'confirmation':False,
        'cases':[{'episode':{'suite':'libero_spatial_swap','task':2,'seed':40},
            'diagnostic':{'domain':'d2','budget':{'no_progress_blocks':None,'max_controls':220}}}]}


def test_repair_accepts_registered_d2_replays_but_never_test_tasks_or_training():
    value = plan()
    validate_plan(value)
    value['cases'][0]['episode']['task'] = 5
    with pytest.raises(ValueError):
        validate_plan(value)
    value = plan()
    value['training'] = True
    with pytest.raises(ValueError):
        validate_plan(value)


def test_self_continuation_cannot_silently_call_vla_again(tmp_path):
    request = {'candidates':[{'id':'vla','skill':'call_vla'}]}
    rpc = object()
    policy = SimpleNamespace(rpc=rpc, choose=lambda _: {'candidate_ids':['vla']})
    adapter = SimpleNamespace(request=lambda **_:request,
        p=SimpleNamespace(env=SimpleNamespace(execution_budget=lambda:{'used_sim_steps':0})))
    with pytest.raises(ValueError, match='bounded skills'):
        first_self_chunk(object(), adapter, policy, {}, tmp_path)
    assert policy.rpc is rpc


def test_original_microwave_fork_accepts_its_libero90_task_only():
    value = plan()
    value['cases'][0] = {'episode': {'suite': 'libero_90', 'task': 35, 'seed': 0},
        'diagnostic': {'domain': 'original', 'budget': {}}}
    validate_plan(value)
    value['cases'][0]['episode']['task'] = 90
    with pytest.raises(ValueError):
        validate_plan(value)


@pytest.mark.parametrize('prefix_success', [False, True])
def test_original_fork_reaches_the_registered_second_goal_and_phase_before_branching(tmp_path, monkeypatch, prefix_success):
    from contextlib import contextmanager

    from scripts import probe_bounded_hybrid_repair as repair

    goals = [['on', 'white_cup', 'left_plate'], ['on', 'yellow_cup', 'right_plate']]
    satisfied = [False, False]
    facade = SimpleNamespace(goal_status=lambda: {'goals': goals, 'satisfied': satisfied})
    adapter = SimpleNamespace(ex=SimpleNamespace(instruction='put the cups on their plates'),
        request=lambda **_: {})
    @contextmanager
    def runtime(*args, **kwargs):
        yield facade, adapter, object(), object()
    monkeypatch.setattr(repair.probe, 'runtime', runtime)
    monkeypatch.setattr(repair.probe, 'save_checkpoint', lambda *args: ({}, {}))
    monkeypatch.setattr(repair.probe, 'restore_checkpoint', lambda *args: None)
    calls = []
    def run_trial(facade, adapter, policy, timings, spec, method, seed, output, request, **kwargs):
        calls.append((spec['id'], method))
        if spec['mode'] == 'on' and prefix_success:
            satisfied[spec['goal_index']] = True
        return {'success': prefix_success, 'decisions': 1}, {}
    monkeypatch.setattr(repair, 'run_trial', run_trial)
    case = {'diagnostic': {'domain': 'original', 'kind': 'original_fork',
        'budget': {}, 'subtask_mode': 'on', 'goal_index': 1, 'trial_seed_base': 1000}}
    result = repair.evaluate_case(case, {}, tmp_path/'case', {'source_commit': 'test'})
    if prefix_success:
        assert calls == [('g0:pick', 'self'), ('g0:on', 'self'), ('g1:pick', 'self'),
            ('g1:on', 'self'), ('g1:on', 'call_vla'), ('g1:on', 'call_vla'), ('g1:on', 'call_vla')]
        assert result['status'] == 'physical_result' and len(result['prefix']) == 3
    else:
        assert calls == [('g0:pick', 'self')]
        assert result['status'] == 'prefix_not_reached' and result['trials'] == []
