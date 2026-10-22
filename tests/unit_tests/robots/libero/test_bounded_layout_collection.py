"""Prefix acquisition saves actual bounded states, separately from method labels."""
from contextlib import contextmanager, nullcontext
import pickle
import time
from types import SimpleNamespace

import pytest


def setup(monkeypatch, *, choose_vla=False):
    from coordination.bounded_skills_20261016.scripts import collect_own_layout_prefixes_20261022 as collect
    from coordination.bounded_skills_20261016.scripts import run_own_layout_pi_pilot_20261022 as pilot
    from robots.libero import bounded_offline_labels as annotations
    from scripts import probe_bounded_hybrid_d2 as probe

    generated = {'private_authoring_coordinates': 'not a request field'}
    monkeypatch.setattr(pilot, 'validate_job', lambda row, plan: (generated, {'layout':{'layout_seed':11020600}}))
    state = {'steps': 0}
    env = SimpleNamespace(terminated=False, truncated=False,
        execution_budget=lambda: {'used_sim_steps':state['steps']})
    adapter = SimpleNamespace(p=SimpleNamespace(env=env), held=None,
        ex=SimpleNamespace(instruction='put the bowl on the plate'))
    requests, executes = [], []
    def request(**kwargs):
        requests.append(kwargs)
        return {'max_actions':1,'candidates':[{'id':'move','skill':'move_to'},
            {'id':'vla','skill':'call_vla'}]}
    def execute(actual, decision):
        assert 'private_authoring_coordinates' not in actual
        executes.append(decision);state['steps'] += 5
        adapter.held = 'e1'
        return [{'skill':'move_to','steps_used':5}]
    adapter.request, adapter.execute = request, execute
    policy = SimpleNamespace(choose=lambda request: {'candidate_ids':['vla' if choose_vla else 'move']})
    facade = SimpleNamespace(goal_status=lambda: {'goals':[['on','bowl','plate']],
        'satisfied':[False], 'done':False})
    timings = SimpleNamespace(started=time.perf_counter(), measure=lambda *_:nullcontext(), summary=lambda wall: {'wall_s':wall})
    @contextmanager
    def runtime(case, endpoints, output, **kwargs):
        assert kwargs == {'domain':'original','constructed_start':generated}
        yield facade, adapter, policy, timings
    monkeypatch.setattr(probe, 'runtime', runtime)
    monkeypatch.setattr(probe, 'configure_development_catalog', lambda *_:None)
    monkeypatch.setattr(probe, 'bind_subtask', lambda *_:(SimpleNamespace(id='e1'), None))
    def save(_facade, _adapter, _policy, path, actual):
        value = {'physics': {'public_steps':state['steps']}}
        path.write_bytes(pickle.dumps(value));return value, probe.reference(path)
    monkeypatch.setattr(probe, 'save_checkpoint', save)
    monkeypatch.setattr(annotations, 'capture_annotation_state', lambda *_:{'captured':True})
    def annotation(path, value):
        path.write_bytes(pickle.dumps(value));return probe.reference(path)
    monkeypatch.setattr(annotations, 'save_annotation_state', annotation)
    row = {'case':{},'construction_report':{},'generated_state':{},'frozen_parent_index':{},
        'max_points':3}
    return collect, row, requests, executes


def test_collects_initial_and_intermediate_states_before_executing_each_action(tmp_path, monkeypatch):
    collect, row, requests, executes = setup(monkeypatch)
    result = collect.run_case(row, {'source_commit':'registered'}, {}, tmp_path/'case')
    assert requests == [{'k':1}]*3 and len(executes) == 2
    assert [p['public_sim_steps'] for p in result['points']] == [0,5,10]
    assert [p['phase'] for p in result['points']] == ['initial','public_held','public_held']
    assert [p['subtask']['mode'] for p in result['points']] == ['pick','on','on']
    assert [pickle.loads(open(p['physics']['path'],'rb').read())['public_steps']
        for p in result['points']] == [0,5,10]
    assert not result['task_success_denominator'] and not result['training']


def test_startup_requires_and_records_a_real_bounded_request(tmp_path, monkeypatch):
    collect, row, requests, executes = setup(monkeypatch)
    result = collect.run_case(row, {'source_commit':'registered'}, {}, tmp_path/'case', startup=True)
    assert len(executes) == 1 and result['sim_steps'] == 5
    assert result['first_physical']['receipts'][0]['steps_used'] == 5
    assert len(result['points']) == 1 and result['status'] == 'startup_physical'


def test_collection_cannot_silently_use_vla_for_the_bounded_prefix(tmp_path, monkeypatch):
    collect, row, _, executes = setup(monkeypatch, choose_vla=True)
    with pytest.raises(ValueError, match='VLA disabled'):
        collect.run_case(row, {'source_commit':'registered'}, {}, tmp_path/'case')
    assert not executes
