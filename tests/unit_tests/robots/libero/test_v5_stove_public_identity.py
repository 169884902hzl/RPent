"""Current measured stove identity must not depend on thin-box IoU or tails."""

from types import SimpleNamespace

import numpy as np
import pytest

from robots.libero.v5_public_fixture_identity import canonical_stove_measurements
from robots.libero.v5_runtime import MeasuredScene
from robots.libero.v5_state import Entity


def entity(identity, points, *, name="stove", step=4):
    low, high = np.quantile(points, [.02, .98], axis=0)
    return Entity(identity, name, tuple(np.median(points, axis=0)),
                  tuple(low), tuple(high), source_step=step)


def samples():
    # A smaller SAM instance samples almost the same XY surface with a
    # different thin Z distribution. Three-dimensional box IoU is unreliable.
    x, y = np.meshgrid(np.linspace(-.12, .06, 35), np.linspace(.10, .29, 35))
    points = np.column_stack([x.ravel(), y.ravel(), np.full(x.size, .925)])
    taller = points.copy()
    taller[::4, 2] = .93
    larger = np.concatenate([points, taller[::4]])
    return larger, points


def scene_with_clouds():
    large, small = samples()
    scene = MeasuredScene.__new__(MeasuredScene)
    scene.toolkit = SimpleNamespace(_state=SimpleNamespace(latest_step=4))
    scene.entities = {"original": entity("original", large), "nested": entity("nested", small)}
    scene.measurement_clouds_by_view = {
        eid: {"agentview": {"xyz_world": points, "src": "perception", "source_step": 4}}
        for eid, points in [("original", large), ("nested", small)]
    }
    scene.stove_identity_history = []
    return scene


def test_runtime_uses_current_in_memory_clouds_without_persisted_mask_files():
    scene = scene_with_clouds()
    before = dict(scene.entities)
    scene.canonicalize_stove_measurements({"original": None, "nested": None}, "agentview")
    assert scene.entities == {"original": before["original"]}
    assert scene.entities["original"] is before["original"]
    event = scene.stove_identity_history[-1]
    assert event["removed_ids"] == ["nested"]
    assert event["aliases"][0]["smaller_public_cloud_coverage"] == 1.
    assert event["aliases"][0]["smaller_actual_mask_coverage"] is None
    guard = scene.stove_operating_area((-.2, 0., 1.1))
    assert guard["original"]["disposition"] == "eligible"


@pytest.mark.parametrize("difference", ["not_in_this_capture", "stale", "different_view", "different_category"])
def test_stale_or_nonmatching_evidence_cannot_merge_entities(difference):
    scene = scene_with_clouds()
    ids = {"original", "nested"}
    if difference == "not_in_this_capture":
        ids.remove("nested")
    elif difference == "stale":
        scene.measurement_clouds_by_view["nested"]["agentview"]["source_step"] = 3
    elif difference == "different_view":
        scene.measurement_clouds_by_view["nested"] = {"wrist": scene.measurement_clouds_by_view["nested"]["agentview"]}
    elif difference == "different_category":
        scene.entities["nested"] = entity("nested", samples()[1], name="drawer")
    result, event = canonical_stove_measurements(scene.entities, 4, ids,
                                                scene.measurement_clouds_by_view, {}, "agentview")
    assert set(result) == {"original", "nested"}
    assert event["aliases"] == []


def test_two_separate_near_stoves_keep_ambiguity():
    scene = scene_with_clouds()
    moved = samples()[1].copy()
    moved[:, 0] += .35
    scene.entities["nested"] = entity("nested", moved)
    scene.measurement_clouds_by_view["nested"]["agentview"]["xyz_world"] = moved
    scene.canonicalize_stove_measurements({"original": None, "nested": None}, "agentview")
    assert len(scene.entities) == 2
    assert all(item["disposition"] == "eligible" for item in scene.stove_operating_area((-.2, 0., 1.1)).values())


def test_wide_bbox_tail_does_not_override_far_point_supported_measurement():
    scene = scene_with_clouds()
    points = np.column_stack([np.full(100, -1.46), np.linspace(-.38, .38, 100), np.full(100, .91)])
    points[:5, 0] = -.64  # The 98th-percentile bound reaches into the old area.
    scene.entities = {"far": entity("far", points)}
    scene.measurement_clouds_by_view = {"far": {"agentview": {"xyz_world": points, "src": "perception", "source_step": 4}}}
    scene.canonicalize_stove_measurements({"far": None}, "agentview")
    eef = (-.2, 0., 1.1)
    assert scene.entities["far"].upper[0] - eef[0] > -.5
    guard = scene.stove_operating_area(eef)["far"]
    assert guard["median_xy_distance_m"] > 1.
    assert guard["point_support_fraction"] == .05
    assert guard["disposition"] == "rejected"


def test_missing_raw_public_points_stays_unmeasured_without_bbox_fallback():
    scene = scene_with_clouds()
    scene.measurement_clouds_by_view = {}
    scene.canonicalize_stove_measurements({"original": None, "nested": None}, "agentview")
    assert all(value["disposition"] == "unmeasured" for value in scene.stove_operating_area((-.2, 0., 1.1)).values())


@pytest.mark.parametrize("enabled", [False, True])
def test_actual_refresh_wires_identity_only_when_opted_in(monkeypatch, enabled):
    from rpent.robots.components.sam3_client import Sam3Client

    world = np.ones((12, 12, 3))
    state = SimpleNamespace(latest_step=4, load_bytes=lambda name: name.encode(),
                            load=lambda name: {"extrinsic_cam2world": np.eye(4)} if name.endswith(".json") else world)
    monkeypatch.setattr(Sam3Client, "_decode_result", staticmethod(lambda value: SimpleNamespace(mask=value["mask"])))
    scene = MeasuredScene(SimpleNamespace(_state=state), SimpleNamespace(call=lambda *a, **kw: {"instances": []}), 0,
                          dual_view_fusion_v1=False, stove_public_identity_v1=enabled)
    scene.refresh(["stove"])
    assert len(scene.stove_identity_history) == int(enabled)
