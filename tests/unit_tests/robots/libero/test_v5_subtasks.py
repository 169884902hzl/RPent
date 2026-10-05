"""Public measured-entity rendering of complete contact subtasks."""

import pytest

from robots.libero.v5_state import Candidate, Entity
from robots.libero.v5_subtasks import subtask_candidates, subtask_prompt


def entity(eid, name, x=0, **kwargs):
    return Entity(eid, name, (x, 0, 1), (x - .03, -.03, .98), (x + .03, .03, 1.02), **kwargs)


@pytest.mark.parametrize("mode", ["on", "in"])
def test_complete_transfer_prompt_uses_selected_public_categories(mode):
    measured = [entity("e4", "frypan"), entity("e9", "basket", .1)]
    assert subtask_prompt(Candidate("vla_subtask", "e4", "e9", mode), measured) == (
        f"put the frying pan {mode} the basket")


@pytest.mark.parametrize("name,mode", [
    ("cabinet middle drawer", "open"), ("cabinet bottom drawer", "close"),
    ("microwave", "open"), ("microwave", "close"),
    ("stove", "turn_on"), ("stove", "turn_off"),
])
def test_fixture_prompt_is_a_complete_public_action(name, mode):
    measured = {"e5": entity("e5", name)}
    assert subtask_prompt(Candidate("vla_subtask", "e5", mode=mode), measured) == (
        f"{mode.replace('_', ' ')} the {name}")


@pytest.mark.parametrize("action", [
    Candidate("grasp", "e1", mode="direct"),
    Candidate("vla_subtask", "e1", mode="grasp"),
    Candidate("vla_subtask", "e1", "e1", "on"),
    Candidate("vla_subtask", "e1", "missing", "on"),
    Candidate("vla_subtask", "missing", "e2", "in"),
    Candidate("vla_subtask", "e1", mode="open"),
    Candidate("vla_subtask", "e2", "e1", "open"),
])
def test_prompt_rejects_unsupported_arguments_instead_of_emitting_free_text(action):
    measured = [entity("e1", "bowl"), entity("e2", "microwave")]
    with pytest.raises(ValueError):
        subtask_prompt(action, measured)


def test_full_transfer_and_fixture_macros_can_be_enumerated_without_task_files():
    measured = [entity("e1", "bowl"), entity("e2", "plate", .1), entity("e3", "stove", .3)]
    choices = subtask_candidates(measured, "put the bowl on the plate", (0, 0, 1.2), None)
    assert choices[0] == Candidate("vla_subtask", "e1", "e2", "on")
    assert all(action.tool == "vla_subtask" for action in choices)
    assert len(choices) <= 6
    assert any(action.object == "e3" and action.mode in ("turn_on", "turn_off") for action in choices)
    fixture_choices = subtask_candidates(measured, "turn on the stove", (0, 0, 1.2), None)
    assert fixture_choices[0] == Candidate("vla_subtask", "e3", mode="turn_on")


def test_held_object_is_the_only_source_for_transfer_macros():
    measured = [entity("e1", "bowl"), entity("e2", "butter", .1), entity("e3", "basket", .3)]
    choices = subtask_candidates(measured, "put the butter in the basket", (0, 0, 1.2), "e2")
    assert choices[0] == Candidate("vla_subtask", "e2", "e3", "in")
    assert all(action.object == "e2" for action in choices if action.target)


def test_missing_object_excluded_but_labelled_cached_measurement_remains_usable():
    measured = [entity("e1", "butter", visible=False),
                entity("e2", "bowl", visible=False, geometry="cached_perception_shape_prior"),
                entity("e3", "plate", .2)]
    choices = subtask_candidates(measured, "put the bowl on the plate", (0, 0, 1.2), None)
    assert Candidate("vla_subtask", "e2", "e3", "on") in choices
    assert all("e1" not in (action.object, action.target) for action in choices)


def test_articulation_front_bands_do_not_become_transfer_destinations():
    measured = [entity("e1", "butter"), entity("e2", "cabinet top drawer", .2,
                geometry="measured_front_band")]
    choices = subtask_candidates(measured, "open the cabinet top drawer", (0, 0, 1.2), None)
    assert Candidate("vla_subtask", "e2", mode="open") in choices
    assert all(action.target != "e2" for action in choices)


def test_macro_allowance_does_not_expand_the_state_candidate_budget():
    measured = [entity(f"e{i}", "bowl", i / 10) for i in range(10)]
    assert len(subtask_candidates(measured, "move the bowl", (0, 0, 1), None)) == 6
    assert subtask_candidates(measured, "move the bowl", (0, 0, 1), None, limit=0) == []
    with pytest.raises(ValueError):
        subtask_candidates(measured, "move the bowl", (0, 0, 1), None, limit=7)
