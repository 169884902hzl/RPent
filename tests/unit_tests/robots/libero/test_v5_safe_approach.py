from types import SimpleNamespace

import numpy as np
import pytest

from robots.libero.v5_runtime import V5Executor
from robots.libero.v5_state import Entity


def executor_at(xyz, residual=0.):
    primitive = SimpleNamespace(_last_obs_eef_pos=np.array(xyz, dtype=float),
                                env=SimpleNamespace(terminated=False, truncated=False))
    calls = []
    def move(target, **kwargs):
        calls.append(target)
        primitive._last_obs_eef_pos = np.array(target)
        return {"steps_used": 80, "final_dist_m": residual}
    primitive.move_to = move
    return V5Executor(SimpleNamespace(primitives=primitive), SimpleNamespace(),
                      grasp_safe_approach_v2=True), calls


def test_contact_staging_lifts_then_translates_above_measured_object():
    executor, calls = executor_at((-.15, 0., 1.))
    obj = Entity("e7", "bowl", (.1, .05, 1.01), (.07, .02, .99), (.13, .08, 1.03))
    receipt = {}
    assert executor.stage_grasp(obj, [.1, .05, 1.07], receipt)
    assert np.allclose(calls, [[-.15, 0., 1.18], [.1, .05, 1.18]])
    assert receipt["contact_policy_standoff_m"] == .15


@pytest.mark.parametrize("residual,allowed", [(.079, True), (.081, False)])
def test_contact_staging_allows_small_residual_but_returns_recoverable_failure(residual, allowed):
    executor, _ = executor_at((0., 0., 1.2), residual=residual)
    obj = Entity("e7", "box", (.1, 0., 1.), (.08, -.02, .98), (.12, .02, 1.02))
    receipt = {}
    assert executor.stage_grasp(obj, [.1, 0., 1.06], receipt) is allowed
    if not allowed:
        assert receipt["failure_reason"] == "approach_not_reached"
        assert receipt["grasp_verified"] is False
        assert receipt["recoverable"] is True and "error" not in receipt
    with pytest.raises(RuntimeError, match="servo did not reach"):
        executor.move([.1, 0., 1.06], -1)


@pytest.mark.parametrize("distance,yaw,allowed", [(.001, .019, True), (.021, .019, False), (.001, .051, False)])
def test_wrist_staging_returns_recoverable_outcome_for_position_or_angle_miss(distance, yaw, allowed):
    primitive = SimpleNamespace(_last_obs_eef_pos=np.array([.1, -.2, 1.15]),
                                env=SimpleNamespace(terminated=False, truncated=False))
    calls = []
    def move_pose(target, **options):
        calls.append((target, options))
        return {"final_dist_m": distance, "final_yaw_err": yaw, "steps_used": 150}
    primitive.move_pose = move_pose
    executor = V5Executor(SimpleNamespace(primitives=primitive), SimpleNamespace(),
                          wrist_position_hold_v1=True)
    receipt = {}
    assert executor.stage_wrist(np.pi / 2, receipt) is allowed
    assert calls[0][0] == [.1, -.2, 1.15]
    if not allowed:
        assert receipt["failure_reason"] == "wrist_pose_not_reached"
        assert receipt["recoverable"] is True and receipt["grasp_verified"] is False
        assert "error" not in receipt


def test_disabled_wrist_feedback_uses_original_primitive():
    calls = []
    primitive = SimpleNamespace(rotate_wrist=lambda **kw: calls.append(kw) or {},
                                env=SimpleNamespace(terminated=False, truncated=False))
    executor = V5Executor(SimpleNamespace(primitives=primitive), SimpleNamespace())
    assert executor.stage_wrist(1.2, {})
    assert calls == [{"target_yaw": 1.2, "gripper": -1}]
