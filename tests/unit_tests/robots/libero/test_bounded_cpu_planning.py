# Copyright 2026 The RPent Authors.
# SPDX-License-Identifier: Apache-2.0
"""Spawned public prediction preserves consequences and owns no live service."""
import pickle

import numpy as np
import pytest

from robots.libero.bounded_chunk import PublicPrefixPrediction
from robots.libero.bounded_cpu_planning import detach_prediction
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

    for workers in (0, -1, True, 1.5):
        with pytest.raises(ValueError, match='positive integer'):
            MeasuredSkillAdapter(adapter.ex, adapter.xml, prefix_consequence_workers=workers)
