# Copyright 2026 The RPent Authors.
# SPDX-License-Identifier: Apache-2.0
"""Spawned public prediction preserves consequences and owns no live service."""
import pickle

import numpy as np
import pytest

from robots.libero.bounded_chunk import PublicPrefixPrediction
from robots.libero.bounded_cpu_planning import capture_request_adapter, detach_prediction
from robots.libero.bounded_screen import PublicRouteScreen
from tests.unit_tests.robots.libero.test_bounded_skills import adapter as adapter


class MeasuredIK:
    """Deterministic CPU screen without a simulator or robot assets."""

    def __init__(self):
        self.cache = {}
        self.last_solution = None

    def check(self, xyz, quat):
        return {'solution_found': True, 'position_error_m': 0., 'angular_error_rad': 0.}


def measured_prediction(adapter):
    geometry = {'boxes': [{'name': 'palm', 'lower': [-.005]*3, 'upper': [.005]*3}],
                'max_opening_m': .08}
    adapter.geometry = geometry
    adapter._cloud_and_ik = lambda *args, **kwargs: PublicRouteScreen(
        np.array([[10., 10., 10.]]), geometry, MeasuredIK())
    request = adapter.request(k=4)
    prediction = PublicPrefixPrediction(adapter, request)
    option = next(c for c in request['candidates'] if c['skill'] == 'nudge'
        and c['parameters'] == {'axis': 'x', 'distance_m': .01})
    prediction.advance(option)
    return prediction


def test_detached_prediction_pickles_without_live_resources_or_source_graphs(adapter):
    prediction = measured_prediction(adapter)
    # These live callbacks must not be copied or serialized into a child.
    prediction.adapter.scene.rpc = lambda *_: pytest.fail('live RPC')
    prediction.adapter.scene.toolkit = adapter.ex.toolkit
    prediction.adapter.unused_service = lambda *_: pytest.fail('unused live service')
    captured = detach_prediction(prediction)
    restored = pickle.loads(pickle.dumps(captured))
    assert restored.source_adapter is None
    assert not hasattr(restored.adapter.scene, 'rpc')
    assert not hasattr(restored.adapter.scene, 'toolkit')
    assert not hasattr(restored.adapter.p.env, 'step')
    assert not hasattr(restored.adapter, 'unused_service')
    assert restored.context() == prediction.context()
    assert not adapter.p.actions


def test_spawned_context_keeps_all_fields_and_diagnostics_in_original_order(adapter):
    prediction = measured_prediction(adapter)
    prediction.adapter.candidate_diagnostics = []
    serial = prediction.context()
    diagnostics = list(prediction.adapter.candidate_diagnostics)
    prediction.adapter.candidate_diagnostics = []
    prediction.adapter.prefix_consequence_workers = 2
    parallel = prediction.context()
    assert parallel == serial
    assert prediction.adapter.candidate_diagnostics == diagnostics
    assert not adapter.p.actions


def test_invalid_runtime_worker_count_is_rejected_at_adapter_boundary(adapter):
    from robots.libero.bounded_skills import MeasuredSkillAdapter

    for name in ('prefix_consequence_workers', 'request_consequence_workers', 'registration_query_workers'):
        for workers in (0, -1, True, 1.5):
            with pytest.raises(ValueError, match='positive integer'):
                MeasuredSkillAdapter(adapter.ex, adapter.xml, **{name: workers})


def test_spawned_initial_request_keeps_candidate_bytes_order_and_diagnostics(adapter):
    measured_prediction(adapter)
    from robots.libero.bounded_motion import measured_robot
    from robots.libero.v5_state import Entity

    for number in (2, 3):
        adapter.scene.entities[f'e{number}'] = Entity(f'e{number}', 'box', (.3, .1, .9),
            (.25, .05, .85), (.35, .15, .95), True, 0)
    obstacle = np.array(measured_robot(adapter.p)['eef_xyz_m']) + [.015, 0., 0.]
    adapter._cloud_and_ik = lambda *args, **kwargs: PublicRouteScreen(
        obstacle[None], adapter.geometry, MeasuredIK())
    serial = adapter.request(k=4)
    assert len(serial['candidates']) >= 64
    diagnostics = list(adapter.candidate_diagnostics)
    assert diagnostics  # Blocked routes must also retain their original order.
    adapter.request_consequence_workers = 2
    parallel = adapter.request(k=4)
    assert parallel == serial
    assert adapter.candidate_diagnostics == diagnostics
    assert not adapter.p.actions


def test_small_request_does_not_pay_process_startup(adapter, monkeypatch):
    from robots.libero.bounded_cpu_planning import request_candidates

    monkeypatch.setattr('multiprocessing.get_context', lambda *_: pytest.fail('small request spawned'))
    options = [('set_gripper', {'mode': 'open'}), ('finish', {})]
    expected = [adapter._candidate(skill, parameters) for skill, parameters in options]
    assert request_candidates(adapter, options, 4) == expected
    assert not adapter.p.actions


def test_cpu_capture_preserves_the_registered_screen_scope(adapter):
    adapter.lazy_planning_v1 = True
    captured = capture_request_adapter(adapter, [('set_gripper', {'mode': 'open'})])
    restored = pickle.loads(pickle.dumps(captured))
    assert restored.lazy_planning_v1 is True
    assert not hasattr(restored.p.env, 'step')


def test_captured_initial_request_keeps_control_history_but_no_live_resources(adapter):
    measured_prediction(adapter)
    adapter.p._bounded_control_index = 3
    adapter.p._bounded_motion_samples = [(3, {'measured': True})]
    adapter.p._bounded_rest_reference = {'control_index': 3}
    adapter.scene.rpc = lambda *_: pytest.fail('live RPC')
    adapter.unused_service = lambda *_: pytest.fail('live service')
    captured = capture_request_adapter(adapter, [('nudge', {'axis': 'x', 'distance_m': .01})])
    restored = pickle.loads(pickle.dumps(captured))
    assert restored.p._bounded_control_index == 3
    assert restored.p._bounded_motion_samples == adapter.p._bounded_motion_samples
    assert restored.p._bounded_rest_reference == adapter.p._bounded_rest_reference
    assert not hasattr(restored.p.env, 'step')
    assert not hasattr(restored.scene, 'rpc')
    assert not hasattr(restored, 'unused_service')
    assert not adapter.p.actions
