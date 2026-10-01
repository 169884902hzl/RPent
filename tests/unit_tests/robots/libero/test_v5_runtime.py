# Copyright 2026 Zhilun Hu.
# SPDX-License-Identifier: Apache-2.0
"""Composite skills must publish the native task result before evaluation."""

from types import SimpleNamespace

import pytest

from robots.libero import tools
from robots.libero.toolkit import LiberoToolkit
from robots.libero.v5_runtime import V5Executor, segmentation_prompt


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


def test_measured_destination_disappears_when_its_anchor_is_not_unique():
    from dataclasses import replace
    from robots.libero.v5_runtime import MeasuredScene
    from robots.libero.v5_state import Entity

    scene = MeasuredScene.__new__(MeasuredScene)
    scene.entities = {"e1": Entity("e1", "stove", (0, 0, 1), (-.08, -.08, .9), (.08, .08, 1.1)),
                      "e2": Entity("e2", "plate", (-.3, 0, .9), (-.35, -.05, .89), (-.25, .05, .91))}
    scene.view_axes = ((0, 1, 0), (1, 0, 0))
    scene.instruction = "push the plate to the front of the stove"
    scene._ids = ["e7"]
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
    assert receipt["verification"] == "unverified"


def test_place_clears_the_measured_rim_and_reuses_grasp_offset():
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
    executor = V5Executor(SimpleNamespace(primitives=p), scene)
    executor.held = "e1"
    executor.held_offset = np.array([0, 0, 0.01])
    waypoints = []

    def move(xyz, gripper):
        waypoints.append(np.asarray(xyz).copy())
        if len(waypoints) == 3:
            raise RuntimeError("stop after waypoint probe")

    executor.move = move
    try:
        executor._execute(Candidate("place", "e1", "e2", "in"), {}, None)
    except RuntimeError:
        pass
    np.testing.assert_allclose(waypoints[0][:2], p._last_obs_eef_pos[:2])
    assert waypoints[1][2] >= basket.upper[2] + 0.04 + 0.01 + 0.1
    np.testing.assert_allclose(waypoints[1][:2], [0.1, 0.25])


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
