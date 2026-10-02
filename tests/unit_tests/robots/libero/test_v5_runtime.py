# Copyright 2026 Zhilun Hu.
# SPDX-License-Identifier: Apache-2.0
"""Composite skills must publish the native task result before evaluation."""

from types import SimpleNamespace

import pytest

from robots.libero import tools
from robots.libero.toolkit import LiberoToolkit
from robots.libero.v5_runtime import V5Executor, segmentation_prompt, scene_vocabulary


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
def test_repeated_rejected_background_mask_keeps_identity_without_entering_state(monkeypatch, intermittent):
    import numpy as np
    from robots.libero.v5_runtime import MeasuredScene
    from rpent.robots.components.sam3_client import Sam3Client

    world = np.zeros((10, 10, 3))
    world[:] = (.1, .2, .5)
    state = SimpleNamespace(latest_step=0, load_bytes=lambda _: b"RGB",
        load=lambda name: {"extrinsic_cam2world": np.eye(4)} if name.endswith(".json") else world)
    monkeypatch.setattr(Sam3Client, "_decode_result", staticmethod(lambda item: SimpleNamespace(mask=np.ones((10,10), dtype=bool))))
    rpc = SimpleNamespace(call=lambda *args, **kwargs: {
        "instances": [] if intermittent and state.latest_step % 2 else [{"score": .9}]})
    scene = MeasuredScene(SimpleNamespace(_state=state), rpc, 1,
                          fixture_support_filter_v1=True, fixture_identity_cache_v1=True)
    scene.support_z = .9
    remaining = len(scene._ids)
    for step in range(140):
        state.latest_step = step
        scene.refresh(["cabinet"])
        assert not scene.entities
        assert len(scene._ids) == remaining - 1
    assert len(scene._rejected_fixture_entities) == 1
    assert len({row["measurement"]["id"] for row in scene.rejected_fixture_measurements}) == 1


@pytest.mark.parametrize("local", [False, True])
def test_shape_approach_can_keep_the_staged_gripper_reference_in_contact_prompt(local):
    import numpy as np
    from robots.libero.v5_state import Entity, Candidate

    obj = Entity("e1", "white yellow mug", (0,0,1), (-.03,-.03,.95), (.03,.03,1.05))
    p = SimpleNamespace(_last_obs_eef_pos=np.array([0.,0.,1.2]), _last_obs_gripper=.08,
                        env=SimpleNamespace(terminated=False, truncated=False))
    scene = SimpleNamespace(entities={"e1":obj}, measure_handle=lambda _:None, view_axes=((1,0,0),(0,1,0)))
    executor = V5Executor(SimpleNamespace(primitives=p), scene, grasp_approach_v1=True,
                          grasp_local_prompt_v1=local)
    calls = []
    executor.move = lambda *args: None
    executor._refresh = lambda *args: None
    def contact(prompt, *args, **kwargs):
        calls.append(prompt)
        return {"grasp_verified":False,"stop":"chunk_budget"}
    executor.vla_act = contact
    executor._execute(Candidate("grasp","e1",mode="direct"), {}, None)
    assert calls == ["pick up the white yellow mug" + (" directly below the gripper" if local else "")]


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
    scene.refresh(["moka pot"])
    measured = {e.name: e for e in scene.entities.values()}
    assert queried == ["black frying pan", "silver moka coffee pot"]
    assert measured["moka pot"].xyz == (.1, 0, 1.01)
    assert measured["frypan"].xyz == (-.1, 0, .93)


@pytest.mark.parametrize("ambiguous", [False, True])
def test_wrist_placement_rebinds_only_selected_object_with_unique_target_measurement(monkeypatch, ambiguous):
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
    scene.instance_limits = {"alphabet soup": 1}
    scene.refresh([selected.name], placement=(selected, target))
    assert scene.entities[other.id] == other
    assert scene.entities[selected.id].visible == (not ambiguous)
    if not ambiguous:
        assert scene.entities[selected.id].xyz == (0, 0, .12)


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
    assert receipt["verification"] == "unverified"


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
    assert receipt["verification"] == "unverified"
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
