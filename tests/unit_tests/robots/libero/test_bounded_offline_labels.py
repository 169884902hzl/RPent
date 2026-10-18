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
