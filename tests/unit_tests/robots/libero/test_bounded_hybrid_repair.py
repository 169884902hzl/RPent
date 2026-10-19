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
