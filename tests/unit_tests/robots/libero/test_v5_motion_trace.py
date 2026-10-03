from types import SimpleNamespace

import numpy as np
import pytest

from robots.libero.tools import LiberoPrimitives
from robots.libero.v5_runtime import V5Executor


@pytest.mark.parametrize("recording", [False, True])
def test_vla_trace_contains_only_actions_executed_before_native_stop(recording):
    actions = np.arange(35).reshape(5, 7) / 100
    observation = {"states": np.array([0., 0., 1., 0., 0., 0., .04, -.04]),
                   "main_images": np.zeros((2, 2, 3)), "task_descriptions": "original task"}
    env = SimpleNamespace(terminated=True, truncated=False, return_all_frames=False)
    def step(actual, **kwargs):
        assert np.array_equal(actual, actions)
        obs = [observation] * 3 if kwargs.get("return_all_frames") else observation
        return obs, np.zeros(3), np.array([False, False, True]), np.zeros(3), {}
    env.chunk_step = step
    primitive = LiberoPrimitives(env, SimpleNamespace(predict=lambda *a, **k: actions), None, lambda: None)
    primitive.set_obs(observation.copy())
    primitive._recording = recording
    trace = []
    result = primitive._vlm_chunk("pick up the bowl", trace_callback=trace.append)
    assert result["task_descriptions"] == "original task"
    assert trace[0]["instruction"] == "pick up the bowl"
    assert trace[0]["requested_action_count"] == 5
    assert trace[0]["executed_action_count"] == 3
    assert trace[0]["steps_used"] == 3
    assert np.array_equal(trace[0]["actions"], actions[:3])
    assert trace[0]["terminated"] is True


def test_motion_trace_retains_gripper_commands_without_changing_servo_calls():
    calls = []
    primitive = SimpleNamespace(_last_obs_eef_pos=np.array([0., 0., 1.]),
                                env=SimpleNamespace(terminated=False, truncated=False))
    def move(xyz, **kwargs):
        calls.append((xyz, kwargs))
        primitive._last_obs_eef_pos = np.array(xyz)
        return {"steps_used": 2, "final_dist_m": 0., "target_xyz": xyz}
    primitive.move_to = move
    executor = V5Executor(SimpleNamespace(primitives=primitive), SimpleNamespace(), motion_trace_v1=True)
    executor.move([0., 0., 1.1], -1)
    executor.move([0., 0., 1.15], 1)
    assert [c[1]["gripper"] for c in calls] == [-1, 1]
    assert [r["gripper_command"] for r in executor.motion_evidence] == [-1, 1]
    assert [r["start_eef_pos"] for r in executor.motion_evidence] == [[0., 0., 1.], [0., 0., 1.1]]
