"""Losing a close-up measurement is a recoverable skill result."""

from dataclasses import replace
from types import SimpleNamespace

import numpy as np

from robots.libero.v5_runtime import V5Executor
from robots.libero.v5_state import Candidate, Entity


def test_closeup_miss_preserves_motion_without_raising_or_running_contact():
    obj = Entity("e1", "moka pot", (0., 0., 1.), (-.03, -.03, .95), (.03, .03, 1.05))
    scene = SimpleNamespace(entities={obj.id: obj})
    p = SimpleNamespace(_last_obs_eef_pos=np.array([0., 0., 1.2]),
                        env=SimpleNamespace(terminated=False, truncated=False))
    executor = V5Executor(SimpleNamespace(primitives=p), scene,
                          wrist_refine_v1=True, grasp_safe_approach_v2=True)
    executor.capture = lambda: None
    scene.refresh = lambda *args, **kwargs: scene.entities.update({obj.id: replace(obj, visible=False)})

    def stage(*args, **kwargs):
        executor.motion_evidence.append({"actions_used": 45})
        return True

    executor.stage_grasp = stage
    executor.vla_act = lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("contact ran"))
    receipt = {"executed": False}
    executor._execute(Candidate("grasp", obj.id, mode="direct"), receipt, None)
    assert receipt["executed"] is True
    assert receipt["verification"] == "unmeasured"
    assert receipt["grasp_verified"] is None
    assert receipt["failure_reason"] == "grasp_closeup_not_measured"
    assert receipt["recoverable"] is True
    assert "error" not in receipt
