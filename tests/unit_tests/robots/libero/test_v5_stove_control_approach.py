"""The third stove method stages at a measured control, never burner truth."""

from types import SimpleNamespace

import numpy as np
import pytest

from robots.libero.v5_fixture_parts import measured_stove_control_pose
from robots.libero.v5_runtime import MeasuredScene, V5Executor
from robots.libero.v5_state import Entity
from rpent.robots.components.sam3_client import Sam3Client


def stove_and_control():
    parent = Entity("e1", "stove", (0., 0., 1.), (-.08, -.08, .98), (.08, .08, 1.02))
    cloud = np.array([(x, y, 1.03) for x in np.linspace(.055, .095, 20)
                      for y in np.linspace(.04, .06, 10)])
    return parent, cloud


def test_horizontal_control_uses_a_three_dimensional_approach_normal():
    parent, cloud = stove_and_control()
    pose, evidence = measured_stove_control_pose(cloud, parent, (.3, .3, 1.5))
    assert pose["xyz"] == pytest.approx([.075, .05, 1.03])
    assert pose["approach_normal_xyz"] == pytest.approx([0., 0., 1.])
    assert pose["approach_normal_xy"] == pytest.approx([0., 0.])
    assert evidence["endpoint_state"] == "unmeasured"
    assert evidence["source"] == "perception"


def test_control_pose_tracks_observed_pose_and_normal_under_rotation():
    parent, cloud = stove_and_control()
    rotation = np.array([[0., 0., 1.], [0., 1., 0.], [-1., 0., 0.]])
    centre = np.array([.075, .05, 1.03])
    moved = (cloud - centre) @ rotation.T + centre
    pose, _ = measured_stove_control_pose(moved, parent, (.3, .3, 1.5))
    assert pose["approach_normal_xyz"] == pytest.approx([1., 0., 0.])
    assert pose["xyz"] == pytest.approx(centre)


@pytest.mark.parametrize("invalid,reason", [
    ("remote", "control_not_adjacent_to_measured_stove"),
    ("burner", "control_mask_includes_large_fixture_surface"),
    ("line", "control_surface_orientation_not_measured"),
    ("missing", "current_stove_control_depth_missing"),
])
def test_burner_remote_or_unsupported_cloud_cannot_fabricate_a_knob(invalid, reason):
    parent, cloud = stove_and_control()
    if invalid == "remote":
        cloud += [.3, 0., 0.]
    elif invalid == "burner":
        cloud[:, 0] = np.linspace(-.09, .09, len(cloud))
    elif invalid == "line":
        cloud[:, 1] = .05
    else:
        cloud = cloud[:10]
    pose, evidence = measured_stove_control_pose(cloud, parent, (.3, .3, 1.5))
    assert pose is None and evidence["reason"] == reason


def scene_with_stove_cloud(tmp_path, monkeypatch, *, ambiguous=False):
    parent, cloud = stove_and_control()
    clouds = [cloud, cloud + [-.04, -.04, 0.]] if ambiguous else [cloud]
    world = np.concatenate(clouds)[None]
    queries = []
    def call(name, *, kwargs, timeout_s):
        queries.append(kwargs["text_prompt"])
        masks = []
        for index in range(len(clouds)):
            mask = np.zeros(world.shape[:2], dtype=bool)
            mask[:, index * len(cloud):(index + 1) * len(cloud)] = True
            masks.append({"mask": mask})
        return {"instances": masks}
    camera = np.eye(4)
    camera[:3, 3] = [.3, .3, 1.5]
    def save(name, value, *, step):
        np.savez_compressed(tmp_path / name, value)
        return tmp_path / name
    state = SimpleNamespace(latest_step=9, load_bytes=lambda _: b"frame",
        load=lambda name: {"extrinsic_cam2world": camera} if name.endswith(".json") else world,
        save=save, artifact_path=lambda name, step: tmp_path / name)
    monkeypatch.setattr(Sam3Client, "_decode_result", staticmethod(lambda item: SimpleNamespace(mask=item["mask"])))
    scene = MeasuredScene(SimpleNamespace(_state=state), SimpleNamespace(call=call), 0, dual_view_fusion_v1=True)
    scene.entities[parent.id] = parent
    return scene, parent, queries


@pytest.mark.parametrize("mode", ["turn_on", "turn_off"])
def test_on_and_off_have_a_unique_current_two_view_control_interface(tmp_path, monkeypatch, mode):
    scene, parent, queries = scene_with_stove_cloud(tmp_path, monkeypatch)
    result = scene.measure_fixture_handle_pose(parent, mode.replace("_", " ") + " the stove")
    assert queries == ["stove knob", "stove switch handle"] * 2
    assert result["pose"]["approach_normal_xyz"] == pytest.approx([0., 0., 1.])
    assert result["source_cameras"] == ["agentview", "wrist"]
    assert result["source_step"] == 9
    assert all(view["accepted_instances"] == 1 for view in result["views"].values())
    assert all(view["cloud"]["points"] == 200 for view in result["views"].values())
    assert result["views"]["wrist"]["queries"][1]["instances"][0]["reason"] == "same_measured_control_mask"


def test_two_distinct_current_controls_remain_ambiguous(tmp_path, monkeypatch):
    scene, parent, _ = scene_with_stove_cloud(tmp_path, monkeypatch, ambiguous=True)
    result = scene.measure_fixture_handle_pose(parent, "turn on the stove")
    assert result["pose"] is None and result["source_cameras"] == []
    assert all(view["accepted_instances"] == 2 for view in result["views"].values())


def test_stove_staging_uses_full_normal_to_approach_above_the_control():
    parent, _ = stove_and_control()
    pose = {"xyz": [.075, .05, 1.03], "approach_normal_xyz": [0., 0., 1.],
            "approach_normal_xy": [0., 0.]}
    scene = SimpleNamespace(entities={parent.id: parent},
        measure_fixture_handle_pose=lambda *args: {"pose": pose, "source_cameras": ["agentview", "wrist"]})
    primitive = SimpleNamespace(_last_obs_eef_pos=np.array([-.1, 0., 1.]),
                                env=SimpleNamespace(terminated=False, truncated=False))
    targets = []
    def move(xyz, **kwargs):
        targets.append(xyz)
        primitive._last_obs_eef_pos = np.array(xyz)
        return {"steps_used": 10, "final_dist_m": 0.}
    primitive.move_to = move
    executor = V5Executor(SimpleNamespace(primitives=primitive), scene, instruction="turn on the stove")
    executor.capture = lambda: None
    receipt = {}
    assert executor.stage_fixture_handle(parent, receipt)
    assert targets[-1] == pytest.approx([.075, .05, 1.21])
    assert receipt["fixture_handle_approach"]["target_xyz"] == pytest.approx(targets[-1])
