"""Fixture contact staging must use current measured handles and wrist RGB-D."""

from types import SimpleNamespace

import numpy as np
import pytest

from robots.libero.v5_fixture_parts import fuse_drawer_handle_clouds, measured_drawer_handle
from robots.libero.v5_runtime import MeasuredScene, V5Executor
from robots.libero.v5_state import Candidate, Entity
from scripts import probe_v5_skill501_original as probe


def drawer_scene():
    parent = Entity("e1", "cabinet", (0., 0., 1.05), (-.1, -.1, .9), (.1, .1, 1.2))
    part = Entity("e2", "cabinet middle drawer", (0., .1, 1.05), (-.09, .1, 1.),
                  (.09, .1, 1.1), part_of="e1")
    border = np.array([(x, .1, z) for x in np.r_[np.linspace(-.1, -.085, 10),
                                                               np.linspace(.085, .1, 10)]
                       for z in np.linspace(.92, 1.18, 25)])
    face = np.array([(x, .1, z) for x in np.linspace(-.07, .07, 30)
                     for z in np.linspace(1.01, 1.09, 20)])
    handle = np.array([(x, .125, z) for x in np.linspace(-.05, .05, 25)
                       for z in np.linspace(1.04, 1.05, 4)])
    return parent, part, border, face, handle


def measured_scene(tmp_path, *, primary_missing_drawer=False, wrist_missing=False):
    parent, part, border, face, handle = drawer_scene()
    loaded = []
    worlds = {"agentview": border if primary_missing_drawer else np.concatenate([border, face, handle]),
              "wrist": border if wrist_missing else np.concatenate([border, face, handle])}
    def load(name):
        loaded.append(name)
        if name.endswith(".json"):
            return {"extrinsic_cam2world": np.eye(4)}
        return worlds[name.split("_", 1)[0]]
    def save(name, value, *, step):
        path = tmp_path / name
        np.savez_compressed(path, value)
        return path
    state = SimpleNamespace(latest_step=3, load=load, load_bytes=lambda _: b"image",
                            save=save, artifact_path=lambda name, step: tmp_path / name)
    scene = MeasuredScene(SimpleNamespace(_state=state), SimpleNamespace(
        call=lambda *a, **k: pytest.fail("drawer geometry must not need a SAM fallback")), 0,
        fixture_endpoint_geometry_v3=True, dual_view_fusion_v1=True)
    scene.entities = {parent.id: parent, part.id: part}
    scene.fixture_front_axes[parent.id] = (0., 1., 0.)
    return scene, parent, part, loaded


def test_handle_fit_uses_selected_current_face_not_a_different_drawer():
    parent, part, border, face, handle = drawer_scene()
    pose, evidence, cloud = measured_drawer_handle(
        np.concatenate([border, face, handle]), parent, part, (0., 1., 0.))
    assert pose["xyz"] == pytest.approx([0., .125, 1.045])
    assert pose["approach_normal_xy"] == [0., 1.]
    assert evidence["moving_face"] and len(cloud) == len(handle)
    wrong = handle.copy()
    wrong[:, 2] += .10
    assert measured_drawer_handle(np.concatenate([border, face, wrong]),
                                  parent, part, (0., 1., 0.))[0] is None


@pytest.mark.parametrize("primary_missing", [False, True])
def test_drawer_endpoint_does_not_return_before_actual_wrist_fusion(tmp_path, primary_missing):
    scene, parent, _, loaded = measured_scene(tmp_path, primary_missing_drawer=primary_missing)
    result = scene.measure_fixture_endpoint(parent, "middle drawer of the cabinet")
    assert result["frame"] and result["moving"]
    assert "wrist_world_high.npz" in loaded
    assert result["fusion_version"] == "rgbd_dual_view/1"
    assert result["moving"]["source_cameras"] == (["wrist"] if primary_missing else ["agentview", "wrist"])
    assert result["point_counts_by_camera"]["wrist"]["moving"] >= 30


def test_fixture_handle_pose_records_actual_contributing_views(tmp_path):
    scene, parent, _, loaded = measured_scene(tmp_path)
    result = scene.measure_fixture_handle_pose(parent, "open the middle drawer of the cabinet")
    assert result["pose"]["xyz"] == pytest.approx([0., .125, 1.045])
    assert result["source_cameras"] == ["agentview", "wrist"]
    assert result["views"]["wrist"]["moving_face"]
    assert result["source_step"] == 3
    assert "wrist_world_high.npz" in loaded


def test_partial_wrist_handle_overlaps_full_view_despite_different_medians(tmp_path):
    scene, parent, _, _ = measured_scene(tmp_path)
    original = scene.toolkit._state.load
    def load(name):
        cloud = original(name)
        if name == "agentview_world_high.npz":
            handle = cloud[(cloud[:, 1] > .12) & (cloud[:, 0] > .02)]
            cloud = np.concatenate([cloud, np.repeat(handle, 2, axis=0)])
        if name == "wrist_world_high.npz":
            # Only the left end is visible at close range. Its much denser
            # pixels must not displace the full handle's measured centre.
            handle = cloud[(cloud[:, 1] > .12) & (cloud[:, 0] < -.02)]
            cloud = np.concatenate([cloud[cloud[:, 1] < .12], np.repeat(handle, 60, axis=0)])
        return cloud
    scene.toolkit._state.load = load
    result = scene.measure_fixture_handle_pose(parent, "open the middle drawer of the cabinet")
    assert result["centre_disagreement_m"] > .04
    assert result["pose"] is not None
    assert abs(result["pose"]["xyz"][0]) < .02
    assert result["source_cameras"] == ["agentview", "wrist"]
    assert result["surface_association"]["tangent_overlap_m"] >= .01


@pytest.mark.parametrize("shift", [(0., .03, 0.), (0., 0., .06), (.2, 0., 0.)])
def test_nonoverlapping_or_wrong_plane_handle_clouds_cannot_fuse(shift):
    *_, handle = drawer_scene()
    points, evidence = fuse_drawer_handle_clouds(handle, handle + shift, (0., 1., 0.))
    assert points is None
    assert evidence["reason"] == "handle_surfaces_do_not_overlap"


def test_conflicting_drawer_planes_remain_unmeasured_instead_of_selecting_one(tmp_path):
    scene, parent, _, _ = measured_scene(tmp_path)
    original = scene.toolkit._state.load
    def load(name):
        value = original(name)
        if name == "wrist_world_high.npz":
            value = value.copy()
            value[np.abs(value[:, 0]) < .08, 1] += .03
        return value
    scene.toolkit._state.load = load
    result = scene.measure_fixture_endpoint(parent, "middle drawer of the cabinet")
    assert result["reason"] == "drawer_views_disagree"
    assert result["moving"] is None
    assert result["view_disagreements"]["moving"]["normal_distance_m"] == pytest.approx(.03)


def stage_executor(*, wrist=True, present=True, residual=0.):
    parent, part, *_ = drawer_scene()
    evidence = {"pose": {"xyz": [0., .125, 1.045], "approach_normal_xy": [0., 1.]},
                "source_cameras": ["agentview", "wrist"] if wrist else ["agentview"]}
    if not present:
        evidence.update(pose=None, reason="selected_fixture_handle_not_measured")
    measurements, captures, motions = [], [], []
    def measure(obj, instruction):
        measurements.append((obj.id, instruction))
        return evidence.copy()
    scene = SimpleNamespace(entities={parent.id: parent, part.id: part},
                            measure_fixture_handle_pose=measure)
    p = SimpleNamespace(_last_obs_eef_pos=np.array([-.15, .2, 1.05]),
                        env=SimpleNamespace(terminated=False, truncated=False))
    def move(xyz, **kwargs):
        motions.append(xyz)
        p._last_obs_eef_pos = np.array(xyz)
        return {"steps_used": 10, "final_dist_m": residual}
    p.move_to = move
    executor = V5Executor(SimpleNamespace(primitives=p), scene,
                          instruction="open the middle drawer of the cabinet")
    executor.capture = lambda: captures.append(True)
    return executor, part, measurements, captures, motions


def test_contact_preapproach_lifts_before_translation_then_refines_at_wrist():
    executor, part, measured, captures, motions = stage_executor()
    receipt = {}
    assert executor.stage_fixture_handle(part, receipt)
    assert motions[0] == pytest.approx([-.15, .2, 1.28])
    assert motions[1] == pytest.approx([0., .275, 1.28])
    assert len(motions) == 2
    assert all(waypoint[2] >= 1.28 for waypoint in motions)
    assert len(measured) == 2 and captures == [True]
    assert receipt["fixture_handle_approach"]["ready_for_contact"]
    assert receipt["fixture_handle_approach"]["source_cameras"] == ["agentview", "wrist"]
    assert receipt["fixture_handle_approach"]["contact_start"] == "wrist_refined_safe_height"


@pytest.mark.parametrize("wrist,present,residual,reason", [
    (False, True, 0., "wrist_fixture_handle_not_measured"),
    (True, False, 0., "selected_fixture_handle_not_measured"),
    (True, True, .09, "fixture_approach_not_reached"),
])
def test_missing_measurement_or_unreachable_approach_returns_recoverable_receipt(
        wrist, present, residual, reason):
    executor, part, _, _, motions = stage_executor(wrist=wrist, present=present, residual=residual)
    receipt = {}
    assert not executor.stage_fixture_handle(part, receipt)
    assert receipt["verification"] == "unmeasured" and receipt["articulate_verified"] is None
    assert receipt["failure_reason"] == reason and receipt["recoverable"]
    if not present:
        assert not motions


def test_scoped_third_arm_runs_measured_approach_then_registered_contact_prompt():
    parent, *_ = drawer_scene()
    calls, prompts, staged = [], [], []
    executor = SimpleNamespace(scene=SimpleNamespace(
        entities={parent.id: parent}, dual_view_fusion_v1=True),
        stage_grasp=lambda *args, **kwargs: True,
        vla_act=lambda prompt, *args, **kwargs: prompts.append(prompt),
        _execute=lambda selected, receipt, card: calls.append(selected),
        p=SimpleNamespace(_vlm_chunk=lambda *args, **kwargs: {}))
    def stage(obj, receipt, **options):
        staged.append((obj.id, options))
        receipt["fixture_handle_approach"] = {"actual_cameras": ["agentview", "wrist"]}
        return True
    executor.stage_fixture_handle = stage
    condition = {"executor": "current", "contact_approach": "measured_fixture_handle", "max_chunks": 160}
    selected = Candidate("articulate", "e1", mode="open")
    registered = {"kind": "articulate", "subtask_prompt": "open the middle drawer of the cabinet"}
    evidence = {}
    with probe.contact_probe_controls(executor, None, registered, condition, selected, evidence):
        executor._execute(selected, {}, None)
        executor.vla_act("a different sentence", 160, "chunk_budget")
    assert staged == [("e1", {"standoff_m": .15})]
    assert calls == [selected] and prompts == [registered["subtask_prompt"]]
    assert evidence["contact_prompts"][0]["text"] == registered["subtask_prompt"]
    assert evidence["approach"]["actual_cameras"] == ["agentview", "wrist"]
