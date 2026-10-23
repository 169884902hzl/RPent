"""Bounded preparation and observed contact direction regressions."""
import numpy as np
from types import SimpleNamespace

from robots.libero.bounded_motion import MotionConfig
from robots.libero.bounded_permissive import move
from robots.libero.bounded_adaptive_contact import dominant_direction, in_target
from tests.unit_tests.robots.libero.test_bounded_motion import FakePrimitives


def test_permissive_preparation_goes_to_measured_endpoint_with_vector_clipping():
    p = FakePrimitives()
    result = move(p, {'xyz_m':[.1,.1,1.]},gripper=-1.,config=MotionConfig())
    assert result['arrived'] and result['endpoint_error_m'] <= .012
    assert not result['sweep_veto'] and not result['tracking_error_veto']
    assert max(np.linalg.norm(action[:3])*.05 for action in p.actions) <= .02000001


def test_blocked_preparation_hands_off_after_budget_without_tracking_abort():
    p = FakePrimitives();p._step_env=lambda action:p.actions.append(action)
    result = move(p, {'xyz_m':[.1,0.,1.]},gripper=1.,config=MotionConfig(),max_steps=7)
    assert result['success'] and not result['arrived'] and result['steps_used']==7
    assert result['stop_reason']=='preparation_step_budget' and result['endpoint_error_m']==.1


def test_articulated_direction_uses_observed_largest_axis():
    np.testing.assert_array_equal(dominant_direction([.004,-.012,.001],[1,0,0]),[0,-1,0])
    np.testing.assert_array_equal(dominant_direction([.0001,0,0],[1,0,0]),[1,0,0])


def test_push_arrival_uses_public_target_footprint():
    target=SimpleNamespace(lower=[.1,.2,.8],upper=[.2,.3,.9])
    assert in_target(SimpleNamespace(xyz=[.15,.25,.85]),target)
    assert not in_target(SimpleNamespace(xyz=[.21,.25,.85]),target)
