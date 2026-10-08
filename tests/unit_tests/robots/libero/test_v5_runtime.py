# Copyright 2026 Zhilun Hu.
# SPDX-License-Identifier: Apache-2.0
"""Composite skills must publish the native task result before evaluation."""

from types import SimpleNamespace

import pytest

from robots.libero import tools
from robots.libero.toolkit import LiberoToolkit
from robots.libero.v5_runtime import V5Executor, segmentation_prompt, scene_vocabulary


@pytest.mark.parametrize("name,profile", [
    ("bowl", "C"), ("wine bottle", "C"), ("ketchup", "C"),
    ("cream cheese", "B"), ("red coffee mug", "B"),
    ("moka pot", None), ("frypan", None), ("alphabet soup", None),
])
def test_category_profiles_use_perceived_classes_without_claiming_pan_or_moka(name, profile):
    executor = V5Executor(SimpleNamespace(primitives=SimpleNamespace()), SimpleNamespace())
    assert executor.category_grasp_profile(SimpleNamespace(name=name)) == profile


@pytest.mark.parametrize("profile,verified", [("C", True), ("B", False), ("B", None)])
def test_category_grasp_preserves_registered_prompt_stop_and_nullable_measurement(profile, verified):
    import numpy as np
    from robots.libero.v5_state import Entity

    name = "bowl" if profile == "C" else "red coffee mug"
    before = Entity("e1", name, (0, 0, .95), (-.04, -.03, .9), (.02, .03, 1.))
    after = Entity("e1", name, (0, 0, 1.1), (-.04, -.03, 1.05), (.02, .03, 1.15), source_step=1)
    calls = []
    p = SimpleNamespace(_last_obs_eef_pos=np.array([0., 0., 1.2]), _last_obs_gripper=.04)
    p.pi0_pick = lambda prompt, **kwargs: calls.append((prompt, kwargs)) or {"chunks_used": 16}
    executor = V5Executor(SimpleNamespace(primitives=p), SimpleNamespace(entities={"e1": after}),
                          instruction="place the bowl on the plate")
    executor.stage_category_start = lambda *args: True
    executor.stage_grasp = lambda obj, xyz, receipt, **kwargs: calls.append((xyz, kwargs)) or True
    executor._refresh = lambda names: calls.append(names)
    executor.verify_grasp_measurement = lambda obj: verified
    receipt = {}
    executor.execute_category_grasp(before, profile, receipt)
    assert calls[-1] == [name]
    if profile == "C":
        assert calls[0] == ("pick up the bowl first, then place the bowl on the plate", {"max_chunks": 160})
    else:
        assert calls[0][0] == pytest.approx([-.01, 0., 1.10])
        assert calls[0][1] == {"minimum_standoff_m": .10}
        assert calls[1] == ("pick up the red coffee mug", {"max_chunks": 160})
    assert receipt["grasp_verified"] is verified
    assert receipt["verification"] == ("unmeasured" if verified is None else "verified" if verified else "failed")
    assert executor.held == ("e1" if verified else None)
    assert (executor.held_offset is None) is not bool(verified)


@pytest.mark.parametrize("verified", [True, False, None])
def test_pan_runtime_uses_shared_coupled_measurement_without_private_truth(monkeypatch, verified):
    import numpy as np
    from robots.libero import v5_pan_grasp
    from robots.libero.v5_state import Entity

    before = Entity("e1", "frypan", (0, 0, .95), (-.12, -.08, .9), (.12, .08, 1.))
    after = Entity("e1", "frypan", (0, 0, 1.15), (-.12, -.08, 1.1), (.12, .08, 1.2), source_step=2)
    raw = {"robot0_eef_quat": [0., 0., 0., 1.]}
    p = SimpleNamespace(_last_obs_eef_pos=np.array([0., 0., 1.2]), _last_obs_gripper=.04,
                        env=SimpleNamespace(raw_obs=lambda: raw))
    scene = SimpleNamespace(entities={"e1": after})
    executor = V5Executor(SimpleNamespace(primitives=p), scene,
        grasp_category_profiles_v1=True, pan_coupled_lift_v1=True,
        grasp_independent_views_v1=True, grasp_measurement_calibration={"registered": True})
    calls = []
    def measure(actual, prompt, budget, obj, **kwargs):
        assert actual is executor and obj is before
        calls.append((prompt, budget, kwargs["trial_lift_m"],
                      kwargs["cross_view_handle_v1"], kwargs["coupled_lift_v1"]))
        kwargs["evidence"].update(stable_visual_grasp={"paired_verdict": {"verified": verified}})
        return {"executed": True, "chunks": 20, "grasp_verified": verified}
    monkeypatch.setattr(v5_pan_grasp, "rpent_pick_then_independent_handle_measure", measure)
    executor.stage_category_start = lambda *args: pytest.fail("same reset pose must not be moved")
    assert executor.category_grasp_profile(before) == "PAN"
    receipt = {}
    executor.execute_category_grasp(before, "PAN", receipt)
    assert calls == [("pick up the frying pan", 320, .1, True, True)]
    assert receipt["grasp_verified"] is verified
    assert receipt["verification"] == ("verified" if verified else "unmeasured" if verified is None else "failed")
    assert executor.held == (before.id if verified else None)
    assert executor.last_verification_measurements["independent_grasp"]["verified"] is verified
    executor.pan_coupled_lift_v1 = False
    assert executor.category_grasp_profile(before) is None


@pytest.mark.parametrize("at_start,reached", [(True, True), (False, True), (False, False)])
def test_category_c_returns_by_public_pose_without_simulator_restore(at_start, reached):
    import numpy as np
    from robots.libero.v5_state import Entity

    start = np.array([.1, .1, 1.2])
    raw = {"robot0_eef_quat": [0., 0., 0., 1.]}
    p = SimpleNamespace(_last_obs_eef_pos=start.copy(), _last_obs_gripper=.08,
                        env=SimpleNamespace(raw_obs=lambda: raw, terminated=False, truncated=False))
    executor = V5Executor(SimpleNamespace(primitives=p), SimpleNamespace(entities={}),
                          grasp_category_profiles_v1=True)
    if not at_start:
        p._last_obs_eef_pos += [.1, 0., .1]
    calls = []
    executor.move = lambda *args, **kwargs: calls.append("move") or {"waypoint_reached": True}
    p.move_pose = lambda *args, **kwargs: calls.append("pose") or {
        "final_dist_m": .001 if reached else .08, "final_pitch": np.pi,
        "final_yaw_err": 0., "steps_used": 12}
    obj = Entity("e1", "bowl", (0, 0, 1), (-.02, -.02, .98), (.02, .02, 1.02))
    receipt = {}
    assert executor.stage_category_start(obj, receipt) is reached
    assert ("pose" in calls) is not at_start
    assert receipt["approach"] == ("C_observed_episode_start" if at_start else "C_public_pose_return_development")
    if not reached:
        assert receipt["verification"] == "failed" and receipt["recoverable"] is True


@pytest.mark.parametrize("calibrated", [True, False])
def test_independent_grasp_uses_current_robot_frame_and_rejects_stale_view(calibrated):
    import json
    from pathlib import Path

    import numpy as np
    from robots.libero.v5_state import Entity

    calibration = json.loads((Path(__file__).resolve().parents[4] /
        "results/harness_v5/gripper513_original_opening_calibration_20261005/runtime_calibration.json").read_text())
    before = Entity("e1", "moka pot", (0, 0, .95), (-.02, -.02, .90), (.02, .02, 1.))
    current = Entity("e1", "moka pot", (0, 0, 1.05), (-.02, -.02, 1.), (.02, .02, 1.10), source_step=2)
    stale = Entity("e1", "moka pot", (0, 0, .95), (-.02, -.02, .90), (.02, .02, 1.), source_step=1)
    raw = {"robot0_eef_pos": np.array([0., 0., 1.05]),
           "robot0_eef_quat": [0., 0., 0., 1.], "robot0_gripper_qpos": [.02, -.02]}
    primitives = SimpleNamespace(env=SimpleNamespace(raw_obs=lambda: raw),
                                 _last_obs_eef_pos=np.array([2., 2., 2.]), _last_obs_gripper=.001)
    scene = SimpleNamespace(entities={"e1": current},
        measurement_views={"e1": {"agentview": current, "wrist": stale}}, measurement_clouds_by_view={})
    executor = V5Executor(SimpleNamespace(primitives=primitives, _state=SimpleNamespace(latest_step=2)),
        scene, grasp_independent_views_v1=True, grasp_measurement_calibration=calibration if calibrated else None)
    frame = executor.independent_grasp_frame(before, None)
    assert frame["eef_xyz"] == [0., 0., 1.05] and frame["opening_m"] == .04
    assert "wrist" not in frame["per_view"]
    assert frame["verified"] is (True if calibrated else None)
    if calibrated:
        geometry = frame["per_view"]["agentview"]["finger_geometry"]
        assert geometry["mode"] == "calibrated_finger_frame"
        assert geometry["object_lower_local_m"] == pytest.approx([-.02, -.02, -.0464])
    scene.measurement_views["e1"] = {"wrist": stale}
    assert executor.independent_grasp_frame(before, None)["verified"] is None


def test_wrist_recall_runs_after_primary_miss_without_mask_recording(monkeypatch):
    import base64
    import numpy as np
    from robots.libero.v5_runtime import MeasuredScene
    from rpent.robots.components.sam3_client import Sam3Client

    rows, cols = np.mgrid[:20, :20]
    world = np.stack((cols * .002, rows * .002, 1 + rows * .0001), axis=-1)
    state = SimpleNamespace(latest_step=1, load_bytes=lambda name: name.encode(),
                            load=lambda name: {"extrinsic_cam2world": np.eye(4)} if name.endswith(".json") else world)
    views = []

    def call(method, kwargs, **unused):
        view = base64.b64decode(kwargs["image_base64"]).decode()
        views.append(view)
        return {"instances": [] if view.startswith("agentview") else
                [{"mask": np.ones((20, 20), dtype=bool), "score": .9}]}

    monkeypatch.setattr(Sam3Client, "_decode_result", staticmethod(lambda item: SimpleNamespace(mask=item["mask"])))
    scene = MeasuredScene(SimpleNamespace(_state=state), SimpleNamespace(call=call), 0, wrist_recall_v1=True)
    scene.refresh(["butter"])
    assert views[-1] == "wrist_high.png"
    assert views.count("wrist_high.png") == 1
    assert all(view == "agentview_high.png" for view in views[:-1])
    assert len(scene.entities) == 1
    assert next(iter(scene.entities.values())).name == "butter"
    assert next(iter(scene.entities.values())).visible


def test_fixed_microwave_reference_does_not_expand_onto_the_closed_door():
    import numpy as np
    from robots.libero.v5_fixture_parts import measured_microwave_frame
    from robots.libero.v5_state import Entity

    x, z = np.meshgrid(np.linspace(.09, .17, 30), np.linspace(.94, 1.10, 30))
    fixed = np.stack([x, np.full_like(x, .246), z], axis=-1)
    parent = Entity("e1", "microwave", (0, .28, 1.02), (-.16, .245, .935), (.17, .34, 1.108))
    face, _, _, anchor = measured_microwave_frame(
        fixed, parent, (0., 0., 1.5), None, {"normal_xy": [1., 0.]})
    assert face is not None and anchor is not None
    closed = fixed.copy()
    closed[..., 0] -= .24
    after, evidence, _, same_anchor = measured_microwave_frame(
        np.concatenate([fixed, closed], axis=1), parent, (0., 0., 1.5), None, None, anchor)
    assert after is not None and after["centre"][0] == pytest.approx(face["centre"][0])
    assert same_anchor == anchor == evidence["anchor"]
    unknown, evidence, _, anchor = measured_microwave_frame(
        fixed, parent, (0., 0., 1.5), None, {"normal_xy": [0., 1.]})
    assert unknown is None and anchor is None
    assert evidence["reason"] == "initial_front_not_distinct_from_moving_door"


@pytest.mark.parametrize("frame_source,frame_accepted,dual_offset,primary_missing", [
    ("door", True, None, False), ("same", False, None, False), ("shell", True, None, False),
    ("shell", True, 0., False), ("shell", True, 0., True), ("shell", True, .03, False),
])
def test_microwave_endpoint_requires_an_independent_frame_inside_the_shell(
        frame_source, frame_accepted, dual_offset, primary_missing, monkeypatch, tmp_path):
    import base64
    import numpy as np
    from robots.libero.v5_runtime import MeasuredScene
    from robots.libero.v5_state import Entity
    from rpent.robots.components.sam3_client import Sam3Client

    x, z = np.meshgrid(np.linspace(-.15, .16, 20), np.linspace(.94, 1.10, 20))
    shell = np.stack([x, np.full_like(x, .25), z], axis=-1)
    y, z = np.meshgrid(np.linspace(.03, .26, 20), np.linspace(.94, 1.10, 20))
    door = np.stack([np.full_like(y, -.18), y, z], axis=-1)
    world = np.concatenate([shell, door], axis=1)
    secondary = world.copy()
    if dual_offset is not None:
        secondary[:, 20:, 0] += dual_offset
    shell_mask = np.zeros(world.shape[:2], dtype=bool)
    shell_mask[:, :20] = True
    door_mask = ~shell_mask
    queries = []

    def call(name, *, kwargs, timeout_s):
        queries.append(kwargs["text_prompt"])
        if primary_missing and base64.b64decode(kwargs["image_base64"]).startswith(b"agentview"):
            return {"instances": []}
        mask = (door_mask if frame_source == "door" else shell_mask) if "frame" in kwargs["text_prompt"] else (
            shell_mask if frame_source == "same" else door_mask)
        return {"instances": [{"mask": mask}]}

    def save(name, value, *, step):
        path = tmp_path / name
        np.savez_compressed(path, value)
        return path

    state = SimpleNamespace(latest_step=0, load_bytes=lambda name: name.encode(),
                            load=lambda name: {"extrinsic_cam2world": np.eye(4)} if name.endswith(".json") else
                            secondary if name.startswith("wrist") else world,
                            save=save, artifact_path=lambda name, step: tmp_path / name)
    monkeypatch.setattr(Sam3Client, "_decode_result", staticmethod(lambda item: SimpleNamespace(mask=item["mask"])))
    scene = MeasuredScene(SimpleNamespace(_state=state), SimpleNamespace(call=call), 0,
                          fixture_endpoint_geometry_v3=True, dual_view_fusion_v1=dual_offset is not None)
    parent = Entity("e1", "microwave", (0, .28, 1.02), (-.16, .245, .935), (.17, .34, 1.108))
    result = scene.measure_fixture_endpoint(parent, "microwave door")
    assert queries == ["front frame around the microwave door", "door of the microwave"] * (2 if dual_offset is not None else 1)
    assert (result["frame"] is not None) is frame_accepted
    assert (result["moving"] is not None) is (dual_offset != .03)
    if primary_missing:
        assert result["moving"]["source_cameras"] == ["wrist"]
    if frame_source == "door":
        assert result["measurement_counts"]["frame"]["outside_parent"] == 1
        assert result["frame"]["centre"][1] == pytest.approx(.25)
        assert "fixed_frame_geometry" in result
    if frame_source == "same":
        assert result["reason"] == "fixed_and_moving_faces_not_independent"


@pytest.mark.parametrize("enabled,mode", [(False, "close"), (True, "close"), (True, "open")])
def test_microwave_contact_prompt_names_the_moving_part_when_enabled(enabled, mode):
    from robots.libero.v5_state import Entity, Candidate

    obj = Entity("e1", "microwave", (0, 0, 1), (-.1, -.1, .9), (.1, .1, 1.1))
    executor = V5Executor(SimpleNamespace(primitives=SimpleNamespace()),
                          SimpleNamespace(entities={obj.id: obj}), fixture_part_prompt_v1=enabled)
    prompts = []
    executor._refresh = lambda names: None
    executor.vla_act = lambda prompt, *args: prompts.append(prompt) or {"executed": True}
    receipt = {}
    executor._execute(Candidate("articulate", obj.id, mode=mode), receipt, None)
    assert prompts == [mode + " the microwave" + (" door" if enabled else "")]


@pytest.mark.parametrize("enabled,held,terminated,truncated,release_terminates,recover", [
    (False, None, False, False, False, False),
    (True, None, False, False, False, True),
    (True, "e2", False, False, False, False),
    (True, None, True, False, False, False),
    (True, None, False, True, False, False),
    (True, None, False, False, True, True),
])
def test_articulation_view_recovery_releases_only_an_empty_gripper_before_retreat(
        enabled, held, terminated, truncated, release_terminates, recover):
    from robots.libero.v5_state import Entity, Candidate

    obj = Entity("e1", "microwave", (0, 0, 1), (-.1, -.1, .9), (.1, .1, 1.1))
    env = SimpleNamespace(terminated=terminated, truncated=truncated)
    events = []
    def release():
        events.append("release")
        env.terminated = env.terminated or release_terminates
    primitives = SimpleNamespace(env=env, _last_obs_gripper=.03, release=release)
    executor = V5Executor(SimpleNamespace(primitives=primitives),
                          SimpleNamespace(entities={obj.id: obj}),
                          articulate_view_retreat_v1=enabled)
    executor.held = held
    executor.vla_act = lambda *args: events.append("contact") or {"executed": True}
    executor.retreat = lambda: events.append("retreat")
    executor._refresh = lambda names: events.append("refresh")
    receipt = {}
    executor._execute(Candidate("articulate", obj.id, mode="close"), receipt, None)
    assert events == ["contact"] + (["release"] + ([] if release_terminates else ["retreat"])
                                   if recover else []) + ["refresh"]
    assert ("post_contact_recovery" in receipt) is recover
    assert executor.held == held


@pytest.mark.parametrize("door_y,clearance", [(0.02, 1.26), (.4, 1.20)])
def test_grasp_transit_clears_only_a_measured_fixture_on_the_path(door_y, clearance):
    import numpy as np
    from robots.libero.v5_state import Entity

    obj = Entity("e1", "mug", (0, 0, 1), (-.03, -.03, .95), (.03, .03, 1.05))
    door = Entity("e2", "microwave door", (-.18, door_y, 1.02),
                  (-.195, door_y - .01, .93), (-.175, door_y + .25, 1.11), part_of="e3")
    p = SimpleNamespace(_last_obs_eef_pos=np.array([-.21, 0., 1.16]), _last_obs_gripper=.08)
    executor = V5Executor(SimpleNamespace(primitives=p), SimpleNamespace(entities={obj.id: obj, door.id: door}))
    assert executor.grasp_transit_height(obj, [0., 0., 1.09]) == pytest.approx(clearance)


def test_failed_approach_records_executed_motion_without_claiming_grasp():
    import numpy as np
    from robots.libero.v5_state import Entity, Candidate

    obj = Entity("e1", "white yellow mug", (0, 0, 1), (-.03, -.03, .95), (.03, .03, 1.05))
    p = SimpleNamespace(_last_obs_eef_pos=np.array([0., 0., 1.2]), _last_obs_gripper=.08,
                        env=SimpleNamespace(terminated=False, truncated=False))
    p.move_to = lambda *args, **kwargs: {"steps_used": 80, "final_dist_m": .08}
    executor = V5Executor(SimpleNamespace(primitives=p), SimpleNamespace(entities={obj.id: obj}))
    executor.capture = lambda: None
    receipt = executor.execute(Candidate("grasp", obj.id, mode="direct"))
    assert receipt["executed"] is True
    assert receipt["verification"] == "execution_error"
    assert receipt["grasp_verified"] is False
    assert executor.held is None
    assert executor.motion_evidence[0]["steps_used"] == 80


@pytest.mark.parametrize("tool", ["grasp", "place", "adjust_place", "retreat"])
def test_unreached_waypoint_is_a_physical_failure_with_original_motion_evidence(tool):
    import numpy as np
    from robots.libero.v5_state import Candidate

    p = SimpleNamespace(_last_obs_eef_pos=np.array([0., 0., 1.]),
                        env=SimpleNamespace(terminated=False, truncated=False))
    evidence = {"steps_used": 80, "final_dist_m": .08, "target_xyz": [0., 0., 1.1]}
    p.move_to = lambda *args, **kwargs: evidence
    executor = V5Executor(SimpleNamespace(primitives=p), SimpleNamespace(), motion_outcome_v1=True)
    executor.capture = lambda: None
    executor._execute = lambda *args: executor.move([0., 0., 1.1], 0)
    receipt = executor.execute(Candidate(tool))
    assert receipt["verification"] == "failed"
    assert receipt["failure_reason"] == "waypoint_not_reached"
    assert receipt["executed"] and "error" not in receipt
    assert executor.motion_evidence == [evidence]
    assert ".08" in receipt["failure_detail"]
    if tool in ("place", "adjust_place"):
        assert receipt["place_verified"] is False


@pytest.mark.parametrize("native_flag", ["terminated", "truncated"])
def test_native_stop_during_servo_preserves_unreached_motion_without_runtime_error(native_flag):
    import numpy as np

    env = SimpleNamespace(terminated=False, truncated=False)
    p = SimpleNamespace(_last_obs_eef_pos=np.array([0., 0., 1.]), env=env)
    def move(*args, **kwargs):
        setattr(env, native_flag, True)
        return {"steps_used": 6, "final_dist_m": .2, native_flag: True}
    p.move_to = move
    executor = V5Executor(SimpleNamespace(primitives=p), SimpleNamespace(), motion_outcome_v1=True)
    assert executor.move([0., 0., 1.1], 0)[native_flag]
    assert len(executor.motion_evidence) == 1


@pytest.mark.parametrize("tool", ["place", "adjust_place"])
@pytest.mark.parametrize("opening", [.03, .08])
def test_occluded_held_object_keeps_measured_grasp_offset_only_while_gripper_holds(tool, opening):
    import numpy as np
    from robots.libero.v5_state import Candidate, Entity

    obj = Entity("e1", "tomato sauce", (0., 0., 1.), (-.03, -.03, .95),
                 (.03, .03, 1.05), visible=False)
    basket = Entity("e2", "basket", (.2, .2, 1.), (.1, .1, .9), (.3, .3, 1.1))
    env = SimpleNamespace(terminated=False, truncated=False)
    p = SimpleNamespace(_last_obs_eef_pos=np.array([0., 0., 1.2]),
                        _last_obs_gripper=opening, env=env)
    scene = SimpleNamespace(entities={obj.id: obj, basket.id: basket})
    executor = V5Executor(SimpleNamespace(primitives=p), scene,
                          held_occlusion_v1=True, adjust_place_v1=True)
    executor.held, executor.held_offset = obj.id, np.array([0., 0., .2])
    before_offset = executor.held_offset.copy()
    moves = []
    def move(xyz, gripper):
        moves.append(np.asarray(xyz).copy())
        raise LookupError("test stops at first real placement waypoint")
    executor.move = move
    executor.retreat = lambda: None
    executor._refresh = lambda names: None
    receipt = {}
    if opening == .03:
        with pytest.raises(LookupError, match="first real placement waypoint"):
            executor._execute(Candidate(tool, obj.id, basket.id, "in"), receipt, None)
        assert moves and receipt["held_geometry_source"] == "last_visual_grasp_measurement_and_gripper"
        np.testing.assert_array_equal(executor.held_offset, before_offset)
        assert not scene.entities[obj.id].visible
    else:
        executor._execute(Candidate(tool, obj.id, basket.id, "in"), receipt, None)
        assert not moves and receipt["place_verified"] is False
        assert receipt["failure_reason"] == "held_verification_lost"
        assert executor.held is executor.held_offset is None


@pytest.mark.parametrize("openings,released", [([.03, .08, .08, .08], True), ([.03] * 4, False)])
def test_contact_release_stop_requires_stable_open_gripper(openings, released):
    import numpy as np

    remaining = iter(openings)
    p = SimpleNamespace(_last_obs_eef_pos=np.array([0., 0., 1.]), _last_obs_gripper=.03,
                        env=SimpleNamespace(terminated=False, truncated=False))
    p._vlm_chunk = lambda prompt: setattr(p, "_last_obs_gripper", next(remaining))
    executor = V5Executor(SimpleNamespace(primitives=p), SimpleNamespace())
    result = executor.vla_act("put the mug inside the microwave", len(openings), "released_object")
    assert result["chunks"] == len(openings)
    assert result["object_released"] is released
    assert result["stop"] == ("released_object" if released else "chunk_budget")
    assert "grasp_verified" not in result


@pytest.mark.parametrize("released", [False, True])
@pytest.mark.parametrize("strict_flags,expected_rule", [
    ({"strict_place_v3": True}, "strict_place/3-dev"),
    ({"strict_place_v5": True}, "strict_place/5-dev"),
    ({"strict_place_v1": True, "strict_place_v4": True}, "strict_place/4-dev"),
    ({"strict_place_v1": True, "strict_place_v2": True,
      "strict_place_v3": True, "strict_place_v4": True}, "strict_place/4-dev"),
])
def test_fixture_contact_does_not_move_to_shell_or_claim_interior_verification(
        released, strict_flags, expected_rule):
    import numpy as np
    from robots.libero.v5_state import Entity, Candidate

    obj = Entity("e1", "white yellow mug", (0, 0, 1.), (-.03, -.03, .95), (.03, .03, 1.05))
    shell = Entity("e2", "microwave", (.2, .2, 1.), (.18, .1, .9), (.22, .3, 1.1))
    p = SimpleNamespace(_last_obs_eef_pos=np.array([0., 0., 1.2]), _last_obs_gripper=.08 if released else .03,
                        env=SimpleNamespace(terminated=False, truncated=False), set_gripper=lambda **kwargs: None)
    scene = SimpleNamespace(entities={obj.id: obj, shell.id: shell}, last_measurement_s={obj.name: 0.},
                            refresh=lambda *args, **kwargs: None)
    executor = V5Executor(SimpleNamespace(primitives=p, _state=SimpleNamespace(latest_step=2)),
                          scene, fixture_in_contact_v1=True, **strict_flags)
    executor.held, executor.held_offset = obj.id, np.array([0., 0., .2])
    moves, prompts = [], []
    executor.move = lambda *args, **kwargs: moves.append(args)
    executor.capture = executor.retreat = lambda: None
    executor._refresh = lambda *args: None
    def contact(prompt, max_chunks, stop):
        prompts.append((prompt, stop))
        return {"executed": True, "object_released": released, "chunks": 5,
                "stop": "released_object" if released else "chunk_budget"}
    executor.vla_act = contact
    receipt = {}
    executor._execute(Candidate("place", obj.id, shell.id, "in"), receipt, None)
    assert not moves
    assert prompts == [("put the white yellow mug inside the microwave", "released_object")]
    assert receipt["verification"] == "unmeasured"
    assert receipt["place_verified"] is (None if released else False)
    assert executor.held == (None if released else obj.id)
    if released:
        assert receipt["verification_rule"] == expected_rule
        assert receipt["verification_reason"] == "interior_containment_not_measured"


@pytest.mark.parametrize("tool", ["place", "adjust_place"])
@pytest.mark.parametrize("released", [False, True])
def test_drawer_surface_contact_preserves_selected_part_without_servo_descent(tool, released):
    import numpy as np
    from robots.libero.v5_state import Entity, Candidate

    obj = Entity("e15", "bowl", (.10, -.04, 1.097), (.042, -.089, 1.078), (.129, .004, 1.130))
    drawer = Entity("e47", "cabinet bottom drawer", (.007, .160, .924),
                    (-.105, .089, .921), (.107, .238, .984), source_step=8)
    p = SimpleNamespace(_last_obs_eef_pos=np.array([.071, .006, 1.100]),
                        _last_obs_gripper=.08 if released else .03,
                        env=SimpleNamespace(terminated=False, truncated=False),
                        set_gripper=lambda **kwargs: None)
    scene = SimpleNamespace(entities={obj.id: obj, drawer.id: drawer},
                            last_measurement_s={obj.name: 0.}, refresh=lambda *args, **kwargs: None)
    executor = V5Executor(SimpleNamespace(primitives=p, _state=SimpleNamespace(latest_step=8)),
                          scene, fixture_in_contact_v1=True, strict_place_v5=True, adjust_place_v1=True)
    executor.held, executor.held_offset = obj.id, np.array([-.029, .047, .003])
    moves, prompts = [], []
    executor.move = lambda *args, **kwargs: moves.append(args)
    executor.capture = executor.retreat = lambda: None
    executor._refresh = lambda *args: None
    def contact(prompt, max_chunks, stop):
        prompts.append((prompt, max_chunks, stop))
        return {"executed": True, "object_released": released, "chunks": 5,
                "stop": "released_object" if released else "chunk_budget"}
    executor.vla_act = contact
    receipt = {}
    executor._execute(Candidate(tool, obj.id, drawer.id, "in"), receipt, None)
    assert not moves
    assert prompts == [("put the bowl in the cabinet bottom drawer", executor.max_chunks, "released_object")]
    assert receipt["placement_controller"] == "fixture_contact/2-selected-drawer"
    assert receipt["place_verified"] is not True
    assert executor.held == (None if released else obj.id)
    if released:
        assert receipt["verification_rule"] == "strict_place/5-dev"


def test_drawer_surface_contact_refuses_ambiguous_measured_identity():
    import numpy as np
    from robots.libero.v5_state import Entity, Candidate

    obj = Entity("e1", "bowl", (0., 0., 1.1), (-.03, -.03, 1.05), (.03, .03, 1.15))
    drawer = Entity("e2", "drawer", (.2, .2, 1.), (.1, .1, .95), (.3, .3, 1.05))
    other = Entity("e3", "drawer", drawer.xyz, drawer.lower, drawer.upper)
    p = SimpleNamespace(_last_obs_eef_pos=np.array([0., 0., 1.2]), _last_obs_gripper=.03)
    executor = V5Executor(SimpleNamespace(primitives=p),
                          SimpleNamespace(entities={e.id: e for e in (obj, drawer, other)}),
                          fixture_in_contact_v1=True)
    executor.held, executor.held_offset = obj.id, np.array([0., 0., .1])
    calls = []
    executor.move = executor.vla_act = lambda *args, **kwargs: calls.append(args)
    receipt = {}
    executor._execute(Candidate("place", obj.id, drawer.id, "in"), receipt, None)
    assert not calls and executor.held == obj.id
    assert receipt == {"executed": False, "place_verified": None, "verification": "unmeasured",
                       "failure_reason": "selected_instance_not_uniquely_measured"}


@pytest.mark.parametrize("contact_enabled,cavity", [(False, False), (True, True)])
def test_drawer_cavity_or_legacy_setting_keeps_geometric_placement(contact_enabled, cavity):
    import numpy as np
    from robots.libero.v5_state import Entity, Candidate

    obj = Entity("e1", "bowl", (0., 0., 1.1), (-.03, -.03, 1.05), (.03, .03, 1.15))
    drawer = Entity("e2", "cabinet bottom drawer", (.2, .2, 1.), (.1, .1, .95), (.3, .3, 1.05),
                    geometry="measured_cavity" if cavity else None)
    p = SimpleNamespace(_last_obs_eef_pos=np.array([0., 0., 1.2]),
                        env=SimpleNamespace(terminated=False, truncated=False))
    executor = V5Executor(SimpleNamespace(primitives=p), SimpleNamespace(entities={e.id: e for e in (obj, drawer)}),
                          fixture_in_contact_v1=contact_enabled)
    executor.held, executor.held_offset = obj.id, np.array([0., 0., .1])
    def move(*args, **kwargs):
        raise LookupError("geometric placement waypoint")
    executor.move = move
    executor.vla_act = lambda *args, **kwargs: pytest.fail("measured cavity or legacy setting used contact fallback")
    with pytest.raises(LookupError, match="geometric placement waypoint"):
        executor._execute(Candidate("place", obj.id, drawer.id, "in"), {}, None)


def test_missing_distinct_microwave_door_does_not_relabel_shell_points(monkeypatch, tmp_path):
    import numpy as np
    from robots.libero.v5_runtime import MeasuredScene
    from robots.libero.v5_state import Entity

    state = SimpleNamespace(latest_step=0, load_bytes=lambda _: b"RGB",
        load=lambda name: {"extrinsic_cam2world": np.eye(4)} if name.endswith(".json") else np.zeros((10, 10, 3)),
        save=lambda name, value, step: tmp_path / name,
        artifact_path=lambda name, step: tmp_path / name)
    rpc = SimpleNamespace(call=lambda *args, **kwargs: {"instances": []})
    scene = MeasuredScene(SimpleNamespace(_state=state), rpc, 0,
                          furniture_parts_v1=True, microwave_door_cloud_v6=True, dual_view_fusion_v1=False)
    parent = Entity("e1", "microwave", (0, 0, 1.05), (-.2, -.2, .95), (.2, .2, 1.15))
    scene.fixture_measurement_evidence[parent.id] = {}
    assert scene._measure_microwave_door(parent, "agentview") == []
    assert scene.fixture_measurement_evidence[parent.id]["door_measurement"]["query"] == "door of the microwave"
    assert scene.calls == 1


@pytest.mark.parametrize("primary_visible,secondary_x,accepted", [
    (False, 0., True), (True, 0., True), (True, .12, False),
])
def test_distinct_door_uses_second_view_only_for_one_measured_plane(
        monkeypatch, tmp_path, primary_visible, secondary_x, accepted):
    import base64
    import numpy as np
    from robots.libero.v5_runtime import MeasuredScene
    from robots.libero.v5_state import Entity
    from rpent.robots.components.sam3_client import Sam3Client

    yy, zz = np.meshgrid(np.linspace(-.12, .12, 20), np.linspace(.96, 1.14, 20))
    primary = np.stack([np.zeros_like(yy), yy, zz], axis=-1)
    secondary = primary.copy()
    secondary[..., 0] = secondary_x
    worlds = {"agentview": primary, "wrist": secondary}
    def load(name):
        if name.endswith("metadata.json"):
            return {"extrinsic_cam2world": np.eye(4)}
        return worlds[name.split("_")[0]]
    def save(name, value, step):
        np.savez_compressed(tmp_path / name, value)
        return tmp_path / name
    state = SimpleNamespace(latest_step=0, load_bytes=lambda name: name.encode(),
                            load=load, save=save, artifact_path=lambda name, step: tmp_path / name)
    def call(name, kwargs, timeout_s):
        view = base64.b64decode(kwargs["image_base64"]).decode().split("_")[0]
        return {"instances": [] if view == "agentview" and not primary_visible else [{"score": .9}]}
    monkeypatch.setattr(Sam3Client, "_decode_result", staticmethod(
        lambda item: SimpleNamespace(mask=np.ones((20,20), dtype=bool))))
    scene = MeasuredScene(SimpleNamespace(_state=state), SimpleNamespace(call=call), 0,
                          furniture_parts_v1=True, microwave_door_cloud_v6=True, dual_view_fusion_v1=True)
    parent = Entity("e1", "microwave", (0., 0., 1.05), (-.2, -.2, .95), (.2, .2, 1.15))
    scene.fixture_measurement_evidence[parent.id] = {}
    parts = scene._measure_microwave_door(parent, "agentview")
    assert bool(parts) is accepted
    assert scene.calls == 2
    evidence = scene.fixture_measurement_evidence[parent.id]["door_measurement"]
    if accepted:
        assert evidence["source_cameras"] == (["agentview", "wrist"] if primary_visible else ["wrist"])
        assert parts[0]["geometry"] == "measured_door_surface"
        assert evidence["sha256"]
    else:
        assert evidence["reason"] == "door_views_not_one_adjacent_plane"


def test_fixture_support_does_not_collect_other_objects_inside_its_bounds(tmp_path):
    import numpy as np
    from robots.libero.v5_runtime import MeasuredScene
    from robots.libero.v5_state import Entity

    def save(name, points, step):
        np.savez_compressed(tmp_path / name, points)
        return tmp_path / name
    state = SimpleNamespace(latest_step=0, save=save, artifact_path=lambda name,step:tmp_path/name,
                            load=lambda _: {"extrinsic_cam2world": np.eye(4)})
    scene = MeasuredScene(SimpleNamespace(_state=state), None, 0, furniture_parts_v1=True)
    parent = Entity("e1","microwave",(0.,0.,1.),(-.1,-.1,.9),(.1,.1,1.1))
    scene.entities = {parent.id:parent}
    world = np.full((6,6,3),(.01,.02,1.))
    mask = np.zeros((6,6),dtype=bool);mask[:3] = True
    scene.measurement_clouds[parent.id] = world[mask].copy()
    scene.refresh_fixture_parts(world,{parent.id:mask})
    evidence = scene.fixture_measurement_evidence[parent.id]
    with np.load(evidence["path"]) as data:
        assert len(data[data.files[0]]) == mask.sum()
    assert evidence["point_selection"] == "segmented_instance_clouds_rgbd/2-dev"


@pytest.mark.parametrize("enabled", [False, True])
def test_measured_mug_rim_can_precede_handle_without_forcing_wrist_yaw(monkeypatch, enabled):
    import numpy as np
    from robots.libero.v5_state import Entity, Candidate
    from robots.libero import v5_perception_geometry

    obj = Entity("e1", "white yellow mug", (0., 0., 1.), (-.03,-.03,.95), (.03,.03,1.05))
    calls = []
    scene = SimpleNamespace(measurement_clouds={obj.id: np.ones((30, 3))},
                            measure_handle=lambda _: calls.append("handle") or (.08, 0., 1.),
                            view_axes=((1,0,0),(0,1,0)))
    p = SimpleNamespace(_last_obs_eef_pos=np.array([0.,0.,1.2]))
    monkeypatch.setattr(v5_perception_geometry, "measured_rim_point", lambda *args: (.02, .01, 1.05))
    executor = V5Executor(SimpleNamespace(primitives=p), scene, measured_rim_v2=True, mug_rim_first_v3=enabled)
    pose, kind, yaw = executor.grasp_approach(obj, Candidate("grasp",obj.id,mode="direct"))
    assert pose[:2] == ([.02,.01] if enabled else [.08,0.])
    assert calls == ([] if enabled else ["handle"])
    assert kind == ("measured_visible_rim" if enabled else "measured_handle")
    assert yaw is None


@pytest.mark.parametrize("enabled", [False, True])
def test_measured_moka_handle_keeps_contact_policy_yaw_when_enabled(enabled):
    import numpy as np
    from robots.libero.v5_state import Entity, Candidate

    obj = Entity("e1", "moka pot", (0.,0.,1.), (-.03,-.03,.95), (.03,.03,1.05))
    scene = SimpleNamespace(measure_handle=lambda _: (0.,.05,1.), view_axes=((1,0,0),(0,1,0)))
    p = SimpleNamespace(_last_obs_eef_pos=np.array([0.,0.,1.2]))
    executor = V5Executor(SimpleNamespace(primitives=p), scene, handle_free_yaw_v2=enabled)
    pose, kind, yaw = executor.grasp_approach(obj, Candidate("grasp",obj.id,mode="direct"))
    assert pose[:2] == [0.,.05]
    assert kind == "measured_handle"
    assert yaw == (None if enabled else pytest.approx(np.pi/2))


@pytest.mark.parametrize("enabled", [False, True])
@pytest.mark.parametrize("refreshed", ["microwave", "bowl"])
def test_missing_refreshed_fixture_does_not_leave_old_part_visible(monkeypatch, enabled, refreshed):
    import numpy as np
    from robots.libero.v5_runtime import MeasuredScene
    from robots.libero.v5_state import Entity, candidates
    import random

    state = SimpleNamespace(latest_step=5, load_bytes=lambda _: b"RGB",
        load=lambda name: {"extrinsic_cam2world": np.eye(4)} if name.endswith(".json") else np.zeros((10, 10, 3)))
    scene = MeasuredScene(SimpleNamespace(_state=state),
        SimpleNamespace(call=lambda *args, **kwargs: {"instances": []}), 1,
        furniture_parts_v1=True, fixture_part_visibility_v2=enabled)
    parent = Entity("e1", "microwave", (0, 0, 1), (-.2, -.2, .9), (.2, .2, 1.2),
                    visible=refreshed == "microwave", source_step=4)
    part = Entity("e2", "microwave door", (0, 0, 1), (-.2, -.01, .9), (.2, .01, 1.2),
                  source_step=4, part_of="e1", geometry="measured_door_surface")
    scene.entities = {parent.id: parent, part.id: part}
    scene.refresh([refreshed])
    invalidated = enabled and refreshed == "microwave"
    assert scene.entities[part.id].visible is not invalidated
    assert scene.entities[part.id].xyz == part.xyz
    choices = candidates(list(scene.entities.values()), "open microwave door", (0, 0, 1),
                         None, [], random.Random(1))
    assert any(c.tool == "articulate" and c.object == part.id for c in choices) is not invalidated


@pytest.mark.parametrize("intermittent", [False, True])
@pytest.mark.parametrize("footprint", [False, True])
def test_repeated_rejected_background_mask_keeps_identity_without_entering_state(monkeypatch, intermittent, footprint):
    import numpy as np
    from robots.libero.v5_runtime import MeasuredScene
    from rpent.robots.components.sam3_client import Sam3Client

    world = np.zeros((10, 10, 3))
    world[:] = (-1.4, 1.4, 1.3) if footprint else (.1, .2, .5)
    state = SimpleNamespace(latest_step=0, load_bytes=lambda _: b"RGB",
        load=lambda name: {"extrinsic_cam2world": np.eye(4)} if name.endswith(".json") else world)
    monkeypatch.setattr(Sam3Client, "_decode_result", staticmethod(lambda item: SimpleNamespace(mask=np.ones((10,10), dtype=bool))))
    rpc = SimpleNamespace(call=lambda *args, **kwargs: {
        "instances": [] if intermittent and state.latest_step % 2 else [{"score": .9}]})
    scene = MeasuredScene(SimpleNamespace(_state=state), rpc, 1,
                          fixture_support_filter_v1=True, fixture_identity_cache_v1=True,
                          fixture_support_footprint_v2=footprint)
    scene.support_z = .9
    scene.work_surface_measurement = {
        "lower": [-.48, -.36, .9], "upper": [.27, .31, .9], "height_m": .9}
    remaining = len(scene._ids)
    for step in range(140):
        state.latest_step = step
        scene.refresh(["cabinet"])
        assert not scene.entities
        assert len(scene._ids) == remaining - 1
    assert len(scene._rejected_fixture_entities) == 1
    assert len({row["measurement"]["id"] for row in scene.rejected_fixture_measurements}) == 1
    expected = ("fixture_footprint_outside_measured_work_surface" if footprint
                else "entire_detection_below_measured_work_surface")
    assert {row["reason"] for row in scene.rejected_fixture_measurements} == {expected}


@pytest.mark.parametrize("approach,local,short,extended", [
    (True, False, False, False), (True, True, False, True),
    (False, False, False, True), (False, False, True, False),
])
def test_shape_approach_can_keep_the_staged_gripper_reference_in_contact_prompt(approach, local, short, extended):
    import numpy as np
    from robots.libero.v5_state import Entity, Candidate

    obj = Entity("e1", "white yellow mug", (0,0,1), (-.03,-.03,.95), (.03,.03,1.05))
    p = SimpleNamespace(_last_obs_eef_pos=np.array([0.,0.,1.2]), _last_obs_gripper=.08,
                        env=SimpleNamespace(terminated=False, truncated=False))
    scene = SimpleNamespace(entities={"e1":obj}, measure_handle=lambda _:None, view_axes=((1,0,0),(0,1,0)))
    executor = V5Executor(SimpleNamespace(primitives=p), scene, grasp_approach_v1=approach,
                          grasp_local_prompt_v1=local, grasp_short_prompt_v2=short)
    calls = []
    executor.move = lambda *args: None
    executor._refresh = lambda *args: None
    def contact(prompt, *args, **kwargs):
        calls.append(prompt)
        return {"grasp_verified":False,"stop":"chunk_budget"}
    executor.vla_act = contact
    executor._execute(Candidate("grasp","e1",mode="direct"), {}, None)
    assert calls == ["pick up the white yellow mug" + (" directly below the gripper" if extended else "")]


@pytest.mark.parametrize("held", [None, "e1"])
def test_view_recovery_retreat_preserves_gripper_without_claiming_held(held):
    import numpy as np

    p = SimpleNamespace(_last_obs_eef_pos=np.array([0., 0., 1.]), _last_obs_gripper=.03)
    executor = V5Executor(SimpleNamespace(primitives=p), SimpleNamespace())
    executor.held = held
    motions = []
    executor.move = lambda xyz, gripper: motions.append((xyz.tolist(), gripper))
    executor.retreat()
    assert motions == [([0., 0., 1.1], 0)]
    assert executor.held == held


def test_repeated_view_retreat_returns_to_observed_start_pose_without_cumulative_lifts():
    import numpy as np

    p = SimpleNamespace(_last_obs_eef_pos=np.array([-.05, .001, .69]), _last_obs_gripper=.03)
    executor = V5Executor(SimpleNamespace(primitives=p), SimpleNamespace(), view_retreat_v2=True)
    executor.held = "e1"
    motions = []

    def move(xyz, gripper):
        motions.append((xyz.tolist(), gripper))
        p._last_obs_eef_pos[:] = xyz

    executor.move = move
    p._last_obs_eef_pos[:] = [-.18, .73, .93]
    executor.retreat()
    executor.retreat()
    assert motions == [([-.05, .001, .69], 0)] * 2
    assert executor.held == "e1"


@pytest.mark.parametrize("enabled", [False, True])
def test_retreat_clearance_carries_above_fixture_before_descending(enabled):
    import numpy as np
    from robots.libero.v5_state import Entity

    cabinet = Entity("e1", "cabinet", (.04, -.24, 1.02),
                     (-.08, -.33, .92), (.16, -.16, 1.13))
    home = np.array([-.21, .014, 1.17])
    p = SimpleNamespace(_last_obs_eef_pos=home.copy(), _last_obs_gripper=.08)
    executor = V5Executor(SimpleNamespace(primitives=p),
        SimpleNamespace(entities={cabinet.id: cabinet}),
        view_retreat_v2=True, retreat_clearance_v1=enabled)
    start = np.array([.045, -.24, 1.256])
    p._last_obs_eef_pos[:] = start
    motions = []

    def move(xyz, gripper):
        motions.append((np.asarray(xyz), gripper))
        p._last_obs_eef_pos[:] = xyz

    executor.move = move
    executor.retreat()
    assert np.allclose(motions[-1][0], home)
    assert all(command == 0 for _, command in motions)
    if enabled:
        assert len(motions) == 3
        assert np.allclose(motions[0][0][:2], start[:2])
        assert motions[0][0][2] >= cabinet.upper[2] + .15
        assert np.allclose(motions[1][0][:2], home[:2])
        assert motions[1][0][2] == motions[0][0][2]
    else:
        assert len(motions) == 1


@pytest.mark.parametrize("enabled,measurement_z", [(False, 1.09), (True, 1.20)])
def test_wrist_measurement_standoff_keeps_the_contact_approach_after_refinement(enabled, measurement_z):
    import numpy as np
    from robots.libero.v5_state import Entity, Candidate

    obj = Entity("e1", "moka pot", (0, 0, 1), (-.03, -.03, .95), (.03, .03, 1.05))
    p = SimpleNamespace(_last_obs_eef_pos=np.array([0., 0., 1.3]), _last_obs_gripper=.08,
                        env=SimpleNamespace(terminated=False, truncated=False))
    cameras, waypoints = [], []
    scene = SimpleNamespace(entities={obj.id: obj}, refresh=lambda names, **kw: cameras.append(kw["camera_view"]))
    executor = V5Executor(SimpleNamespace(primitives=p), scene, wrist_refine_v1=True,
                          wrist_measurement_standoff_v2=enabled)
    executor.move = lambda xyz, gripper: waypoints.append(list(xyz))
    executor.capture = lambda: None
    executor._refresh = lambda names: None
    executor.vla_act = lambda *args, **kwargs: {"grasp_verified": False, "stop": "chunk_budget"}
    executor._execute(Candidate("grasp", obj.id, mode="direct"), {}, None)
    assert cameras == ["wrist"]
    assert waypoints[0] == pytest.approx([0, 0, measurement_z])
    assert waypoints[1] == pytest.approx([0, 0, 1.09])


def test_table_centre_reference_adds_a_measured_table_to_scene_vocabulary():
    assert "table" in scene_vocabulary(["akita_black_bowl_1"], "pick up the bowl from table center")
    assert "table" in scene_vocabulary(["akita_black_bowl_1"], "pick up the bowl from table centre")
    assert "table" not in scene_vocabulary(["akita_black_bowl_1"], "pick up the bowl")


def test_distinct_stacked_masks_keep_both_public_categories(monkeypatch):
    import numpy as np

    from robots.libero.v5_runtime import MeasuredScene
    from rpent.robots.components.sam3_client import Sam3Client

    world = np.zeros((10, 10, 3))
    world[:5, :, :] = (0, 0, 1)
    world[5:, :, :] = (0.01, 0, 0.99)
    state = SimpleNamespace(latest_step=0, load_bytes=lambda _: b"RGB",
                           load=lambda name: {"extrinsic_cam2world": np.eye(4)} if name.endswith(".json") else world)
    def segment(_, kwargs, **unused):
        mask = np.zeros((10, 10), dtype=bool)
        if kwargs["text_prompt"] == "black patterned bowl":
            mask[:5] = True
        else:
            mask[5:] = True
        return {"instances": [{"score": 0.9 if mask[5, 0] else 0.8, "mask": mask}]}
    monkeypatch.setattr(Sam3Client, "_decode_result", staticmethod(lambda item: SimpleNamespace(mask=item["mask"])))
    scene = MeasuredScene(SimpleNamespace(_state=state), SimpleNamespace(call=segment), 1)
    scene.refresh(["bowl", "cookie box"])
    assert sorted(e.name for e in scene.entities.values()) == ["bowl", "cookie box"]


def test_moka_geometry_excludes_pan_measured_in_the_same_frame(monkeypatch):
    import numpy as np

    from robots.libero.v5_runtime import MeasuredScene
    from rpent.robots.components.sam3_client import Sam3Client

    world = np.zeros((10, 10, 3))
    world[:, :7] = (-.1, 0, .93)
    world[:, 7:] = (.1, 0, 1.01)
    state = SimpleNamespace(latest_step=0, load_bytes=lambda _: b"RGB",
                            load=lambda name: {"extrinsic_cam2world": np.eye(4)}
                            if name.endswith(".json") else world)
    queried = []

    def segment(_, kwargs, **unused):
        queried.append(kwargs["text_prompt"])
        mask = np.ones((10, 10), dtype=bool)
        if kwargs["text_prompt"] == "black frying pan":
            mask[:, 7:] = False
        return {"instances": [{"score": .9, "mask": mask}]}

    monkeypatch.setattr(Sam3Client, "_decode_result",
                        staticmethod(lambda item: SimpleNamespace(mask=item["mask"])))
    scene = MeasuredScene(SimpleNamespace(_state=state), SimpleNamespace(call=segment), 1)
    scene.vocabulary.add("frypan")
    scene.dual_view_fusion_v1 = False  # This case isolates primary-camera mask exclusion.
    scene.refresh(["moka pot"])
    measured = {e.name: e for e in scene.entities.values()}
    assert queried == ["black frying pan", "silver moka coffee pot"]
    assert measured["moka pot"].xyz == (.1, 0, 1.01)
    assert measured["frypan"].xyz == (-.1, 0, .93)


@pytest.mark.parametrize("ambiguous", [False, True])
def test_wrist_placement_never_uses_target_to_disambiguate_same_class_masks(monkeypatch, ambiguous):
    import numpy as np

    from robots.libero.v5_runtime import MeasuredScene
    from robots.libero.v5_state import Entity
    from rpent.robots.components.sam3_client import Sam3Client

    world = np.empty((12, 12, 3))
    world[:4] = (0, 0, .12)
    world[4:8] = (.05 if ambiguous else .4, 0, .12)
    world[8:] = (.4, 0, .12)
    masks = []
    for start in (0, 4):
        mask = np.zeros((12, 12), dtype=bool)
        mask[start:start + 4] = True
        masks.append(mask)
    state = SimpleNamespace(latest_step=1,
        load_bytes=lambda name: b"RGB" if name == "wrist_high.png" else None,
        load=lambda name: {"extrinsic_cam2world": np.eye(4)}
        if name == "agentview_metadata.json" else world)

    def segment(_, kwargs, **unused):
        assert kwargs["text_prompt"] == "top of a can"
        return {"instances": [{"score": .7, "mask": masks[0]},
                              {"score": .95, "mask": masks[1]}]}

    monkeypatch.setattr(Sam3Client, "_decode_result",
                        staticmethod(lambda item: SimpleNamespace(mask=item["mask"])))
    selected = Entity("e1", "alphabet soup", (-.2, 0, .2), (-.23, -.03, .1), (-.17, .03, .3), visible=False)
    other = Entity("e2", "alphabet soup", (.4, 0, .12), (.37, -.03, .09), (.43, .03, .15))
    target = Entity("e3", "basket", (0, 0, .1), (-.1, -.1, .05), (.1, .1, .2))
    scene = MeasuredScene(SimpleNamespace(_state=state), SimpleNamespace(call=segment), 1)
    scene.entities = {e.id: e for e in (selected, other, target)}
    scene.dual_view_fusion_v1 = False  # The placement-binding fixture provides one camera.
    scene.instance_limits = {"alphabet soup": 1}
    scene.refresh([selected.name], placement=(selected, target))
    assert scene.entities[other.id] == other
    assert scene.entities[selected.id].visible is False
    assert scene.entities[selected.id].xyz == selected.xyz


def test_duplicate_package_detection_keeps_the_supplied_scene_categories(monkeypatch):
    import numpy as np

    from robots.libero.v5_runtime import MeasuredScene
    from rpent.robots.components.sam3_client import Sam3Client

    world = np.zeros((10, 10, 3))
    world[:5] = (0, 0, 1)
    world[5:] = (0.2, 0, 1)
    butter_mask = np.zeros((10, 10), dtype=bool)
    butter_mask[:5] = True
    pudding_mask = ~butter_mask
    state = SimpleNamespace(latest_step=0, load_bytes=lambda _: b"RGB",
                           load=lambda name: {"extrinsic_cam2world": np.eye(4)} if name.endswith(".json") else world)

    def segment(_, kwargs, **unused):
        if kwargs["text_prompt"] == "small red box":
            return {"instances": [{"score": .64, "mask": butter_mask}]}
        return {"instances": [{"score": .68, "mask": pudding_mask},
                              {"score": .66, "mask": butter_mask}]}

    monkeypatch.setattr(Sam3Client, "_decode_result", staticmethod(lambda item: SimpleNamespace(mask=item["mask"])))
    scene = MeasuredScene(SimpleNamespace(_state=state), SimpleNamespace(call=segment), 1)
    scene.instance_limits = {"butter": 1, "chocolate pudding": 1}
    scene.dual_view_fusion_v1 = False  # This case isolates duplicate primary detections.
    scene.refresh(["butter", "chocolate pudding"])
    assert sorted(e.name for e in scene.entities.values()) == ["butter", "chocolate pudding"]
    assert next(e for e in scene.entities.values() if e.name == "butter").xyz == (0, 0, 1)
    assert next(e for e in scene.entities.values() if e.name == "chocolate pudding").xyz == (.2, 0, 1)


def test_front_destination_uses_measured_stove_bounds_and_table_support_only():
    import random

    from robots.libero.v5_runtime import MeasuredScene
    from robots.libero.v5_state import Entity, candidates, entity_record

    scene = MeasuredScene.__new__(MeasuredScene)
    scene.entities = {"e1": Entity("e1", "stove", (0, 0, 1), (-.08, -.08, .9), (.08, .08, 1.1)),
                      "e2": Entity("e2", "plate", (-.3, 0, .9), (-.35, -.05, .89), (-.25, .05, .91))}
    scene.view_axes = ((0, 1, 0), (1, 0, 0))
    scene.instruction = "push the plate to the front of the stove"
    scene._ids = ["e7"]
    scene.refresh_instruction_regions()
    region = scene.entities["e7"]
    assert region.xyz[0] > scene.entities["e1"].upper[0]
    assert region.xyz[2] == .89
    assert entity_record(region)["extent"] == "measured_anchor_region"
    actions = candidates(list(scene.entities.values()), scene.instruction, (0, 0, 1.2), None, [], random.Random(1))
    assert not any(c.tool == "grasp" and c.object == region.id for c in actions)


@pytest.mark.parametrize("enabled", [False, True])
def test_region_anchor_retains_pre_occlusion_measurement(enabled):
    from dataclasses import replace
    from robots.libero.v5_runtime import MeasuredScene
    from robots.libero.v5_state import Entity

    scene = MeasuredScene.__new__(MeasuredScene)
    plate = Entity("e1", "plate", (.17, .016, .447), (.11, -.045, .441), (.232, .077, .453),
                   source_step=0)
    scene.entities = {plate.id: plate}
    scene.view_axes = ((0, 1, 0), (1, 0, 0))
    scene.instruction = "put the pudding to the right of the plate"
    scene._ids = ["e7"]
    scene.region_anchor_cache_v1 = enabled
    scene.region_anchors = {}
    scene.refresh_instruction_regions()
    initial = scene.entities["e7"]
    scene.entities[plate.id] = replace(plate, xyz=(.194, .034, .447), source_step=4)
    scene.refresh_instruction_regions()
    after = scene.entities["e7"]
    assert after.xyz[:2] == (initial.xyz[:2] if enabled else (.194, .155))
    assert after.source_step == (0 if enabled else 4)


@pytest.mark.parametrize("enabled", [False, True])
def test_measured_destination_disappears_when_its_anchor_is_not_unique(enabled):
    from dataclasses import replace

    from robots.libero.v5_runtime import MeasuredScene
    from robots.libero.v5_state import Entity

    scene = MeasuredScene.__new__(MeasuredScene)
    scene.entities = {"e1": Entity("e1", "stove", (0, 0, 1), (-.08, -.08, .9), (.08, .08, 1.1)),
                      "e2": Entity("e2", "plate", (-.3, 0, .9), (-.35, -.05, .89), (-.25, .05, .91))}
    scene.view_axes = ((0, 1, 0), (1, 0, 0))
    scene.instruction = "push the plate to the front of the stove"
    scene._ids = ["e7"]
    scene.region_anchor_cache_v1 = enabled
    scene.region_anchors = {}
    scene.refresh_instruction_regions()
    scene.entities["e1"] = replace(scene.entities["e1"], visible=False)
    scene.refresh_instruction_regions()
    assert not scene.entities["e7"].visible
    scene.entities["e1"] = replace(scene.entities["e1"], visible=True)
    scene.refresh_instruction_regions()
    assert scene.entities["e7"].visible
    scene.entities["e3"] = replace(scene.entities["e1"], id="e3")
    scene.refresh_instruction_regions()
    assert not scene.entities["e7"].visible


def test_composite_capture_updates_the_real_toolkit_completion_cache(monkeypatch):
    toolkit = LiberoToolkit.__new__(LiberoToolkit)
    toolkit._primitives = SimpleNamespace(recorded_frame_count=lambda: 1)
    toolkit._state = object()
    toolkit._solved = False
    toolkit._action_frame_cursor = 0
    toolkit._dashboard_events = SimpleNamespace(enabled=False)
    monkeypatch.setattr(
        tools,
        "dump_state",
        lambda *a, **kw: SimpleNamespace(terminated=True, step_idx=1),
    )
    monkeypatch.setattr(tools, "view_env_state", lambda *a, **kw: {})
    assert not toolkit.solved()
    V5Executor(toolkit, SimpleNamespace()).capture()
    assert toolkit.solved()


def test_package_aliases_do_not_conflate_the_two_original_cans():
    assert segmentation_prompt("alphabet soup") == "blue can"
    assert segmentation_prompt("tomato sauce") == "red tomato sauce can"
    assert segmentation_prompt("milk") == "carton labeled Milk"


def test_instruction_fixtures_are_queried_even_when_not_movable_observation_keys():
    from robots.libero.v5_runtime import scene_vocabulary

    assert "rack" in scene_vocabulary(["wine_bottle_1"], "put the wine bottle on the rack")
    vocab = scene_vocabulary(["black_book_1"], "put the book in the back compartment of the caddy")
    assert "caddy" in vocab and "compartment" in vocab
    assert "caddy" not in scene_vocabulary(["black_book_1"], "pick up the book")


def test_reperceive_retries_scene_categories_that_had_no_initial_detection():
    from robots.libero.v5_state import Candidate

    scene = SimpleNamespace(entities={}, vocabulary={"cream cheese", "basket"})
    executor = V5Executor(SimpleNamespace(primitives=None), scene)
    queried = []
    executor._refresh = lambda names: queried.extend(names)
    executor._execute(Candidate("reperceive"), {}, None)
    assert queried == ["basket", "cream cheese"]


def test_articulation_preserves_the_public_middle_drawer_reference():
    from robots.libero.v5_state import Candidate, Entity

    cabinet = Entity("e9", "cabinet", (0, 0, 1), (0, 0, 0.9), (0.2, 0.2, 1.2))
    executor = V5Executor(
        SimpleNamespace(primitives=None),
        SimpleNamespace(entities={"e9": cabinet}),
        instruction="open the middle drawer of the cabinet",
    )
    prompts = []
    executor.vla_act = lambda prompt, *a: prompts.append(prompt) or {"executed": True}
    executor._refresh = lambda names: None
    receipt = {}
    executor._execute(Candidate("articulate", "e9", mode="open"), receipt, None)
    assert prompts == ["open the middle drawer of the cabinet"]
    assert receipt["verification"] == "unmeasured"


def test_measured_drawer_part_refreshes_its_cabinet_after_articulation():
    from robots.libero.v5_state import Candidate, Entity

    cabinet = Entity("e9", "cabinet", (0, 0, 1), (0, 0, .9), (.2, .2, 1.2))
    drawer = Entity("e8", "cabinet middle drawer", (0, .2, 1),
                    (0, .19, .98), (.2, .21, 1.02), part_of="e9")
    executor = V5Executor(SimpleNamespace(primitives=None),
                          SimpleNamespace(entities={"e9": cabinet, "e8": drawer},
                                          fixture_handle_geometry_v3=True))
    executor.vla_act = lambda *args: {"executed": True}
    refreshed = []
    executor._refresh = lambda names: refreshed.extend(names)
    executor._execute(Candidate("articulate", "e8", mode="open"), {}, None)
    assert refreshed == ["cabinet", "drawer"]


@pytest.mark.parametrize("selected", [False, True])
@pytest.mark.parametrize("part_of", [None, "e8"])
def test_selected_drawer_is_not_overridden_by_another_drawer_in_instruction(selected, part_of):
    from robots.libero.v5_state import Candidate, Entity

    drawer = Entity("e9", "cabinet top drawer", (0, 0, 1),
                    (0, 0, .9), (.2, .2, 1.2), part_of=part_of)
    executor = V5Executor(
        SimpleNamespace(primitives=None), SimpleNamespace(entities={"e9": drawer}),
        instruction="close the bottom drawer of the cabinet",
        selected_fixture_target_v1=selected,
    )
    prompts = []
    executor.vla_act = lambda prompt, *args: prompts.append(prompt) or {"executed": True}
    executor._refresh = lambda names: None
    executor._execute(Candidate("articulate", "e9", mode="close"), {}, None)
    assert prompts == ["close the cabinet top drawer" if selected
                       else "close the bottom drawer of the cabinet"]


def test_selected_fixture_switch_keeps_language_binding_for_generic_cabinet():
    from robots.libero.v5_state import Candidate, Entity

    cabinet = Entity("e9", "cabinet", (0, 0, 1), (0, 0, .9), (.2, .2, 1.2))
    executor = V5Executor(
        SimpleNamespace(primitives=None), SimpleNamespace(entities={"e9": cabinet}),
        instruction="open the bottom drawer of the cabinet",
        selected_fixture_target_v1=True,
    )
    prompts = []
    executor.vla_act = lambda prompt, *args: prompts.append(prompt) or {"executed": True}
    executor._refresh = lambda names: None
    executor._execute(Candidate("articulate", "e9", mode="open"), {}, None)
    assert prompts == ["open the bottom drawer of the cabinet"]


@pytest.mark.parametrize("mode,clearance,release_z", [
    ("in", False, .23), ("in", True, .27), ("on", True, .23),
])
def test_place_clears_the_measured_rim_and_reuses_grasp_offset(mode, clearance, release_z):
    import numpy as np

    from robots.libero.v5_state import Candidate, Entity

    obj = Entity(
        "e1", "alphabet soup", (0, 0, 0.15), (-0.03, -0.03, 0.11), (0.03, 0.03, 0.19)
    )
    basket = Entity(
        "e2", "basket", (0.177, 0.329, 0.1), (0.02, 0.17, 0.04), (0.18, 0.33, 0.18)
    )
    p = SimpleNamespace(
        _last_obs_eef_pos=np.array([0.07, 0.24, 0.14]),
        env=SimpleNamespace(terminated=False, truncated=False),
    )
    scene = SimpleNamespace(entities={"e1": obj, "e2": basket})
    executor = V5Executor(SimpleNamespace(primitives=p), scene,
                          in_release_clearance_v1=clearance)
    executor.held = "e1"
    executor.held_offset = np.array([0, 0, 0.01])
    waypoints = []

    def move(xyz, gripper):
        waypoints.append(np.asarray(xyz).copy())
        if len(waypoints) == 3:
            raise RuntimeError("stop after waypoint probe")

    executor.move = move
    try:
        executor._execute(Candidate("place", "e1", "e2", mode), {}, None)
    except RuntimeError:
        pass
    np.testing.assert_allclose(waypoints[0][:2], p._last_obs_eef_pos[:2])
    assert waypoints[1][2] >= basket.upper[2] + 0.04 + 0.01 + 0.1
    np.testing.assert_allclose(waypoints[1][:2], [0.1, 0.25])
    np.testing.assert_allclose(waypoints[2], [0.1, 0.25, release_z])


def test_v5_chunk_stops_before_actions_after_native_termination():
    import numpy as np

    from robots.libero.v5_env_server import V5EnvFacade

    facade = V5EnvFacade.__new__(V5EnvFacade)
    calls = []

    def step(action):
        calls.append(action)
        return {"step": len(calls)}, 1.0, len(calls) == 2, False, {}

    facade.step = step
    obs, rewards, term, trunc, _ = facade.chunk_step(
        np.zeros((50, 7)), return_all_frames=True
    )
    assert len(calls) == len(obs) == len(rewards) == 2
    assert term.tolist() == [False, True]
    assert not trunc.any()


@pytest.mark.parametrize(
    "initially_interrupted,interrupt_after,budget,expected_chunks,expected_stop",
    [(True, None, 4, 0, "execution_interrupted"),
     (False, 1, 4, 1, "execution_interrupted"),
     (False, 1, 1, 1, "execution_interrupted"),
     (False, None, 2, 2, "chunk_budget")],
)
def test_contact_receipt_reports_actual_stop_without_claiming_grasp(
    initially_interrupted, interrupt_after, budget, expected_chunks, expected_stop
):
    from robots.libero.v5_state import Entity

    env = SimpleNamespace(terminated=initially_interrupted, truncated=False)
    calls = []

    def chunk(prompt):
        calls.append(prompt)
        env.truncated = len(calls) == interrupt_after

    obj = Entity("e1", "bowl", (0, 0, 1), (0, 0, .9), (.1, .1, 1.1))
    p = SimpleNamespace(env=env, _last_obs_gripper=0, _vlm_chunk=chunk)
    executor = V5Executor(SimpleNamespace(primitives=p), SimpleNamespace())
    receipt = executor.vla_act("pick up the bowl", budget, "grasp_verified", obj)
    assert receipt["executed"] == (expected_chunks > 0)
    assert len(calls) == receipt["chunks"] == expected_chunks
    assert receipt["stop_condition"] == "grasp_verified"
    assert receipt["stop"] == expected_stop
    assert receipt["grasp_verified"] is False
    assert "terminated" not in receipt and "truncated" not in receipt


def test_contact_grasp_stop_requires_measured_lift():
    from dataclasses import replace

    import numpy as np

    from robots.libero.v5_state import Entity

    obj = Entity("e1", "bowl", (0, 0, 1), (0, 0, .9), (.1, .1, 1.1))
    scene = SimpleNamespace(entities={"e1": obj})
    calls = []
    p = SimpleNamespace(env=SimpleNamespace(terminated=False, truncated=False),
                        _last_obs_gripper=.02, _last_obs_eef_pos=np.array([0., 0., 1.1]),
                        _vlm_chunk=lambda prompt: calls.append(prompt))
    executor = V5Executor(SimpleNamespace(primitives=p), scene)
    executor.move = lambda xyz, gripper: None
    executor._refresh = lambda names: scene.entities.update(e1=replace(obj, xyz=(0, 0, 1.05)))
    receipt = executor.vla_act("pick up the bowl", 4, "grasp_verified", obj)
    assert receipt["chunks"] == len(calls) == 2
    assert receipt["grasp_verified"] is True
    assert receipt["stop"] == receipt["stop_condition"] == "grasp_verified"


@pytest.mark.parametrize("measured_rise,verified", [(0, False), (.05, True)])
def test_one_trial_lift_returns_for_recovery_instead_of_climbing(measured_rise, verified):
    from dataclasses import replace

    import numpy as np

    from robots.libero.v5_state import Candidate, Entity

    obj = Entity("e1", "wine bottle", (0, 0, 1), (-.02, -.02, .95), (.02, .02, 1.1))
    scene = SimpleNamespace(entities={obj.id: obj})
    chunks, lifts = [], []
    p = SimpleNamespace(env=SimpleNamespace(terminated=False, truncated=False),
                        _last_obs_gripper=.02, _last_obs_eef_pos=np.array([0., 0., 1.1]),
                        _vlm_chunk=lambda prompt: chunks.append(prompt))
    executor = V5Executor(SimpleNamespace(primitives=p), scene, max_chunks=80,
                          grasp_lift_check_v2=True)

    def move(xyz, gripper):
        if gripper == 1:
            lifts.append(tuple(xyz))
        p._last_obs_eef_pos = np.asarray(xyz)

    executor.move = move
    executor._refresh = lambda names: scene.entities.update(
        e1=replace(obj, xyz=(0, 0, 1 + measured_rise)))
    receipt = executor.execute(Candidate("grasp", obj.id, mode="direct"))
    assert len(chunks) == receipt["chunks"] == 2
    assert len(lifts) == 1
    assert receipt["grasp_verified"] is verified
    assert receipt["stop"] == ("grasp_verified" if verified else "grasp_not_verified")
    assert executor.held == (obj.id if verified else None)
    assert not p.env.terminated


def test_grasp_receipt_records_loss_of_verification_after_contact_stop():
    import numpy as np

    from robots.libero.v5_state import Candidate, Entity

    obj = Entity("e1", "bowl", (0, 0, 1), (0, 0, .9), (.1, .1, 1.1))
    p = SimpleNamespace(env=SimpleNamespace(terminated=False, truncated=False),
                        _last_obs_gripper=.02, _last_obs_eef_pos=np.array([0., 0., 1.1]))
    executor = V5Executor(SimpleNamespace(primitives=p), SimpleNamespace(entities={"e1": obj}))
    executor.move = lambda xyz, gripper: None
    executor._refresh = lambda names: None
    executor.vla_act = lambda *args: {"executed": True, "chunks": 2,
                                     "stop_condition": "grasp_verified",
                                     "stop": "grasp_verified", "grasp_verified": True}
    receipt = executor.execute(Candidate("grasp", "e1", mode="direct"))
    assert receipt["executed"] is True
    assert receipt["grasp_verified"] is False
    assert receipt["stop"] == "verification_lost"
    assert executor.held is None


@pytest.mark.parametrize("enabled,visible,rise,opening,expected", [
    (False, True, .05, .02, False),
    (True, True, .05, .02, True),
    (True, True, .01, .02, False),
    (True, False, .05, .02, False),
    (True, True, .05, .078, False),
])
def test_occluded_trial_lift_uses_one_fresh_wrist_measurement(
    enabled, visible, rise, opening, expected
):
    from dataclasses import replace

    import numpy as np

    from robots.libero.v5_state import Candidate, Entity

    obj = Entity("e1", "wine bottle", (0, 0, 1), (-.02, -.02, .95), (.02, .02, 1.1))
    scene = SimpleNamespace(entities={obj.id: obj})
    chunks, primary, scans = [], [], []
    p = SimpleNamespace(env=SimpleNamespace(terminated=False, truncated=False),
                        _last_obs_gripper=.02, _last_obs_eef_pos=np.array([0., 0., 1.1]),
                        _vlm_chunk=lambda prompt: chunks.append(prompt))
    executor = V5Executor(SimpleNamespace(primitives=p), scene, max_chunks=80,
                          grasp_lift_check_v2=True, grasp_occlusion_scan_v1=enabled)
    executor.move = lambda xyz, gripper: setattr(p, "_last_obs_eef_pos", np.asarray(xyz))

    def refresh(names):
        primary.append(names)
        scene.entities[obj.id] = replace(obj, visible=False)

    def scan(names):
        scans.append(names)
        p._last_obs_gripper = opening
        scene.entities[obj.id] = replace(
            obj, xyz=(0, 0, 1 + rise), visible=visible, source_step=2)

    executor._refresh = refresh
    executor.scan_wrist = scan
    receipt = executor.execute(Candidate("grasp", obj.id, mode="direct"))
    assert receipt["grasp_verified"] is expected
    assert executor.held == (obj.id if expected else None)
    assert len(chunks) == 2 and len(scans) == int(enabled)
    assert len(primary) == (1 if expected else 2)
    # The extra view must not add fields to the rendered receipt.
    assert "grasp_occlusion_scan" not in receipt
    if enabled:
        assert executor.last_verification_measurements["grasp_occlusion_scan"]["verified"] is expected
    if expected:
        assert receipt["measured_z_rise_cm"] == 5
        assert np.allclose(executor.held_offset, [0, 0, .14])


def test_wrist_scan_preserves_gripper_and_only_measures_the_requested_category():
    scans, measured = [], []
    p = SimpleNamespace(env=SimpleNamespace(raw_obs=lambda: {"robot0_eef_quat": [0, 0, 0, 1]}),
                        rotate_wrist=lambda **kw: scans.append(kw) or {"steps_used": 2})
    scene = SimpleNamespace(refresh=lambda names, **kw: measured.append((names, kw)))
    executor = V5Executor(SimpleNamespace(primitives=p), scene)
    executor.capture = lambda: None
    executor.scan_wrist(["wine bottle"])
    assert scans == [{"target_yaw": .35, "gripper": 0}]
    assert measured == [(["wine bottle"], {"camera_view": "wrist"})]
    assert executor.wrist_scan_direction == -1


@pytest.mark.parametrize("opening,terminated,visible", [
    (.078, False, False), (.02, True, False), (.02, False, True),
])
def test_occlusion_scan_requires_missing_measurement_and_an_active_closed_gripper(
    opening, terminated, visible
):
    from dataclasses import replace

    from robots.libero.v5_state import Entity

    obj = Entity("e1", "bowl", (0, 0, 1), (-.03, -.03, .98), (.03, .03, 1.02))
    scene = SimpleNamespace(entities={obj.id: replace(obj, visible=visible)})
    p = SimpleNamespace(env=SimpleNamespace(terminated=terminated, truncated=False),
                        _last_obs_gripper=opening)
    executor = V5Executor(SimpleNamespace(primitives=p), scene, grasp_occlusion_scan_v1=True)
    executor.scan_wrist = lambda names: pytest.fail("scan without required physical preconditions")
    assert executor.verify_grasp_measurement(obj) is False
    assert executor.last_verification_measurements == {}


@pytest.mark.parametrize("native_flag", ["terminated", "truncated"])
def test_grasp_stops_when_approach_exhausts_the_native_episode(native_flag):
    import numpy as np

    from robots.libero.v5_state import Candidate, Entity

    obj = Entity("e1", "ketchup", (0, 0, 1), (-.02, -.02, .95), (.02, .02, 1.05))
    env = SimpleNamespace(terminated=False, truncated=False)
    p = SimpleNamespace(env=env, _last_obs_gripper=.078,
                        _last_obs_eef_pos=np.array([0., 0., 1.1]))
    executor = V5Executor(SimpleNamespace(primitives=p), SimpleNamespace(entities={"e1": obj}))
    captured = []
    executor.capture = lambda: captured.append(True)
    executor.move = lambda *args: setattr(env, native_flag, True)
    # Any wrist, contact, or further move would reproduce the native assertion.
    p.rotate_wrist = lambda **kwargs: pytest.fail("wrist step after native termination")
    executor.vla_act = lambda *args, **kwargs: pytest.fail("contact after native termination")
    receipt = executor.execute(Candidate("grasp", "e1", mode="yaw_90"))
    assert receipt["executed"] and receipt["grasp_verified"] is False
    assert receipt["stop"] == "execution_interrupted"
    assert "error" not in receipt and captured == [True]
    assert executor.held is None


@pytest.mark.parametrize("second_bowl", [False, True])
def test_direct_drawer_grasp_avoids_overhead_motion_only_for_unique_binding(second_bowl):
    import numpy as np

    from robots.libero.v5_state import Candidate, Entity

    obj = Entity("e1", "bowl", (0, 0, 1), (-.02, -.02, .98), (.02, .02, 1.02))
    drawer = Entity("e2", "drawer", (0, 0, 1), (-.1, -.1, .9), (.1, .1, 1.1))
    entities = {obj.id: obj, drawer.id: drawer}
    if second_bowl:
        entities["e3"] = Entity("e3", "bowl", (.05, 0, 1), (.03, -.02, .98), (.07, .02, 1.02))
    p = SimpleNamespace(env=SimpleNamespace(terminated=False, truncated=False),
                        _last_obs_gripper=.02, _last_obs_eef_pos=np.array([0., 0., 1.1]))
    executor = V5Executor(SimpleNamespace(primitives=p), SimpleNamespace(entities=entities))
    moves, prompts = [], []
    executor.move = lambda xyz, gripper: moves.append((xyz, gripper))
    executor._refresh = lambda names: None
    executor.vla_act = lambda prompt, *args, **kwargs: prompts.append(prompt) or {
        "executed": True, "stop": "grasp_verified", "grasp_verified": True}
    executor.execute(Candidate("grasp", "e1", mode="direct"))
    assert bool(moves) == second_bowl
    assert prompts == ["pick up the bowl directly below the gripper" if second_bowl
                       else "pick up the bowl from inside the drawer"]


def test_drawer_grasp_waits_until_clear_before_trial_lift():
    from dataclasses import replace

    import numpy as np

    from robots.libero.v5_state import Entity

    obj = Entity("e1", "bowl", (0, 0, 1), (-.02, -.02, .98), (.02, .02, 1.02))
    drawer = Entity("e2", "drawer", (0, 0, 1), (-.1, -.1, .9), (.1, .1, 1.1))
    p = SimpleNamespace(env=SimpleNamespace(terminated=False, truncated=False),
                        _last_obs_gripper=.02, _last_obs_eef_pos=np.array([0., 0., 1.]))
    chunks, lifts = [], []

    def contact(prompt):
        chunks.append(prompt)
        if len(chunks) == 3:
            p._last_obs_eef_pos[1] = .2

    p._vlm_chunk = contact
    scene = SimpleNamespace(entities={"e1": obj})
    executor = V5Executor(SimpleNamespace(primitives=p), scene)
    executor.move = lambda xyz, gripper: lifts.append(tuple(xyz))
    executor._refresh = lambda names: scene.entities.update(e1=replace(obj, xyz=(0, .2, 1.05)))
    receipt = executor.vla_act("pick up the bowl from inside the drawer", 4,
                              "grasp_verified", obj, lift_obstacle=drawer)
    assert receipt["grasp_verified"] is True and receipt["chunks"] == 3
    assert lifts == [(0, .2, 1.05)]


@pytest.mark.parametrize("opening,lost", [(.0797, True), (.02, False)])
def test_articulation_rechecks_held_verification_after_contact(opening, lost):
    from robots.libero.v5_state import Candidate, Entity

    cabinet = Entity("e1", "cabinet", (0, 0, 1), (0, 0, .9), (.1, .1, 1.1))
    milk = Entity("e2", "milk", (.2, 0, 1), (.1, 0, .9), (.3, .1, 1.1))
    p = SimpleNamespace(_last_obs_gripper=opening)
    executor = V5Executor(SimpleNamespace(primitives=p),
                          SimpleNamespace(entities={"e1": cabinet, "e2": milk}))
    executor.held = "e2"
    executor.held_offset = (0, 0, .02)
    executor.vla_act = lambda *args: {"executed": True, "chunks": 1,
                                     "stop": "chunk_budget", "stop_condition": "chunk_budget"}
    measured = []
    executor._refresh = lambda names: measured.extend(names)
    receipt = executor.execute(Candidate("articulate", "e1", mode="close"))
    assert receipt["verification"] == "unmeasured"
    if lost:
        assert executor.held is executor.held_offset is None
        assert receipt["held_verification_lost"] is True
        assert receipt["lost_held_object"] == "e2"
        assert receipt["gripper_opening"] == opening
        assert measured == ["cabinet", "drawer", "milk"]
    else:
        assert executor.held == "e2"
        assert executor.held_offset == (0, 0, .02)
        assert "held_verification_lost" not in receipt
        assert measured == ["cabinet", "drawer"]
@pytest.mark.parametrize("guide,small_part,visible", [(False, False, False), (True, False, True), (True, True, False)])
def test_wrist_text_miss_can_use_current_depth_point_but_rejects_a_knob(monkeypatch, guide, small_part, visible):
    import numpy as np
    from robots.libero.v5_runtime import MeasuredScene
    from robots.libero.v5_state import Entity
    from rpent.robots.components.sam3_client import Sam3Client

    obj = Entity("e1", "moka pot", (0, 0, .98), (-.04, -.03, .90), (.04, .03, 1.008))
    rows, cols = np.mgrid[:20, :20]
    world = np.stack(((cols - 9.5) * .003, (rows - 9.5) * .0025,
                      1 + rows * .0001), axis=-1)
    state = SimpleNamespace(latest_step=1, load_bytes=lambda _: b"new RGB",
                            load=lambda key: {"extrinsic_cam2world": np.eye(4)} if key.endswith(".json") else world)
    calls = []
    mask = np.ones((20, 20), dtype=bool)
    if small_part:
        mask[:] = False
        mask[6:14, 6:14] = True

    def call(method, kwargs, **unused):
        calls.append((method, kwargs))
        return {"found": True, "score": .9, "mask": mask} if method == "sam3.segment" else {"instances": []}

    monkeypatch.setattr(Sam3Client, "_decode_result", staticmethod(lambda item: SimpleNamespace(mask=item["mask"])))
    scene = MeasuredScene(SimpleNamespace(_state=state), SimpleNamespace(call=call), 1)
    scene.entities[obj.id] = obj
    scene.refresh([obj.name], camera_view="wrist", guided_entity=obj if guide else None)
    assert scene.entities[obj.id].visible is visible
    assert any(method == "sam3.segment" for method, _ in calls) is guide
    if visible:
        assert scene.entities[obj.id].source_step == 1
        assert scene.entities[obj.id].xyz[2] > obj.xyz[2]
        assert scene.perception_evidence[obj.id]["guidance"]["camera"] == "wrist"
