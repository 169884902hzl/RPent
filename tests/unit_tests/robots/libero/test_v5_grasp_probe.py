"""Original instance binding and measured diagnostic grasp verification."""

from types import SimpleNamespace

import pytest

from harness_v5_eval import _select_grasp_probe
from robots.libero.v5_state import Candidate
from scripts.probe_v5_grasp449_20261005 import rpent_pick_then_measure
from robots.libero.v5_runtime import V5Executor
from robots.libero.v5_state import Entity
from scripts.summarize_v5_grasp449_20261005 import truth_metrics


@pytest.mark.parametrize("mode", ["direct", "above_10cm", "yaw_90"])
def test_multiple_bowls_use_bound_instance_with_requested_mode(mode):
    entities = [SimpleNamespace(id=eid, name="bowl") for eid in ("e4", "e7")]
    choices = [Candidate("grasp", e.id, mode=m) for e in entities
               for m in ("direct", "above_10cm", "yaw_90")]
    action, count = _select_grasp_probe(
        choices, entities, "bowl", mode,
        lambda: Candidate("grasp", "e7", mode="direct"),
    )
    assert action == Candidate("grasp", "e7", mode=mode)
    assert count == 2


def test_missing_category_does_not_fall_back_to_another_object():
    entities = [SimpleNamespace(id="e4", name="bowl")]
    choices = [Candidate("grasp", "e4", mode="direct")]
    with pytest.raises(ValueError, match="category is not measured"):
        _select_grasp_probe(choices, entities, "moka pot", "direct", None)


def test_task_binding_cannot_select_a_different_category():
    entities = [SimpleNamespace(id=eid, name="bowl") for eid in ("e4", "e7")]
    choices = [Candidate("grasp", e.id, mode="yaw_90") for e in entities]
    with pytest.raises(ValueError, match="binder did not select"):
        _select_grasp_probe(choices, entities, "bowl", "yaw_90",
                            lambda: Candidate("articulate", "e8", mode="open"))


def test_unique_measured_category_needs_no_task_rebinding():
    entities = [SimpleNamespace(id="e7", name="moka pot")]
    action = Candidate("grasp", "e7", mode="above_10cm")
    assert _select_grasp_probe([action], entities, "moka pot", "above_10cm", None) == (action, 1)


@pytest.mark.parametrize("primitive_success,visual_success", [(True, False), (False, True), (True, True)])
def test_rpent_stop_uses_public_primitive_but_visual_receipt(primitive_success, visual_success):
    calls = []
    primitive = {"chunks_used": 12, "success": primitive_success}
    obj = SimpleNamespace(name="bowl")
    executor = SimpleNamespace(
        p=SimpleNamespace(pi0_pick=lambda prompt, **kwargs:
                          calls.append((prompt, kwargs)) or primitive),
        _refresh=lambda names: calls.append(names),
        verify_grasp_measurement=lambda before: visual_success)
    receipt, recorded = rpent_pick_then_measure(executor, "pick up the bowl", 160, obj)
    assert calls == [("pick up the bowl", {"max_chunks": 160}), ["bowl"]]
    assert receipt["grasp_verified"] is visual_success
    assert receipt["chunks"] == 12
    assert recorded == primitive


@pytest.mark.parametrize("enabled,opening,rise,expected", [
    (False, .0049, .05, False),
    (True, .0049, .05, True),
    (True, .001193, .05, False),
    (True, .0049, .01, False),
])
def test_thin_rim_fix_keeps_empty_closure_and_unlifted_object_negative(
    enabled, opening, rise, expected
):
    before = Entity("e1", "bowl", (0, 0, 1), (-.03, -.03, .98), (.03, .03, 1.02))
    after = Entity("e1", "bowl", (0, 0, 1 + rise),
                   (-.03, -.03, .98 + rise), (.03, .03, 1.02 + rise))
    executor = V5Executor(
        SimpleNamespace(primitives=SimpleNamespace(_last_obs_gripper=opening)),
        SimpleNamespace(entities={"e1": after}), grasp_thin_aperture_v1=enabled)
    assert executor.verify_grasp_measurement(before) is expected


def test_motion_failure_reason_is_separate_from_contact_failure():
    row = {"true_sustained_grasp": False, "visual_verified": False,
           "first_receipt": {"failure_reason": "waypoint_not_reached"},
           "grasp_attempted": True, "case": {"episode": {"suite": "libero_10", "task": 1, "seed": 0}}}
    metrics = truth_metrics([row], 1)
    assert metrics["failure_counts"] == {"waypoint_not_reached": 1}
