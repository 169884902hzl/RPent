# Copyright 2026 Zhilun Hu.
# SPDX-License-Identifier: Apache-2.0
"""Saved CPU prefix labels follow model prefixes without live environment IO."""
import copy
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from robots.libero.bounded_offline_labels import (
    annotate_prefix,
    capture_annotation_state,
    load_annotation_state,
    rebuild_schema6_captured_request,
    request_digest,
    save_annotation_state,
)
from robots.libero.bounded_oracle import BoundedOracle
from robots.libero.v5_state import Entity
from rpent.skill_package.contract import legal_after
from tests.unit_tests.robots.libero.test_bounded_skills import (
    adapter as adapter_fixture,
)


class SavedScreen:
    points = target = np.empty((0, 3))

    def __call__(self, poses):
        return {'passed': True, 'reason': 'saved_public_geometry', 'collision': False,
            'ik_reachable': True, 'path_min_clearance_m': .05}

    def endpoint_screen(self, route, robot):
        return self(route)


@pytest.fixture
def captured(monkeypatch):
    adapter = adapter_fixture.__wrapped__(monkeypatch)
    adapter._cloud_and_ik = lambda *args, **kwargs: SavedScreen()
    adapter.scene.entities['e2'] = Entity('e2', 'plate', (.3, .1, .91),
        (.25, .05, .9), (.35, .15, .92), True, 0)
    request = adapter.request(k=4)
    calls = []
    status = {'done': False, 'goals': [['on', 'box_1', 'plate_1']], 'satisfied': [False]}
    def call(method):
        calls.append(method)
        return copy.deepcopy(status)
    oracle = BoundedOracle(SimpleNamespace(call=call), adapter)
    state = capture_annotation_state(oracle, request)
    return adapter, oracle, request, state, calls


def test_saved_state_matches_oracle_path_and_does_not_touch_live_services(captured, tmp_path):
    adapter, oracle, request, state, calls = captured
    oracle.choose(request)
    expected = copy.deepcopy(oracle.last_labels['positions'])
    assert len(expected) >= 3
    reference = save_annotation_state(tmp_path/'state.pkl.gz', state)
    restored = load_annotation_state(reference['path'], reference['sha256'])
    calls_before = list(calls)
    for position in expected:
        actual = annotate_prefix(restored, request, position['prefix'])
        for field in ('legal', 'rule_acceptable', 'selected'):
            assert actual[field] == position[field]
        assert actual['physics_steps'] == 0 and not actual['gpu_used']
    assert calls == calls_before and not adapter.p.actions


def test_schema6_capture_preserves_merged_options_and_prefix_screen_scope(captured):
    adapter, oracle, _, _, calls = captured
    adapter.schema6_v1 = adapter.lazy_planning_v1 = True
    request = adapter.request(k=4)
    state = capture_annotation_state(oracle, request)
    assert state['adapter'].schema6_v1
    assert state['adapter'].public_progress is not adapter.public_progress
    oracle.choose(request)
    calls_before = list(calls)
    for expected in oracle.last_labels['positions']:
        actual = annotate_prefix(state, request, expected['prefix'])
        for field in ('legal', 'rule_acceptable', 'selected'):
            assert actual[field] == expected[field]
    assert calls == calls_before and not adapter.p.actions


def test_schema6_captured_catalog_uses_same_builder_and_keeps_exact_request(captured):
    adapter, oracle, _, _, calls = captured
    adapter.schema6_v1 = adapter.lazy_planning_v1 = True
    request = adapter.request(k=4)
    state = capture_annotation_state(oracle, request)
    calls_before = list(calls)
    rebuilt, current, flags = rebuild_schema6_captured_request(state, request)
    assert current == request
    assert flags['old_to_new'] == {c['id']: c['id'] for c in request['candidates']}
    assert not flags['failure_history_incomplete'] and not flags['progress_history_reset']
    assert annotate_prefix(rebuilt, current, [])['rule_acceptable']
    assert calls == calls_before and not adapter.p.actions


def test_legacy_captured_catalog_rebuilds_merged_moves_and_relabels_arbitrary_prefix(captured):
    adapter, _, request, state, calls = captured
    request = copy.deepcopy(request)
    request['schema_version'] = 'bounded-skills/3'
    state = copy.deepcopy(state)
    state['request_sha256'] = request_digest(request)
    for field in ('memory', 'public_progress', '_failed_move_anchors', '_move_approach_by_anchor'):
        vars(state['adapter']).pop(field)
    calls_before = list(calls)
    rebuilt, current, flags = rebuild_schema6_captured_request(state, request)
    moves = [c for c in current['candidates'] if c['skill'] == 'move_to']
    assert len(moves) == len(current['anchors']) == 2
    for move in moves:
        anchor = move['parameters']['anchor_id']
        legacy = [c for c in request['candidates'] if c['skill'] == 'move_to'
            and c['parameters']['anchor_id'] == anchor]
        assert len(legacy) == 12
        assert {flags['old_to_new'][c['id']] for c in legacy} == {move['id']}
        assert flags['priority_reference_old_move_by_anchor'][anchor] == next(c['id'] for c in legacy
            if c['parameters']['approach'] == 'above' and c['parameters']['path'] == 'over')
        assert flags['default_old_candidate_id_by_new_id'][move['id']] is None
    assert flags['failure_history_incomplete'] and flags['progress_history_reset']
    prefix = [next(c['id'] for c in current['candidates'] if c['skill'] == 'nudge')]
    label = annotate_prefix(rebuilt, current, prefix)
    assert label['prefix'] == prefix and label['rule_acceptable']
    assert label['legal'] == list(legal_after(current, prefix))
    assert calls == calls_before and not adapter.p.actions
    assert len([c for c in request['candidates'] if c['skill'] == 'move_to']) == 24
    unrelated_goals = copy.deepcopy(state)
    unrelated_goals['private_status'] = {'done': True, 'goals': [], 'satisfied': []}
    assert rebuild_schema6_captured_request(unrelated_goals, request)[1] == current


def test_captured_catalog_rebuild_rejects_inflight_prefix(captured):
    _, _, request, state, _ = captured
    request = copy.deepcopy(request)
    request['execution_prefix'] = {'steps': []}
    state = copy.deepcopy(state)
    state['request_sha256'] = request_digest(request)
    with pytest.raises(ValueError, match='new capture after it completes'):
        rebuild_schema6_captured_request(state, request)


def test_captured_legacy_failure_memory_is_projected_without_restoring_blocked_move(captured):
    adapter, oracle, request, _, _ = captured
    move = next(c for c in request['candidates'] if c['skill'] == 'move_to'
        and c['parameters'] == {'anchor_id': 'e1', 'approach': 'above', 'path': 'over'})
    for _ in range(2):
        adapter.memory.record(move, 'failure', 'measured_sweep_collision')
    request = adapter.request(k=4)
    state = capture_annotation_state(oracle, request)
    _, current, flags = rebuild_schema6_captured_request(state, request)
    moves = [c for c in current['candidates'] if c['skill'] == 'move_to'
        and c['parameters']['anchor_id'] == 'e1']
    assert len(moves) == 3 and all('approach' in c['parameters'] for c in moves)
    assert flags['failure_history_projected_to_merged_catalog']
    assert not flags['failure_history_incomplete']


def test_model_chosen_nonoracle_prefix_is_labeled_without_mutating_saved_state(captured):
    adapter, _, request, state, calls = captured
    option = next(c for c in request['candidates'] if c['skill'] == 'nudge'
        and c['parameters'] == {'axis': 'x', 'distance_m': .01})
    prefix = [option['id']]
    actual = annotate_prefix(state, request, prefix)
    assert actual['prefix'] == prefix and actual['legal'] == list(legal_after(request, prefix))
    assert actual['status'] == 'labeled' and actual['rule_acceptable']
    assert set(actual['rule_acceptable']) <= set(actual['legal'])
    assert actual == annotate_prefix(state, request, prefix)
    assert calls == ['oracle.status'] and not adapter.p.actions


def test_unfitted_anchor_recovery_labels_match_the_online_selector(monkeypatch):
    adapter = adapter_fixture.__wrapped__(monkeypatch)
    adapter._cloud_and_ik = lambda *args, **kwargs: SavedScreen()
    adapter.grasp_geometry = lambda entity: None
    adapter.scene.entities['e2'] = Entity('e2', 'plate', (.3, .1, .91),
        (.25, .05, .9), (.35, .15, .92), True, 0)
    request = adapter.request(k=4)
    status = {'done': False, 'goals': [['on', 'box_1', 'plate_1']], 'satisfied': [False]}
    oracle = BoundedOracle(SimpleNamespace(call=lambda method: status), adapter)
    state = capture_annotation_state(oracle, request)
    choice = oracle.choose(request)
    assert len(choice['candidate_ids']) == 1
    expected = oracle.last_labels['positions'][0]
    actual = annotate_prefix(state, request, [])
    for field in ('legal', 'rule_acceptable', 'selected'):
        assert actual[field] == expected[field]
    after_approach = annotate_prefix(state, request, choice['candidate_ids'])
    assert after_approach['requires_measurement']
    assert after_approach['legal'] == list(legal_after(request, choice['candidate_ids']))
    assert after_approach['physics_steps'] == 0 and not adapter.p.actions


def test_reject_mismatched_request_invalid_prefix_and_corrupt_snapshot(captured, tmp_path):
    _, _, request, state, _ = captured
    with pytest.raises(ValueError, match='different request'):
        annotate_prefix(state, {**request, 'instruction': 'another task'}, [])
    with pytest.raises(ValueError, match='unknown candidate'):
        annotate_prefix(state, request, ['unknown'])
    option = next(c for c in request['candidates'] if c['skill'] == 'observe')
    result = annotate_prefix(state, request, [option['id']])
    assert result['status'] == 'terminal_prefix' and result['legal'] == []
    reference = save_annotation_state(tmp_path/'state.pkl.gz', state)
    Path(reference['path']).write_bytes(b'corrupt')
    with pytest.raises(ValueError, match='hash mismatch'):
        load_annotation_state(reference['path'], reference['sha256'])


def test_parallel_labels_preserve_every_field_for_oracle_and_model_prefixes(captured):
    adapter, oracle, request, state, calls = captured
    oracle.choose(request)
    prefixes = [row['prefix'] for row in oracle.last_labels['positions']]
    nudge = next(c for c in request['candidates'] if c['skill'] == 'nudge'
        and c['parameters'] == {'axis': 'x', 'distance_m': .01})
    prefixes.append([nudge['id']])
    calls_before = list(calls)
    for prefix in prefixes:
        assert annotate_prefix(state, request, prefix, workers=4) == annotate_prefix(state, request, prefix)
    assert calls == calls_before and not adapter.p.actions


@pytest.mark.parametrize('workers', [0, -1, 1.5, True])
def test_reject_invalid_worker_count(captured, workers):
    _, _, request, state, _ = captured
    with pytest.raises(ValueError, match='positive integer'):
        annotate_prefix(state, request, [], workers=workers)


def test_parallel_rejects_live_adapter_and_initialized_cuda(captured, monkeypatch):
    import sys

    adapter, _, request, state, _ = captured
    with pytest.raises(ValueError, match='frozen CPU'):
        annotate_prefix({**state, 'adapter': adapter}, request, [], workers=4)
    monkeypatch.setitem(sys.modules, 'torch', SimpleNamespace(cuda=SimpleNamespace(is_initialized=lambda: True)))
    with pytest.raises(ValueError, match='initialized CUDA'):
        annotate_prefix(state, request, [], workers=4)
