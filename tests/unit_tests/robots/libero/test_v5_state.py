# Copyright 2026 Zhilun Hu.
# SPDX-License-Identifier: Apache-2.0
"""Observable v5 boundaries: geometry, finite choices and visual evidence."""

import random
from dataclasses import replace
from types import SimpleNamespace

import pytest

from robots.libero.v5_state import (
    Candidate,
    Entity,
    candidates,
    grasp_verified,
    place_verified,
    prepare_request,
    relations,
    serialize,
)


def measured(eid="e1", name="bowl", xyz=(0.0, 0.0, 0.10)):
    return Entity(
        eid, name, xyz, tuple(x - 0.01 for x in xyz), tuple(x + 0.01 for x in xyz)
    )


def test_candidates_cover_instances_and_bound_choices():
    entities = [measured(f"e{i}", "bowl", (i / 10, 0.0, 0.10)) for i in range(12)]
    choices = candidates(entities, "move a bowl", (0, 0, 0), None, [], random.Random(4))
    assert len(choices) <= 24
    assert {c.object for c in choices if c.tool == "grasp"} == {
        f"e{i}" for i in range(8)
    }
    assert all(c.tool not in ("segment", "back_project") for c in choices)
    assert {c.tool for c in choices} >= {
        "finish",
        "ask_help",
        "release",
        "retreat",
        "reperceive",
    }


def test_recovery_requires_actual_failed_grasp_receipt():
    e = measured()
    initial = candidates([e], "move bowl", (0, 0, 0), None, [], random.Random(2))
    failed = candidates(
        [e],
        "move bowl",
        (0, 0, 0),
        None,
        [{"tool": "grasp", "object": "e1", "grasp_verified": False}],
        random.Random(2),
    )
    assert not any(c.tool == "regrasp_restage" for c in initial)
    assert any(c.tool == "regrasp_restage" and c.object == "e1" for c in failed)


def test_measured_table_is_a_reference_and_place_target_without_grasp_choices():
    bowl, table = measured(), measured("e2", "table")
    initial = candidates([bowl, table], "move bowl from table center", (0, 0, 0), None, [], random.Random(2))
    assert any(c.tool == "grasp" and c.object == bowl.id for c in initial)
    assert not any(c.tool == "grasp" and c.object == table.id for c in initial)
    held = candidates([bowl, table], "put bowl on table", (0, 0, 0), bowl.id, [], random.Random(2))
    assert Candidate("place", bowl.id, table.id, "on") in held


def test_relations_and_request_use_measured_units():
    a, b = measured(), measured("e2", "plate", (0.10, 0.10, 0.10))
    text = serialize("put bowl on plate", [a, b], 0.08, None, [{"tool": "retreat"}] * 5)
    assert "xyz_cm=[10.0,10.0,10.0]" in text
    assert "rel e1 left_of e2" in relations([a, b])
    assert text.count("receipt ") == 3
    assert "src=perception" in text
    assert not any(x in text for x in ("obj_", "zone_", "BDDL"))


def test_complete_prompt_limit_includes_options_and_rejects_without_truncating():
    seen = []

    def prepare(tokenizer, context, definition, limit):
        seen.append((context, definition, limit))
        return SimpleNamespace(full_ids=[list(range(3073))])

    with pytest.raises(ValueError, match="3073 tokens"):
        prepare_request(
            None, prepare, "whole state", [Candidate("finish"), Candidate("ask_help")]
        )
    assert seen[0][0] == "whole state"
    assert seen[0][1]["action"]["choice_descriptions"] == {
        "C0": "finish()",
        "C1": "ask_help()",
    }
    assert seen[0][2] == 3072


def test_visible_side_of_support_can_establish_contact_without_containing_source_center():
    bowl = Entity("e1", "bowl", (0, 0, 1.04), (-.04, -.04, 1.01), (.04, .04, 1.07))
    box = Entity("e2", "cookie box", (.035, 0, 1), (.03, -.02, .98), (.04, .02, 1))
    assert "rel e1 on e2" in relations([bowl, box])


def test_grasp_needs_visual_rise_and_aperture():
    a = measured()
    risen = measured(xyz=(0, 0, 0.14))
    assert grasp_verified(a, risen, 0.04)
    assert not grasp_verified(a, a, 0.04)
    assert not grasp_verified(a, risen, 0.0)
    assert not grasp_verified(a, replace(risen, visible=False), 0.04)


def test_relations_use_the_measured_camera_basis_without_changing_world_coordinates():
    a = measured(xyz=(0.1, 0.0, 0.1))
    b = measured("e2", "plate", (0.0, 0.1, 0.1))
    rows = relations([a, b], right_axis=(0, 1, 0), front_axis=(1, 0, 0))
    assert "rel e1 left_of e2" in rows
    assert "rel e1 in_front_of e2" in rows
    text = serialize(
        "move bowl", [a, b], 0.08, None, [], view_axes=((0, 1, 0), (1, 0, 0))
    )
    assert "xyz_cm=[10.0,0.0,10.0]" in text
    assert "frame=agentview_planar" in text


def test_place_needs_two_stable_frames_release_and_retreat():
    target = measured("e2", "plate", (0, 0, 0.10))
    placed = measured(xyz=(0, 0, 0.14))
    assert place_verified(placed, placed, target, 0.08, (0, 0, 0.25), 0.31)
    assert not place_verified(placed, placed, target, 0.08, (0, 0, 0.25), 0.10)
    assert not place_verified(placed, placed, target, 0.04, (0, 0, 0.25), 0.31)
    assert not place_verified(placed, placed, target, 0.08, placed.xyz, 0.31)
    assert not place_verified(
        placed, measured(xyz=(0.03, 0, 0.14)), target, 0.08, (0, 0, 0.25), 0.31
    )


def test_container_placement_requires_measured_containment_instead_of_above_rim():
    target = Entity("e2", "basket", (0, 0, .10), (-.1, -.1, .05), (.1, .1, .20))
    lid = measured(xyz=(0, 0, .12))
    assert place_verified(lid, lid, target, .08, (0, 0, .30), .31, relation="in")
    assert not place_verified(lid, lid, target, .08, (0, 0, .30), .31, relation="on")
    below = measured(xyz=(0, 0, .02))
    assert not place_verified(below, below, target, .08, (0, 0, .30), .31, relation="in")
    assert not place_verified(lid, lid, target, .04, (0, 0, .30), .31, relation="in")


def test_on_relation_tolerates_measured_contact_surface_quantiles():
    bowl = Entity(
        "e99",
        "bowl",
        (0.0549, 0.2128, 0.9341),
        (0.0211, 0.1646, 0.9170),
        (0.1128, 0.2583, 0.9746),
    )
    plate = Entity(
        "e34",
        "plate",
        (0.0509, 0.2070, 0.9097),
        (-0.0078, 0.1438, 0.9072),
        (0.1141, 0.2661, 0.9185),
    )
    assert "rel e99 on e34" in relations([bowl, plate])
    floating = replace(
        bowl,
        xyz=(0.0549, 0.2128, 1.01),
        lower=(0.0211, 0.1646, 0.99),
        upper=(0.1128, 0.2583, 1.03),
    )
    assert "rel e99 on e34" not in relations([floating, plate])
