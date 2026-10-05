from dataclasses import replace

from robots.libero.v5_action_effect import measured_action_effect
from robots.libero.v5_state import Entity


def snapshot(entity, opening=.08, held=None):
    return {"opening": opening, "held": held, "entities": {entity.id: entity}}


def test_occluded_cache_cannot_claim_measured_displacement():
    box = Entity("e1", "butter", (0, 0, 1), (-.02, -.02, .98), (.02, .02, 1.02), source_step=2)
    cached = replace(box, xyz=(0, 0, 1.1), visible=False, source_step=2, geometry="cached_perception")
    effect = measured_action_effect(snapshot(box), snapshot(cached), {"object": "e1"})
    assert effect["effect"] == "no_effect"
    assert effect["measurement"]["dxyz_cm"] == {}
    assert effect["measurement"]["unmeasured_entities"] == ["e1"]


def test_held_change_and_new_rgbd_motion_are_reported_separately():
    box = Entity("e1", "butter", (0, 0, 1), (-.02, -.02, .98), (.02, .02, 1.02), source_step=2)
    lifted = replace(box, xyz=(0, 0, 1.1), lower=(-.02, -.02, 1.08), upper=(.02, .02, 1.12), source_step=3)
    effect = measured_action_effect(snapshot(box), snapshot(lifted, .03, "e1"), {"object": "e1"})
    assert effect["effect"] == "measured_change"
    assert effect["measurement"] == {"gripper_m": [.08, .03], "held": [None, "e1"], "dxyz_cm": {"e1": [0, 0, 10]}}


def test_gripper_opening_change_does_not_fabricate_fixture_verification():
    drawer = Entity("e1", "cabinet top drawer", (0, 0, 1), (-.2, -.2, .95), (.2, .2, 1.05), part_of="e2", source_step=2)
    updated = replace(drawer, source_step=3)
    effect = measured_action_effect(snapshot(drawer, .03), snapshot(updated), {"object": "e1", "articulate_verified": None})
    assert effect["effect"] == "measured_change"
    assert effect["measurement"]["furniture"]["e1"]["verified"] is None


def test_duplicate_frame_does_not_prove_measurement_change():
    box = Entity("e1", "butter", (0, 0, 1), (-.02, -.02, .98), (.02, .02, 1.02), source_step=2)
    effect = measured_action_effect(snapshot(box), snapshot(box), {"object": "e1"})
    assert effect["effect"] == "no_effect"
    assert "e1" in effect["measurement"]["unmeasured_entities"]


def test_already_open_verified_fixture_is_still_no_effect():
    drawer = Entity("e1", "cabinet top drawer", (0, 0, 1), (-.2, -.2, .95), (.2, .2, 1.05), part_of="e2", source_step=2)
    effect = measured_action_effect(snapshot(drawer), snapshot(replace(drawer, source_step=3)),
                                    {"object": "e1", "articulate_verified": True})
    assert effect["effect"] == "no_effect"
    assert effect["measurement"]["furniture"]["e1"]["verified"] is True


def test_rgbd_coil_change_is_progress_without_a_fabricated_position_change():
    stove = Entity("e1", "stove", (0, 0, 1), (-.1, -.1, .95), (.1, .1, 1.05), source_step=2)
    endpoint = {"state": "on", "before": {"visible": True, "source_step": 2,
                "features": {"red_fraction": 0.}}, "after": {"visible": True, "source_step": 3,
                "features": {"red_fraction": .08}}}
    effect = measured_action_effect(snapshot(stove), snapshot(replace(stove, source_step=3)),
        {"object": "e1", "articulate_verified": True, "articulation_state": endpoint})
    assert effect["effect"] == "measured_change"
    assert effect["measurement"]["dxyz_cm"]["e1"] == [0., 0., 0.]
    assert effect["measurement"]["furniture"]["e1"]["state"] == "on"
    endpoint["after"]["features"]["red_fraction"] = 0.
    effect = measured_action_effect(snapshot(stove), snapshot(replace(stove, source_step=3)),
        {"object": "e1", "articulate_verified": True, "articulation_state": endpoint})
    assert effect["effect"] == "no_effect"


def test_complete_transfer_uses_measured_categories_and_no_held_stop(monkeypatch):
    import time
    import numpy as np
    from types import SimpleNamespace
    from robots.libero.v5_runtime import V5Executor
    from robots.libero.v5_state import Candidate

    box = Entity("e1", "butter", (0, 0, 1.1), (-.02, -.02, 1.08), (.02, .02, 1.12), source_step=2)
    target = Entity("e2", "plate", (0, 0, 1), (-.1, -.1, .98), (.1, .1, 1.02), source_step=2)
    executor = V5Executor.__new__(V5Executor)
    executor.scene = SimpleNamespace(entities={e.id: e for e in (box, target)},
        last_measurement_s={"butter": time.perf_counter() - 1}, refresh=lambda _: None)
    executor.p = SimpleNamespace(_last_obs_gripper=.08, _last_obs_eef_pos=np.array([.3, .3, 1.4]),
                                 env=SimpleNamespace(terminated=True, truncated=False))
    executor.target_cache_v1 = True
    executor.target_cache = {}
    executor.max_chunks = 160
    executor.held, executor.held_offset = "e1", np.zeros(3)
    executor.instruction = "private goal must not be copied into this macro"
    calls = []
    executor.vla_act = lambda prompt, budget, stop: calls.append((prompt, budget, stop)) or {"executed": True, "chunks": 22}
    executor._refresh = executor.capture = lambda *args: None
    monkeypatch.setattr("robots.libero.v5_verification.strict_place_verified_v6", lambda *args, **kwargs: True)
    receipt = {}
    executor.execute_subtask(Candidate("vla_subtask", "e1", "e2", "on"), receipt)
    assert calls == [("put the butter on the plate", 160, "chunk_budget")]
    assert executor.held is None
    assert receipt["place_verified"] is True
    assert "private goal" not in receipt["subtask_prompt"]
