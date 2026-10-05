"""A new placement capture cannot turn stale measurements into current ones."""

from types import SimpleNamespace

import numpy as np

from robots.libero.v5_state import Entity
from rpent.session.base import EnvState
from scripts.v5_place527_evidence import public_placement_frame


def test_explicit_current_and_cached_clouds_keep_original_source_step(tmp_path):
    state = EnvState(tmp_path)
    with state.record_step(state={}):
        pass
    with state.record_step(state={}):
        for camera in ("agentview", "wrist"):
            state.save(f"{camera}_high.png", np.zeros((2, 2, 3), dtype=np.uint8))
            state.save(f"{camera}_world_high.npz", np.zeros((2, 2, 3)))
            state.save(f"{camera}_metadata.json", {"camera": camera})
    obj = Entity("e1", "frypan", (0, 0, .9), (-.1, -.1, .9), (.1, .1, .94), source_step=1)
    target = Entity("e2", "stove", (.1, .1, .9), (0, 0, .89), (.2, .2, .9), source_step=0)
    points = np.arange(18).reshape(6, 3)
    scene = SimpleNamespace(entities={e.id: e for e in (obj, target)},
        measurement_views={"e1": {"agentview": obj}, "e2": {"wrist": target}},
        measurement_clouds_by_view={
            "e1": {"agentview": {"xyz_world": points, "source_step": 1, "src": "perception", "object_id": "e1"}},
            "e2": {"wrist": {"xyz_world": points, "source_step": 0, "src": "perception", "object_id": "e2"}}},
        perception_evidence={})
    executor = SimpleNamespace(toolkit=SimpleNamespace(_state=state), scene=scene, held=None,
                               p=SimpleNamespace(_last_obs_gripper=.08, _last_obs_eef_pos=(0, 0, 1)))
    record = public_placement_frame(executor, {"object": obj, "target": target}, 0, "post_release")
    current = record["entities"]["object"]["per_view"]["agentview"]
    cached = record["entities"]["target"]["per_view"]["wrist"]
    assert current["current"] is True
    assert cached["current"] is False
    assert cached["cloud"]["source_step"] == 0
    assert record["entities"]["object"]["per_view"]["wrist"]["cloud"] is None
    assert record["new_robot_actions"] == 0
    assert record["src"] == "perception"
    assert "raw_metric_depth_not_saved" in record["cameras"]["wrist"]["depth_representation"]
    assert state.latest_step == 1
    saved = state.load("placement527_0000_public.json")
    assert "private_label" not in saved
    assert saved["entities"]["target"]["per_view"]["wrist"]["current"] is False
