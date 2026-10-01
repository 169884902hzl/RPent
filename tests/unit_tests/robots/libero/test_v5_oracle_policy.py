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


def test_cached_binding_recovers_a_unique_public_measurement_without_using_a_hidden_pose():
    from dataclasses import replace

    policy = OriginalOraclePolicy(None)
    policy._bindings["ketchup_1"] = "e6"
    axes = ((1, 0, 0), (0, 1, 0))
    hidden = replace(measured("e6", "ketchup", 0, 0, .1), visible=False)
    observed = measured("e63", "ketchup", .3, 0, .1)
    assert policy.bind("ketchup_1", [hidden, observed], "pick up the ketchup", axes).id == "e63"
    assert policy.bind("ketchup_1", [hidden], "pick up the ketchup", axes) is None
    ambiguous = measured("e64", "ketchup", -.3, 0, .1)
    assert policy.bind("ketchup_1", [hidden, observed, ambiguous], "pick up the ketchup", axes) is None


def test_cached_binding_cannot_follow_a_mask_recategorized_as_another_object():
    policy = OriginalOraclePolicy(None)
    policy._bindings["ketchup_1"] = "e6"
    sauce = measured("e6", "barbecue sauce", 0, 0, .1)
    ketchup = measured("e63", "ketchup", .3, 0, .1)
    assert policy.bind("ketchup_1", [sauce, ketchup], "pick up the ketchup", ()).id == "e63"
    assert policy.bind("ketchup_1", [sauce], "pick up the ketchup", ()) is None


def test_a_visible_cached_reference_stays_bound_after_the_object_moves():
    policy = OriginalOraclePolicy(None)
    policy._bindings["akita_black_bowl_1"] = "e6"
    moved = measured("e6", "bowl", .3, 0, .1)
    other = measured("e63", "bowl", -.3, 0, .1)
    assert policy.bind("akita_black_bowl_1", [moved, other], "pick up the left bowl", ((1, 0, 0), (0, 1, 0))).id == "e6"


def test_pick_then_place_pronoun_keeps_the_destination_clause():
    from robots.libero.v5_oracle_policy import goal_clause

    text = "pick up the book and place it in the back compartment of the caddy"
    assert goal_clause(text, "black_book_1") == text
    text = "pick up the book then place it in the back compartment of the caddy"
    assert goal_clause(text, "black_book_1") == text


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


def test_table_center_reference_excludes_bowl_on_a_measured_plate():
    from dataclasses import replace

    entities = [
        Entity("e99", "bowl", (-.021, .3149, .9297),
               (-.05297, .2583, .90674), (.04883, .35669, .95068)),
        Entity("e98", "bowl", (-.0958, .015, .9299),
               (-.12561, -.03464, .90674), (-.02336, .06396, .95068)),
        Entity("e114", "cookie box", (.0865, .0371, .9194),
               (.03891, .00835, .90381), (.11761, .06598, .91992)),
        Entity("e54", "plate", (.0691, .2021, .9097),
               (.01009, .13916, .90723), (.13168, .26123, .91846)),
        Entity("e6", "ramekin", (-.2126, .1875, .9243),
               (-.24072, .14673, .90527), (-.15906, .22498, .94287)),
    ]
    phrase = "pick up the black bowl from table center and place it on the plate"
    policy = OriginalOraclePolicy(None)
    for symbol in ("akita_black_bowl_1", "akita_black_bowl_9"):
        assert policy.bind(symbol, entities, phrase, ((0, 1, 0), (1, 0, 0))).id == "e98"
    renamed = [replace(e, id=f"e{i + 10}") for i, e in enumerate(reversed(entities))]
    selected = policy.bind("akita_black_bowl_1", renamed, phrase, ((0, 1, 0), (1, 0, 0)))
    assert selected.xyz == entities[1].xyz


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


def test_collective_reference_moves_each_measured_member_without_private_instance_binding():
    from dataclasses import replace
    from types import SimpleNamespace

    status = {"done": False, "goals": [["on", "moka_pot_1", "stove_1_region"],
                                     ["on", "moka_pot_2", "stove_1_region"]],
              "satisfied": [False, False]}
    axes = ((0, 1, 0), (1, 0, 0))
    instruction = "put both moka pots on the stove"
    first = measured("e99", "moka pot", .0618, .0373, .06)
    second = measured("e98", "moka pot", -.0339, .2461, .06)
    stove = Entity("e114", "stove", (-.0266, -.2035, .9258),
                   (-.12, -.30, .91), (.07, -.11, .95))
    for suffixes in ((1, 2), (8, 3)):
        status["goals"] = [["on", f"moka_pot_{s}", "stove_9_region"] for s in suffixes]
        policy = OriginalOraclePolicy(SimpleNamespace(call=lambda *a, **k: status))
        entities = [first, second, stove]
        choices = candidates(entities, instruction, (0, 0, 1), None, [], random.Random(0))
        chosen = policy.choose(entities, choices, None, [], instruction, axes)
        assert chosen.text() == "grasp(e99,direct)"
        # Move the first measured member to the support.  The private
        # predicate order can differ from the expert's public binding order.
        status["satisfied"] = [False, True]
        entities[0] = replace(first, xyz=(-.02, -.20, 1),
                              lower=(-.05, -.23, .951), upper=(.01, -.17, 1.08))
        choices = candidates(entities, instruction, (0, 0, 1), None, [], random.Random(0))
        assert policy.choose(entities, choices, None, [], instruction, axes).text() == "grasp(e98,direct)"
        assert not any("moka_pot" in key for key in policy._bindings)
        status["satisfied"] = [False, False]
    # Singular language still requires a unique source, and missing
    # measurements cannot be replaced by the oracle's object identities.
    policy = OriginalOraclePolicy(SimpleNamespace(call=lambda *a, **k: status))
    choices = candidates([first, second, stove], instruction, (0, 0, 1), None, [], random.Random(0))
    assert policy.choose([first, second, stove], choices, None, [], "put a moka pot on the stove", axes).tool == "ask_help"
    assert policy.choose([first, stove], choices, None, [], instruction, axes).tool == "ask_help"


def test_occluded_member_after_failed_grasp_clears_view_before_remeasurement():
    from dataclasses import replace
    from types import SimpleNamespace

    status = {"done": False, "goals": [["on", "moka_pot_1", "stove_1_region"],
                                     ["on", "moka_pot_2", "stove_1_region"]],
              "satisfied": [False, False]}
    policy = OriginalOraclePolicy(SimpleNamespace(call=lambda *a, **k: status))
    hidden = replace(measured("e99", "moka pot", 0, 0, .06), visible=False)
    other = measured("e98", "moka pot", .2, 0, .06)
    stove = measured("e114", "stove", -.2, 0, .2)
    entities = [hidden, other, stove]
    text = "put both moka pots on the stove"
    failure = {"tool": "grasp", "object": "e99", "grasp_verified": False}
    receipts = [failure]
    choices = candidates(entities, text, (0, 0, 1), None, receipts, random.Random(0))
    assert policy.choose(entities, choices, None, receipts, text, ()).tool == "retreat"
    receipts.append({"tool": "retreat", "executed": True})
    assert policy.choose(entities, choices, None, receipts, text, ()).tool == "reperceive"
    receipts.append({"tool": "reperceive", "executed": True})
    assert policy.choose(entities, choices, None, receipts, text, ()).tool == "ask_help"
    # A fresh visible measurement unlocks the next staging mode.  The
    # recovery chain does not use the hidden object's stale coordinates.
    entities[0] = replace(hidden, visible=True)
    choices = candidates(entities, text, (0, 0, 1), None, receipts, random.Random(0))
    assert policy.choose(entities, choices, None, receipts, text, ()).text() == "grasp(e99,above_10cm)"


def test_hidden_object_after_unverified_place_is_remeasured_before_help():
    from dataclasses import replace
    from types import SimpleNamespace

    status = {"done": False, "goals": [["on", "cream_cheese_1", "akita_black_bowl_1"]],
              "satisfied": [False]}
    policy = OriginalOraclePolicy(SimpleNamespace(call=lambda *a, **k: status))
    hidden = replace(measured("e98", "cream cheese", -.12, .06, .04), visible=False)
    bowl = measured("e99", "bowl", -.07, 0, .10)
    entities = [hidden, bowl]
    text = "put the cream cheese in the bowl"
    receipts = [{"tool": "place", "object": "e98", "target": "e99",
                 "executed": True, "place_verified": False}]
    choices = candidates(entities, text, (0, 0, 1), None, receipts, random.Random(0))
    assert not any(c.object == hidden.id for c in choices)
    assert policy.choose(entities, choices, None, receipts, text, ()).tool == "retreat"
    receipts.append({"tool": "retreat", "executed": True})
    assert policy.choose(entities, choices, None, receipts, text, ()).tool == "reperceive"
    receipts.append({"tool": "reperceive", "executed": True})
    assert policy.choose(entities, choices, None, receipts, text, ()).tool == "ask_help"
    # A failed visual verification never overrides the independent completion.
    status["done"] = True
    assert policy.choose(entities, choices, None, receipts, text, ()).tool == "finish"


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


def test_closed_top_drawer_is_opened_before_interior_pose_binding():
    from types import SimpleNamespace
    region = "white_cabinet_1_top_region"
    rpc = SimpleNamespace(call=lambda *a, **k: {"done": False,
        "goals": [["in", "akita_black_bowl_1", region]], "satisfied": [False],
        "storage_open": {region: False}})
    cabinet = measured("e4", "cabinet", 0, 0, .2)
    bowl = measured("e5", "bowl", .2, 0, .1)
    policy = OriginalOraclePolicy(rpc)
    choices = [Candidate("articulate", "e4", mode="open"), Candidate("ask_help")]
    assert policy.choose([cabinet, bowl], choices, None, [],
        "open the top drawer and put the bowl inside", ((1, 0, 0), (0, 1, 0))) == choices[0]
    receipt = {"tool": "articulate", "object": "e4", "mode": "open"}
    assert policy.choose([cabinet, bowl], choices, None, [receipt],
        "open the top drawer and put the bowl inside", ((1, 0, 0), (0, 1, 0))) == choices[1]
