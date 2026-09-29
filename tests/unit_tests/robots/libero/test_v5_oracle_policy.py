# Copyright 2026 Zhilun Hu.
# SPDX-License-Identifier: Apache-2.0
"""Private oracle progress must bind to public measured instances."""

import random

from robots.libero.v5_oracle_policy import OriginalOraclePolicy
from robots.libero.v5_state import Entity, candidates, serialize


def measured(eid, name, x, y, width):
    return Entity(
        eid,
        name,
        (x, y, 0.93),
        (x - width / 2, y - width / 2, 0.90),
        (x + width / 2, y + width / 2, 0.95),
    )


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
