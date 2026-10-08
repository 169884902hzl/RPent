# Copyright 2026 Zhilin Hu.
# SPDX-License-Identifier: Apache-2.0
"""Cached measured sources remain bindable for collective transfers."""

from types import SimpleNamespace

from robots.libero.v5_oracle_policy import OriginalOraclePolicy, NoLegalCandidate
from robots.libero.v5_state import Candidate, Entity


def measured(eid, name, x, y, *, cached=False):
    return Entity(
        eid,
        name,
        (x, y, 0.93),
        (x - 0.04, y - 0.04, 0.90),
        (x + 0.04, y + 0.04, 0.96),
        visible=not cached,
        geometry="cached_perception:latest" if cached else "measured_rgbd",
    )


def test_collective_source_uses_cached_measured_member():
    status = {
        "done": False,
        "goals": [["on", "moka_pot_1", "flat_stove_1"],
                  ["on", "moka_pot_2", "flat_stove_1"]],
        "satisfied": [False, False],
    }
    policy = OriginalOraclePolicy(SimpleNamespace(call=lambda *a, **k: status))
    entities = [
        measured("m1", "moka pot", 0.0, 0.0),
        measured("m2", "moka pot", 0.1, 0.0, cached=True),
        Entity("stove", "stove", (0.05, 0.0, 0.90), (-0.10, -0.10, 0.88),
               (0.20, 0.10, 0.92), geometry="measured_rgbd"),
    ]
    choices = [Candidate("grasp", "m1", mode="direct"),
               Candidate("grasp", "m2", mode="direct"),
               Candidate("ask_help")]
    selected = policy.choose(
        entities, choices, None, [], "put both moka pots on the stove", (),
    )
    assert selected.tool == "grasp"
    assert selected.object in {"m1", "m2"}


def test_collective_source_does_not_invent_unmeasured_hidden_member():
    status = {
        "done": False,
        "goals": [["on", "moka_pot_1", "flat_stove_1"],
                  ["on", "moka_pot_2", "flat_stove_1"]],
        "satisfied": [False, False],
    }
    policy = OriginalOraclePolicy(SimpleNamespace(call=lambda *a, **k: status))
    entities = [
        measured("m1", "moka pot", 0.0, 0.0),
        Entity("stove", "stove", (0.05, 0.0, 0.90), (-0.10, -0.10, 0.88),
               (0.20, 0.10, 0.92), geometry="measured_rgbd"),
    ]
    choices = [Candidate("retreat"), Candidate("reperceive")]
    selected = policy.choose(
        entities, choices, None, [], "put both moka pots on the stove", (),
    )
    assert selected.tool == "retreat"
