"""A public front query cannot manufacture an independently measured door."""

from types import SimpleNamespace
import base64
import io

import numpy as np
import pytest

from robots.libero.v5_microwave_front_hint import shell_front_panel_prompt
from robots.libero.v5_runtime import MeasuredScene
from robots.libero.v5_state import Entity


def public_scene():
    parent = Entity("e1", "microwave", (0., .29, 1.02), (-.16, .245, .93), (.17, .34, 1.11), source_step=0)
    world = np.zeros((100, 160, 3))
    rows, columns = np.mgrid[:100, :160]
    world[..., 0] = columns * .0021 - .16
    world[..., 1] = .248
    world[..., 2] = rows * .0018 + .93
    world[:, 88:108] = 0.
    anchor = {"lower": [.073, .245, .94], "upper": [.17, .251, 1.1], "parent": parent.id, "source_step": 0}
    return parent, world, anchor


def test_current_front_depth_returns_only_a_SAM_hint_outside_fixed_patch():
    parent, world, anchor = public_scene()
    point, evidence = shell_front_panel_prompt(world, parent, anchor, source_step=3)
    assert point is not None and point[1] < 88
    assert evidence["candidate_pixels"] >= 60
    assert evidence["door_label_admitted"] is evidence["stop_admitted"] is False
    assert evidence["current_fixed_reference"]["points"] >= 30


@pytest.mark.parametrize("missing", ["anchor", "wrong_parent", "future", "zero_depth", "fixed_patch", "back_wall"])
def test_front_hint_requires_current_depth_and_independent_fixed_reference(missing):
    parent, world, anchor = public_scene()
    if missing == "anchor":
        anchor = None
    elif missing == "wrong_parent":
        anchor["parent"] = "e2"
    elif missing == "future":
        anchor["source_step"] = 4
    elif missing == "zero_depth":
        world[:] = 0.
    elif missing == "fixed_patch":
        world[:, 108:] = 0.
    else:
        world[:, :88, 1] = .30  # A visible cavity/back wall is not the shell-front query.
    point, evidence = shell_front_panel_prompt(world, parent, anchor, source_step=3)
    assert point is None
    assert evidence["stop_admitted"] is evidence["door_label_admitted"] is False


def test_two_current_front_regions_stay_ambiguous():
    parent, world, anchor = public_scene()
    world[:, 38:48] = 0.
    point, evidence = shell_front_panel_prompt(world, parent, anchor, source_step=3)
    assert point is None
    assert len(evidence["panels"]) == 2


def test_private_labels_do_not_change_the_front_hint():
    parent, world, anchor = public_scene()
    before = shell_front_panel_prompt(world, parent, anchor, source_step=3)
    anchor.update(solved=True, private_joint_qpos=0., private_xyz=[99., 99., 99.])
    assert shell_front_panel_prompt(world, parent, anchor, source_step=3) == before


@pytest.mark.parametrize("found", [False, True])
def test_runtime_still_requires_SAM_mask_before_measuring_front_door(tmp_path, monkeypatch, found):
    from PIL import Image
    import robots.libero.v5_perception_geometry as geometry

    parent, world, anchor = public_scene()
    def save(name, value, *, step):
        path = tmp_path / name
        np.savez_compressed(path, array=value)
        return path
    image_bytes = io.BytesIO()
    Image.fromarray(np.zeros((*world.shape[:2], 3), np.uint8)).save(image_bytes, format="PNG")
    state = SimpleNamespace(latest_step=3, load_bytes=lambda name: image_bytes.getvalue(), save=save,
        artifact_path=lambda name, step: tmp_path / name,
        load=lambda name: {"extrinsic_cam2world": np.eye(4)} if name.endswith(".json") else world)
    calls = []
    def call(method, **kwargs):
        calls.append((method, kwargs["kwargs"]))
        if method != "sam3.segment":
            return {"instances": []}
        with Image.open(io.BytesIO(base64.b64decode(kwargs["kwargs"]["image_base64"]))) as image:
            shape = (image.height, image.width)
        mask_bytes = io.BytesIO()
        Image.fromarray(np.full(shape, 255, np.uint8)).save(mask_bytes, format="PNG")
        return {"found": found, "mask_png_base64": base64.b64encode(mask_bytes.getvalue()).decode(),
                "mask_shape": list(shape), "score": .9}
    monkeypatch.setattr(geometry, "appliance_foreground_mask", lambda world, mask, support: (mask, {}))
    scene = MeasuredScene(SimpleNamespace(_state=state), SimpleNamespace(call=call), 0,
        dual_view_fusion_v1=False, fixture_endpoint_geometry_v3=True,
        door_point_recall_v7=True, door_plane_consensus_v1=True, microwave_shell_front_hint_v1=True)
    scene._microwave_frame_anchors[(parent.id, "agentview")] = anchor
    observed = scene.measure_fixture_endpoint(parent, "microwave door", temporal_capture=True)
    assert len([row for row in calls if row[0] == "sam3.segment"]) == 1
    assert observed["measurement_counts"]["moving"]["point_guidance"]["trigger_only"] is True
    assert (observed["moving"] is not None) is found
    if found:
        assert observed["moving"]["source"] == "perception"
        assert observed["moving"]["source_step"] == 3
        assert observed["frame_moving_mask_overlap"] == 0.


def test_front_hint_flag_defaults_off():
    state = SimpleNamespace(load=lambda name: {"extrinsic_cam2world": np.eye(4)})
    assert MeasuredScene(SimpleNamespace(_state=state), SimpleNamespace(), 0).microwave_shell_front_hint_v1 is False
