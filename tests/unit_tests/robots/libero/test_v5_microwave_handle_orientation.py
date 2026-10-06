"""Thin handles can use only a unique door cloud from the same RGB-D capture."""

import hashlib
from dataclasses import replace
from types import SimpleNamespace

import numpy as np
import pytest

from robots.libero.v5_runtime import MeasuredScene
from robots.libero.v5_state import Entity
from rpent.robots.components.sam3_client import Sam3Client


def scene_with_door(tmp_path, monkeypatch):
    step = 3
    parent = Entity("e1", "microwave", (0., .04, 1.1), (-.16, -.02, .9),
                    (.16, .12, 1.25), source_step=step)
    door = Entity("e2", "microwave door", (0., 0., 1.1), (-.12, 0., 1.),
                  (.12, 0., 1.2), source_step=step, part_of=parent.id,
                  geometry="measured_door_surface")
    points = np.array([(x, 0., z) for x in np.linspace(-.12, .12, 30)
                       for z in np.linspace(1., 1.2, 30)])
    path = tmp_path / "current_door.npz"
    np.savez_compressed(path, points)
    rows, columns = np.mgrid[:10, :10]
    world = np.stack((.01 + columns * .001, np.full_like(rows, .03, dtype=float),
                      1.08 + rows * .001), axis=-1)
    extrinsic = np.eye(4)
    extrinsic[1, 3] = .5

    def save(name, value, *, step):
        destination = tmp_path / name
        np.savez_compressed(destination, value)
        return destination

    state = SimpleNamespace(latest_step=step, load_bytes=lambda _: b"image", save=save,
        load=lambda name: {"extrinsic_cam2world": extrinsic} if name.endswith(".json") else world,
        artifact_path=lambda name, step: tmp_path / name)
    rpc = SimpleNamespace(call=lambda *args, **kwargs: {"instances": [{"mask": np.ones((10, 10), bool)}]})
    monkeypatch.setattr(Sam3Client, "_decode_result", staticmethod(lambda item: SimpleNamespace(mask=item["mask"])))
    scene = MeasuredScene(SimpleNamespace(_state=state), rpc, 0, dual_view_fusion_v1=True)
    scene.entities = {parent.id: parent, door.id: door}
    scene.fixture_measurement_evidence[parent.id] = {"door_measurement": {
        "source": "perception", "source_step": step, "source_cameras": ["agentview", "wrist"],
        "accepted_by_camera": {"agentview": 1, "wrist": 1}, "path": str(path),
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}}
    scene.measure_fixture_endpoint = lambda *args: {"moving": None}
    return scene, parent, door, world.reshape(-1, 3), path


def test_current_unique_door_cloud_orients_thin_handle_in_both_views(tmp_path, monkeypatch):
    scene, parent, door, _, _ = scene_with_door(tmp_path, monkeypatch)
    result = scene.measure_fixture_handle_pose(parent, "close the microwave")
    assert result["pose"] is not None
    assert result["pose"]["approach_normal_xy"] == pytest.approx([0., 1.])
    assert result["source_cameras"] == ["agentview", "wrist"]
    for view in result["views"].values():
        assert view["current_door_orientation"]["door"] == door.id
        assert view["current_door_orientation"]["source_step"] == 3
        assert view["current_door_orientation"]["normal_gap_m"] == pytest.approx(.03)


@pytest.mark.parametrize("mutation", ["stale_parent", "stale_door", "cached_door", "wrong_parent",
    "two_doors", "stale_provenance", "missing_view", "ambiguous_view", "changed_cloud", "nonplanar"])
def test_missing_or_ambiguous_current_door_evidence_cannot_orient_handle(tmp_path, monkeypatch, mutation):
    scene, parent, door, _, path = scene_with_door(tmp_path, monkeypatch)
    evidence = scene.fixture_measurement_evidence[parent.id]["door_measurement"]
    if mutation == "stale_parent":
        scene.entities[parent.id] = replace(parent, source_step=2)
    elif mutation == "stale_door":
        scene.entities[door.id] = replace(door, source_step=2)
    elif mutation == "cached_door":
        scene.entities[door.id] = replace(door, visible=False)
    elif mutation == "wrong_parent":
        scene.entities[door.id] = replace(door, part_of="e99")
    elif mutation == "two_doors":
        scene.entities["e3"] = replace(door, id="e3")
    elif mutation == "stale_provenance":
        evidence["source_step"] = 2
    elif mutation == "missing_view":
        evidence["source_cameras"] = []
    elif mutation == "ambiguous_view":
        evidence["accepted_by_camera"]["wrist"] = 2
    elif mutation == "changed_cloud":
        path.write_bytes(b"different cloud")
    elif mutation == "nonplanar":
        np.savez_compressed(path, np.random.default_rng(2).uniform([-.1, -.1, 1.], [.1, .1, 1.2], (900, 3)))
        evidence["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    result = scene.measure_fixture_handle_pose(scene.entities[parent.id], "close the microwave")
    assert result["pose"] is None and result["reason"] == "current_fixture_handle_not_measured"
    assert all(view["pose"] is None for view in result["views"].values())


@pytest.mark.parametrize("shift", [[0., .08, 0.], [.2, 0., 0.], [0., 0., .2]])
def test_handle_must_be_adjacent_to_the_current_unique_door(tmp_path, monkeypatch, shift):
    scene, parent, _, handle, _ = scene_with_door(tmp_path, monkeypatch)
    face, evidence = scene._current_microwave_door_face(parent, "wrist", handle + shift)
    assert face is None and evidence["reason"] == "handle_not_adjacent_to_current_door"
