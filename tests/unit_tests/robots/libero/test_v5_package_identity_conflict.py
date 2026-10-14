"""Current public masks must not reassign two package IDs to one instance."""
from types import SimpleNamespace

import numpy as np
import pytest

from robots.libero.v5_runtime import MeasuredScene
from rpent.robots.components.sam3_client import Sam3Client


@pytest.mark.parametrize("alternative_visible", [True, False])
def test_refreshed_package_id_does_not_jump_to_another_current_category(monkeypatch, alternative_visible):
    yy, xx = np.mgrid[:10, :20]
    world = np.stack((np.where(xx < 10, xx * .002, .2 + xx * .002),
                      yy * .002, .92 + yy * .0002), axis=-1)
    left = xx < 10
    state = SimpleNamespace(latest_step=0, load_bytes=lambda _: b"RGB",
        load=lambda name: {"extrinsic_cam2world": np.eye(4)} if name.endswith(".json") else world)

    def segment(_, kwargs, **unused):
        if kwargs["text_prompt"] == "small red box":
            return {"instances": [{"score": .64, "mask": left}]}
        if state.latest_step == 0:
            return {"instances": [{"score": .68, "mask": ~left}]}
        instances = [{"score": .9, "mask": left}]
        if alternative_visible:
            instances.append({"score": .6, "mask": ~left})
        return {"instances": instances}

    monkeypatch.setattr(Sam3Client, "_decode_result", staticmethod(
        lambda item: SimpleNamespace(mask=item["mask"])))
    scene = MeasuredScene(SimpleNamespace(_state=state), SimpleNamespace(call=segment), 1,
                          dual_view_fusion_v1=False, grasp_geometry_cleanup_v1=True)
    scene.instance_limits = {"butter": 1, "chocolate pudding": 1}
    scene.refresh(["butter", "chocolate pudding"])
    pudding = next(e for e in scene.entities.values() if e.name == "chocolate pudding")
    butter = next(e for e in scene.entities.values() if e.name == "butter")
    state.latest_step = 1
    scene.refresh(["butter", "chocolate pudding"])
    assert scene.entities[pudding.id].visible is alternative_visible
    assert scene.entities[pudding.id].xyz == pudding.xyz
    assert scene.entities[butter.id].visible is True
    assert scene.entities[butter.id].xyz == butter.xyz
    if alternative_visible:
        assert scene.entities[pudding.id].source_step == 1
