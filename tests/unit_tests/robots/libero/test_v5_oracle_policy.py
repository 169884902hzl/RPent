# Copyright 2026 Zhilun Hu.
# SPDX-License-Identifier: Apache-2.0
"""Private oracle progress must bind to public measured instances."""

import random

from robots.libero.v5_oracle_policy import OriginalOraclePolicy, _kind
from robots.libero.v5_state import Candidate, Entity, candidates, serialize


def measured(eid, name, x, y, width):
    return Entity(
        eid,
        name,
        (x, y, 0.93),
        (x - width / 2, y - width / 2, 0.90),
        (x + width / 2, y + width / 2, 0.95),
    )


def test_named_drawer_uses_existing_cabinet_articulation_without_inventing_a_drawer_pose():
    from types import SimpleNamespace
    cabinet = measured("e4", "cabinet", 0, 0, .2)
    rpc = SimpleNamespace(call=lambda *a, **k: {"done": False, "goals": [["open", "wooden_cabinet_1_middle_region"]],
                                              "satisfied": [False]})
    policy = OriginalOraclePolicy(rpc)
    choices = [Candidate("articulate", "e4", mode="open"), Candidate("ask_help")]
    chosen = policy.choose([cabinet], choices, None, [], "open the middle drawer of the cabinet", ((1, 0, 0), (0, 1, 0)))
    assert chosen == choices[0]


def test_category_digits_survive_removal_of_the_private_instance_suffix():
    assert _kind("chefmate_8_frypan_1") == "frypan"
    assert _kind("chefmate_8_frypan_9") == "frypan"
    assert _kind("white_cabinet_1_bottom_region") == "cabinet"


def test_storage_precedes_closure_and_closed_storage_is_opened_first():
    class Rpc:
        open = True

        def call(self, method, **kwargs):
            return {"done": False, "goals": [["close", "white_cabinet_1_bottom_region"],
                    ["in", "akita_black_bowl_1", "white_cabinet_1_bottom_region"]],
                    "satisfied": [not self.open, False],
                    "storage_open": {"white_cabinet_1_bottom_region": self.open}}

    entities = [measured("e1", "bowl", 0, 0, .1), measured("e2", "drawer", .2, 0, .2)]
    instruction = "put the black bowl in the bottom drawer of the cabinet and close it"
    choices = candidates(entities, instruction, (0, 0, 1), None, [], random.Random(0))
    rpc = Rpc()
    policy = OriginalOraclePolicy(rpc)
    assert policy.choose(entities, choices, None, [], instruction, ()).text() == "grasp(e1,direct)"
    rpc.open = False
    assert policy.choose(entities, choices, None, [], instruction, ()).text() == "articulate(e2,open)"


def test_natural_relation_anchor_retains_ordinal_qualifier():
    entities = [measured("e7", "plate", -.2, 0, .1), measured("e8", "plate", .2, 0, .1)]
    policy = OriginalOraclePolicy(None)
    axes = ((1, 0, 0), (0, -1, 0))
    assert policy.bind("the left plate", entities, "", axes).id == "e7"
    assert policy.bind("the right plate", entities, "", axes).id == "e8"


def test_second_mug_uses_the_second_destination_clause():
    class Rpc:
        def call(self, method, **kwargs):
            return {"done": False, "goals": [["on", "porcelain_mug_1", "plate_1"],
                                              ["on", "white_yellow_mug_1", "plate_2"]],
                    "satisfied": [True, False]}
    entities = [measured("e7", "plate", -.2, 0, .1), measured("e8", "plate", .2, 0, .1),
                measured("e3", "white yellow mug", 0, 0, .08)]
    instruction = "put the white mug on the left plate and put the yellow and white mug on the right plate"
    choices = candidates(entities, instruction, (0, 0, 1), "e3", [], random.Random(0))
    policy = OriginalOraclePolicy(Rpc())
    selected = policy.choose(entities, choices, "e3", [], instruction, ((1, 0, 0), (0, -1, 0)))
    assert selected.text() == "place(e3,e8,on)"


def test_between_binding_uses_measurements_instead_of_internal_instance_suffix():
    entities = [
        measured("e99", "bowl", -0.084, 0.207, 0.10),
        measured("e98", "bowl", -0.210, 0.326, 0.10),
        measured("e114", "bowl", -0.211, 0.189, 0.08),
        measured("e6", "plate", 0.051, 0.207, 0.12),
    ]
    policy = OriginalOraclePolicy(None)
    phrase = "pick up the black bowl between the plate and the ramekin"
    for symbol in ("akita_black_bowl_1", "akita_black_bowl_9"):
        assert policy.bind(symbol, entities, phrase, ((0, 1, 0), (1, 0, 0))).id == "e99"
    assert (
        policy.bind(
            "akita_black_bowl_1", entities, "pick a bowl", ((0, 1, 0), (1, 0, 0))
        )
        is None
    )


def test_unresolved_reference_selects_help_and_private_goals_never_enter_request():
    class Rpc:
        def call(self, method, **kwargs):
            assert method == "oracle.status"
            return {
                "done": False,
                "goals": [["on", "akita_black_bowl_7", "plate_1"]],
                "satisfied": [False],
            }

    entities = [
        measured("e10", "bowl", 0, 0, 0.10),
        measured("e20", "bowl", 0.2, 0, 0.10),
        measured("e30", "plate", 0.4, 0, 0.12),
    ]
    choices = candidates(
        entities, "put a bowl on plate", (0, 0, 1), None, [], random.Random(0)
    )
    policy = OriginalOraclePolicy(Rpc())
    assert (
        policy.choose(
            entities, choices, None, [], "put a bowl on plate", ((0, 1, 0), (1, 0, 0))
        ).tool
        == "ask_help"
    )
    context = serialize("put a bowl on plate", entities, 0.08, None, [])
    assert "akita_black_bowl_7" not in context
    assert "goal" not in context


def test_finish_requires_independent_done_predicate():
    class Rpc:
        def call(self, method, **kwargs):
            return {"done": True}

    choices = candidates([], "put bowl on plate", (0, 0, 1), None, [], random.Random(1))
    assert (
        OriginalOraclePolicy(Rpc())
        .choose([], choices, None, [], "put bowl on plate", ((0, 1, 0), (1, 0, 0)))
        .tool
        == "finish"
    )


def test_native_success_is_latched_when_instantaneous_goal_changes():
    class Rpc:
        def call(self, method, **kwargs):
            return {
                "done": False,
                "goals": [["on", "bowl_1", "plate_1"]],
                "satisfied": [False],
            }

    choices = candidates([], "put bowl on plate", (0, 0, 1), None, [], random.Random(1))
    policy = OriginalOraclePolicy(Rpc())
    for native_success in (True, False):
        assert (
            policy.choose(
                [],
                choices,
                None,
                [],
                "put bowl on plate",
                ((0, 1, 0), (1, 0, 0)),
                native_success=native_success,
            ).tool
            == "finish"
        )


def test_storage_region_binds_to_the_measured_parent_category():
    plate = measured("e7", "plate", 0, 0, 0.1)
    assert (
        OriginalOraclePolicy(None).bind(
            "plate_1_region", [plate], "", ((0, 1, 0), (1, 0, 0))
        )
        == plate
    )


def test_wine_rack_region_binds_to_the_public_rack_category():
    rack = measured("e7", "rack", 0, 0, 0.2)
    policy = OriginalOraclePolicy(None)
    assert policy.bind("wine_rack_1_top_region", [rack], "", ()) == rack
    assert policy.bind("wine_rack_9_top_region", [rack], "", ()) == rack
    assert policy.bind("wine_rack_1_top_region", [], "", ()) is None


def test_next_to_reference_selects_the_unique_nearest_measured_bowl():
    entities = [
        measured("e35", "bowl", 0.103, -0.063, 0.10),
        measured("e73", "bowl", -0.187, 0.319, 0.10),
        measured("e109", "bowl", -0.199, 0.199, 0.08),
    ]
    policy = OriginalOraclePolicy(None)
    assert (
        policy.bind(
            "akita_black_bowl_9",
            entities,
            "pick up the black bowl next to the ramekin",
            ((0, 1, 0), (1, 0, 0)),
        ).id
        == "e73"
    )
    entities[0] = measured("e35", "bowl", -0.319, 0.199, 0.10)
    assert policy.bind("bowl", entities, "bowl next to the ramekin", ()) is None


def test_on_reference_requires_one_measured_support_and_not_a_private_suffix():
    bowl = Entity("e1", "bowl", (0, 0, 1.16), (-0.04, -0.04, 1.135), (0.04, 0.04, 1.18))
    table_bowl = measured("e2", "bowl", -0.3, 0, 0.1)
    cabinet = Entity("e3", "cabinet", (0, 0, 1.1), (-0.1, -0.1, 0.9), (0.1, 0.1, 1.127))
    policy = OriginalOraclePolicy(None)
    for symbol in ("akita_black_bowl_1", "akita_black_bowl_9"):
        assert (
            policy.bind(
                symbol, [bowl, table_bowl, cabinet], "bowl on the wooden cabinet", ()
            ).id
            == "e1"
        )
    assert (
        policy.bind("bowl", [bowl, table_bowl], "bowl on the wooden cabinet", ())
        is None
    )


def test_top_drawer_uses_measured_height_and_table_centre_needs_a_measurement():
    bottom = measured("e1", "drawer", 0, 0, 0.2)
    top = Entity("e2", "drawer", (0, 0, 1.1), (-0.1, -0.1, 1.05), (0.1, 0.1, 1.15))
    policy = OriginalOraclePolicy(None)
    assert (
        policy.bind("top drawer of the wooden cabinet", [bottom, top], "", ()).id
        == "e2"
    )
    bowls = [measured("e3", "bowl", 0, 0, 0.1), measured("e4", "bowl", 0.3, 0, 0.1)]
    assert policy.bind("bowl", bowls, "bowl from table center", ()) is None
    table = Entity("e5", "table", (0, 0, 0.89), (-0.4, -0.4, 0.88), (0.4, 0.4, 0.9))
    assert policy.bind("bowl", [*bowls, table], "bowl from table center", ()).id == "e3"


def test_derived_plate_region_does_not_make_the_measured_plate_ambiguous():
    plate = measured("e7", "plate", 0, 0, .1)
    region = measured("e8", "area right of plate", 0, .2, .1)
    policy = OriginalOraclePolicy(None)
    axes = ((0, 1, 0), (1, 0, 0))
    assert policy.bind("plate_1", [plate, region], "put the white mug on the plate", axes,
                       source_reference=False) == plate
    assert policy.bind("table_plate_right_region", [plate, region],
                       "put chocolate to the right of the plate", axes,
                       source_reference=False) == region
