"""Original instance binding and measured diagnostic grasp verification."""

from types import SimpleNamespace

import pytest

from harness_v5_eval import _select_grasp_probe
from robots.libero.v5_state import Candidate
from scripts.probe_v5_grasp449_20261005 import rpent_pick_then_measure
from scripts.probe_v5_grasp449_20261005 import rpent_pick_then_stable_measure
from scripts.probe_v5_grasp449_20261005 import measured_rim_approach
from scripts.probe_v5_grasp449_20261005 import probe_contact_prompt
from robots.libero.v5_runtime import V5Executor
from robots.libero.v5_state import Entity
from scripts.summarize_v5_grasp449_20261005 import truth_metrics


def test_selected_only_prompt_cannot_reintroduce_other_task_objects():
    prompt, detail = probe_contact_prompt(
        {"profile": "start_full", "full_prompt_binding": "target_first",
         "contact_prompt_binding": "selected_only"}, {"original_goal_source": True},
        "put both the cream cheese box and the butter in the basket", "butter", "pick up the frypan")
    assert prompt == "pick up the butter"
    assert "cream cheese" not in prompt and "basket" not in prompt
    assert detail["full_prompt_origin"] == "selected_measured_category_only"


def test_selected_prompt_keeps_alias_out_of_measured_entity_name():
    prompt, _ = probe_contact_prompt(
        {"profile": "start_full", "contact_prompt_binding": "selected_only",
         "contact_category_aliases": {"frypan": "frying pan"}},
        {"original_goal_source": False}, "", "frypan", "pick up the frypan")
    assert prompt == "pick up the frying pan"


def test_control_full_prompt_retains_original_task_after_selected_category():
    prompt, detail = probe_contact_prompt(
        {"profile": "start_full", "full_prompt_binding": "target_first"},
        {"original_goal_source": True}, "put both boxes in the basket", "butter", "")
    assert prompt == "pick up the butter first, then put both boxes in the basket"
    assert detail["original_full_prompt"] == "put both boxes in the basket"


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


def test_rim_probe_uses_observed_outer_patch_instead_of_container_cavity():
    import numpy as np

    angles = np.linspace(0, 2 * np.pi, 120, endpoint=False)
    points = np.array([(.05 * np.cos(a), .05 * np.sin(a), 1.) for a in angles])
    bowl = Entity("e7", "bowl", (0, 0, 1), (-.05, -.05, .95), (.05, .05, 1.))
    executor = SimpleNamespace(scene=SimpleNamespace(measurement_clouds={"e7": points}),
                               p=SimpleNamespace(_last_obs_eef_pos=np.array([-.2, 0, 1.2])))
    pose, method = measured_rim_approach(executor, bowl, .15)
    assert method == "measured_visible_rim"
    assert pose[0] < -.045 and abs(pose[1]) < .01
    assert pose[2] == pytest.approx(1.15)


def test_rim_probe_does_not_invent_an_unseen_rim_from_a_box():
    import numpy as np

    bowl = Entity("e7", "bowl", (0, 0, 1), (-.05, -.05, .95), (.05, .05, 1.))
    executor = SimpleNamespace(scene=SimpleNamespace(measurement_clouds={}),
                               p=SimpleNamespace(_last_obs_eef_pos=np.array([-.2, 0, 1.2])))
    assert measured_rim_approach(executor, bowl, .15) == (None, "visible_rim_not_measured")


def test_rim_condition_preserves_other_classes_registered_overhead_pose():
    bottle = Entity("e3", "wine bottle", (0, 0, 1), (-.02, -.03, .9), (.04, .01, 1.1))
    # Non-container classes must not require a rim, contacts or private poses.
    pose, method = measured_rim_approach(SimpleNamespace(), bottle, .10)
    assert method == "bounds_centre"
    assert pose == pytest.approx([.01, -.01, 1.20])


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


@pytest.mark.parametrize("first_lower_rise,second_lower_rise,expected", [
    (.05, .05, True),
    (.05, .01, False),  # A lifted object that drops must stay negative.
    (.02, .02, False),  # Centre rises while the rotated bottom is still low.
])
def test_stable_visual_grasp_requires_clearance_in_both_frames(
    first_lower_rise, second_lower_rise, expected
):
    import numpy as np

    before = Entity("e1", "bowl", (0, 0, 1), (-.03, -.03, .98), (.03, .03, 1.02))
    frames = [Entity("e1", "bowl", (0, 0, 1.10),
                     (-.03, -.03, .98 + rise), (.03, .03, 1.15), source_step=i + 1)
              for i, rise in enumerate((first_lower_rise, second_lower_rise))]
    calls = []
    scene = SimpleNamespace(entities={"e1": before})
    def refresh(names):
        calls.append(("refresh", names))
        scene.entities["e1"] = frames.pop(0)
    def move(target, gripper, **kwargs):
        calls.append(("lift", target.tolist(), gripper, kwargs))
        return {"waypoint_reached": True}
    primitives = SimpleNamespace(
        pi0_pick=lambda *args, **kwargs: {"chunks_used": 11},
        env=SimpleNamespace(terminated=False, truncated=False),
        _last_obs_eef_pos=np.array([0., 0., 1.1]), _last_obs_gripper=.0049,
        set_gripper=lambda **kwargs: calls.append(("hold", kwargs)))
    executor = SimpleNamespace(p=primitives, scene=scene, grasp_minimum_opening=.002,
                               move=move, _refresh=refresh)
    receipt, _, evidence = rpent_pick_then_stable_measure(executor, "pick up the bowl", 160, before)
    assert receipt["grasp_verified"] is expected
    assert len(evidence["frames"]) == 2
    assert calls[0][0] == "lift"
    assert calls[0][1] == pytest.approx([0, 0, 1.15])
    assert ("hold", {"gripper": 1, "steps": 10}) in calls


def test_stable_visual_grasp_uses_wrist_measurement_when_main_view_is_missing():
    import numpy as np
    from dataclasses import replace

    before = Entity("e1", "moka pot", (0, 0, 1), (-.03, -.03, .98), (.03, .03, 1.10))
    after = replace(before, xyz=(0, 0, 1.10), lower=(-.03, -.03, 1.08),
                    upper=(.03, .03, 1.20), source_step=2)
    calls = []
    scene = SimpleNamespace(entities={"e1": before})
    def main_refresh(names):
        scene.entities["e1"] = replace(before, visible=False)
    def wrist_refresh(names, **kwargs):
        calls.append((names, kwargs))
        scene.entities["e1"] = replace(after, source_step=len(calls) + 1)
    scene.refresh = wrist_refresh
    executor = SimpleNamespace(
        p=SimpleNamespace(pi0_pick=lambda *a, **kw: {"chunks_used": 12},
            env=SimpleNamespace(terminated=False, truncated=False),
            _last_obs_eef_pos=np.array([0., 0., 1.1]), _last_obs_gripper=.05,
            set_gripper=lambda **kw: None), scene=scene, grasp_minimum_opening=.002,
        move=lambda *a, **kw: {"waypoint_reached": True}, _refresh=main_refresh)
    receipt, _, evidence = rpent_pick_then_stable_measure(executor, "pick up the moka pot", 160, before)
    assert receipt["grasp_verified"] is True
    assert calls == [(["moka pot"], {"camera_view": "wrist"})] * 2
    assert all(frame["camera"] == "wrist" for frame in evidence["frames"])


@pytest.mark.parametrize("stable_verified", [True, False])
def test_final_stable_measurement_is_not_overwritten_by_single_frame(stable_verified):
    import numpy as np
    from dataclasses import replace

    before = Entity("e1", "bowl", (0, 0, 1), (-.03, -.03, .98), (.03, .03, 1.02))
    after = replace(before, xyz=(0, 0, 1.10), lower=(-.03, -.03, 1.08),
                    upper=(.03, .03, 1.12), source_step=2)
    scene = SimpleNamespace(entities={"e1": before})
    executor = V5Executor(SimpleNamespace(primitives=SimpleNamespace(
        env=SimpleNamespace(terminated=False, truncated=False),
        _last_obs_eef_pos=np.array([0., 0., 1.1]), _last_obs_gripper=.05)), scene)
    executor.move = lambda *args, **kwargs: None
    def forbidden(*args, **kwargs):
        raise AssertionError("final two-frame evidence must not become a fresh single-frame decision")
    executor._refresh = forbidden
    executor.verify_grasp_measurement = forbidden
    def vla(*args, **kwargs):
        scene.entities["e1"] = after
        return {"executed": True, "chunks": 11, "grasp_verified": stable_verified,
                "stop": "grasp_verified" if stable_verified else "grasp_not_verified",
                "final_grasp_measurement": True}
    executor.vla_act = vla
    receipt = {}
    executor._execute(Candidate("grasp", "e1", mode="direct"), receipt, None)
    assert receipt["grasp_verified"] is stable_verified
    assert "final_grasp_measurement" not in receipt
    assert executor.held == ("e1" if stable_verified else None)
