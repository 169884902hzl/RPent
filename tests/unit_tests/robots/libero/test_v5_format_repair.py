# Copyright 2026 Zhilun Hu.
# SPDX-License-Identifier: Apache-2.0
"""Regressions for failure evidence, measured support and category card binding."""

import random

import numpy as np

from robots.libero.v5_cards import VERSION, card_view, resolve_card, validate_card
from robots.libero.v5_fixture_parts import above_work_surface, fixture_parts, fixture_points
from robots.libero.v5_state import Candidate, Entity, candidates, recent_failures, serialize
from robots.libero.v5_verification import strict_place_verified


def entity(eid="e1", name="bowl", z=.14):
    return Entity(eid, name, (0, 0, z), (-.01, -.01, z-.01), (.01, .01, z+.01))


def test_failures_match_the_bound_action_and_verified_recovery_resets_count():
    action = Candidate("place", "e1", "e2", "on")
    failed = {"tool": "place", "object": "e1", "target": "e2", "mode": "on", "verification": "execution_error"}
    assert recent_failures(action, [failed, failed]) == (2, "execution_error")
    assert recent_failures(Candidate("place", "e1", "e3", "on"), [failed]) == (0, "none")
    assert recent_failures(action, [failed, {**failed, "verification": "verified"}]) == (0, "none")
    assert "recent_failures=2" in serialize("move", [entity()], .08, None, [failed]*2,
                                          choices=[action], failure_counts=True)


def test_failed_place_creates_recovery_without_fabricating_a_target():
    a, b = entity(), entity("e2", "plate")
    receipt = {"tool": "place", "object": "e1", "target": "e2", "mode": "on", "error": "servo waypoint"}
    cs = candidates([a,b], "put bowl on plate", (0,0,.3), "e1", [receipt], random.Random(3), adjust_place=True)
    assert Candidate("adjust_place", "e1", "e2", "on") in cs
    absent = candidates([a], "put bowl on plate", (0,0,.3), None, [receipt], random.Random(3), adjust_place=True)
    assert not any(c.tool == "adjust_place" for c in absent)


def test_strict_placement_rejects_a_stable_object_floating_above_support():
    plate = entity("e2", "plate", z=.1)
    floating = entity(z=.20)
    contact = entity(z=.12)
    assert not strict_place_verified(floating, floating, plate, .08, (0,0,.4), .31)
    assert strict_place_verified(contact, contact, plate, .08, (0,0,.4), .31)


def test_category_card_does_not_resolve_ambiguous_instances_or_wrong_held_object():
    card = {"version": VERSION, "origin": "original_oracle", "steps": [
        {"skill":"grasp", "object_category":"bowl", "mode":"direct"}]}
    validate_card(card)
    view = card_view(card, 0)
    assert resolve_card(view, [entity()], None) == Candidate("grasp", "e1", mode="direct")
    assert resolve_card(view, [entity(),entity("e2")], None) is None
    assert "xyz" not in view["next"]


def test_furniture_bands_come_from_current_depth_points_and_remain_in_parent_extent():
    parent = Entity("e1", "cabinet", (0,0,.3), (-.1,-.1,0), (.1,.1,.6))
    cloud=np.array([(x,y,z) for x in [-.1,0,.1] for y in [-.1,0,.1] for z in np.linspace(.01,.59,30)])
    parts = fixture_parts(parent, cloud, (1,0,0))
    assert {p['name'] for p in parts} >= {"cabinet top drawer","cabinet middle drawer","cabinet bottom drawer"}
    assert all(parent.lower[i] <= p['xyz'][i] <= parent.upper[i] for p in parts for i in range(3))
    assert not fixture_parts(parent, cloud[:2], (1,0,0))


def test_background_cabinet_below_the_measured_work_surface_is_rejected():
    parent = Entity("e55", "cabinet", (.08,.27,1.1), (-.12,.23,.92), (.12,.35,1.13))
    background = Entity("e62", "cabinet", (-1.39,-.49,.69), (-1.41,-.87,.38), (-1.36,-.26,.85))
    assert above_work_surface(parent, .91)
    assert not above_work_surface(background, .91)
    assert above_work_surface(background, None)
    cloud = np.array([[.08,.27,1.1],[-1.39,-.49,.69],[np.nan,0,0]])
    assert np.array_equal(fixture_points(cloud, parent), cloud[:1])


def test_public_choices_roundtrip_without_code_execution():
    for action in [Candidate("place","e1","e2","in"),Candidate("grasp","e1",mode="direct"),Candidate("retreat")]:
        assert Candidate.from_text(action.text()) == action


def test_instruction_queries_keep_both_nouns_without_a_language_model():
    from robots.libero.v5_runtime import instruction_noun_phrases
    assert instruction_noun_phrases("Pick up the akita black bowl and place it in the top drawer of the cabinet.") == [
        "akita black bowl", "top drawer", "cabinet"]
