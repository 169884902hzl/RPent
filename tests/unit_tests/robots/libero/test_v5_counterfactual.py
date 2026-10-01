"""Counterfactual training retains original physical scene definitions."""

import pytest

from robots.libero.v5_counterfactual import counterfactual_bddl, replace_section


def test_only_registered_language_and_goal_change():
    original = "(define (:language put bowl on stove)\n(:regions (x (:ranges (0 1 2 3))))\n(:init (On bowl table))\n(:goal (And (On bowl stove))))"
    changed = counterfactual_bddl(original, ["On", "bowl", "plate"], "put bowl on plate")
    for text in ("(:regions (x (:ranges (0 1 2 3))))", "(:init (On bowl table))"):
        assert text in changed
    assert "(:language put bowl on plate)" in changed
    assert "(:goal (And (On bowl plate)))" in changed
    assert replace_section(replace_section(changed, "language", "(:language)"), "goal", "(:goal)") == replace_section(replace_section(original, "language", "(:language)"), "goal", "(:goal)")


def test_scene_text_and_unregistered_predicates_cannot_enter_goal():
    with pytest.raises(ValueError):
        counterfactual_bddl("(:goal (And))", ["Navigate", "bowl", "plate"], "go elsewhere")
    with pytest.raises(ValueError):
        counterfactual_bddl("(:goal (And))", ["On", "bowl)", "plate"], "put bowl on plate")
