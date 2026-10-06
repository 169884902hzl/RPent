"""Public measured-entity rendering of complete contact subtasks."""

import pytest

from robots.libero.v5_state import Candidate, Entity, relations
from robots.libero.v5_subtasks import SubtaskBindingError, subtask_candidates, subtask_prompt


def entity(eid, name, x=0, y=0, z=1, **kwargs):
    return Entity(eid, name, (x, y, z), (x - .03, y - .03, z - .02),
                  (x + .03, y + .03, z + .02), **kwargs)


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


def test_two_identical_bowls_describe_selected_id_without_correcting_wrong_selection():
    measured = [entity("e98", "bowl", -.2), entity("e43", "bowl", .2), entity("e22", "plate", .4)]
    left = Candidate("vla_subtask", "e98", "e22", "on")
    right = Candidate("vla_subtask", "e43", "e22", "on")
    assert subtask_prompt(left, measured) == "put the leftmost bowl on the plate"
    assert subtask_prompt(right, measured) == "put the rightmost bowl on the plate"
    assert left.text() == "vla_subtask(e98,e22,on)"
    # The original goal is deliberately irrelevant to selected-ID rendering.
    assert subtask_prompt(right, measured) != subtask_prompt(left, measured)


def test_repeated_destination_class_is_disambiguated_as_well_as_source():
    measured = [entity("e1", "butter"), entity("e2", "bowl", -.2), entity("e3", "bowl", .2)]
    assert subtask_prompt(Candidate("vla_subtask", "e1", "e3", "in"), measured) == (
        "put the butter in the rightmost bowl")


def test_selected_instance_order_rotates_with_same_public_axes_as_state_relations():
    measured = [entity("e98", "bowl", y=-.2), entity("e43", "bowl", y=.2), entity("e22", "plate", .4)]
    axes = ((0, 1, 0), (1, 0, 0))
    assert "rel e98 left_of e43" in relations(measured, right_axis=axes[0], front_axis=axes[1])
    assert subtask_prompt(Candidate("vla_subtask", "e98", "e22", "on"), measured, axes) == (
        "put the leftmost bowl on the plate")
    opposite = ((0, -1, 0), (-1, 0, 0))
    assert subtask_prompt(Candidate("vla_subtask", "e98", "e22", "on"), measured, opposite) == (
        "put the rightmost bowl on the plate")


def test_front_and_ordinal_descriptions_follow_measured_positions():
    measured = [entity("e1", "bowl", y=-.3), entity("e2", "bowl"),
                entity("e3", "bowl", y=.3), entity("e4", "plate", .4)]
    assert subtask_prompt(Candidate("vla_subtask", "e1", "e4", "on"), measured) == (
        "put the frontmost bowl on the plate")
    assert subtask_prompt(Candidate("vla_subtask", "e2", "e4", "on"), measured) == (
        "put the second bowl from the front on the plate")
    assert subtask_prompt(Candidate("vla_subtask", "e3", "e4", "on"), measured) == (
        "put the backmost bowl on the plate")
    horizontal = [entity("e1", "bowl", -.3), entity("e2", "bowl"),
                  entity("e3", "bowl", .3), entity("e4", "plate", .4)]
    assert subtask_prompt(Candidate("vla_subtask", "e2", "e4", "on"), horizontal) == (
        "put the second bowl from the left on the plate")


def test_measured_relation_to_unique_anchor_resolves_stacked_instances():
    measured = [entity("e1", "bowl", z=1.04), entity("e2", "bowl", z=1.2),
                entity("e3", "plate", z=1), entity("e4", "basket", .4)]
    assert "rel e1 on e3" in relations(measured)
    assert subtask_prompt(Candidate("vla_subtask", "e1", "e4", "in"), measured) == (
        "put the bowl that is on the plate in the basket")


@pytest.mark.parametrize("offset", [0, .019, .02])
def test_near_tied_positions_do_not_bind_by_neutral_id_or_input_order(offset):
    measured = [entity("e1", "bowl"), entity("e9", "bowl", offset), entity("e2", "plate", .4)]
    action = Candidate("vla_subtask", "e1", "e2", "on")
    for order in (measured, list(reversed(measured))):
        with pytest.raises(SubtaskBindingError, match="cannot uniquely bind selected e1"):
            subtask_prompt(action, order)


def test_near_tied_other_instances_do_not_invent_an_interior_ordinal():
    measured = [entity("e1", "bowl"), entity("e2", "bowl", .01),
                entity("e3", "bowl", .3), entity("e4", "bowl", .6), entity("e5", "plate", .8)]
    with pytest.raises(SubtaskBindingError):
        subtask_prompt(Candidate("vla_subtask", "e3", "e5", "on"), measured)


def test_unmeasured_duplicate_blocks_binding_but_public_cached_pose_can_resolve_it():
    source, target = entity("e1", "bowl", -.2), entity("e3", "plate", .4)
    unseen = entity("e2", "bowl", .2, visible=False)
    with pytest.raises(SubtaskBindingError, match="measurement unavailable"):
        subtask_prompt(Candidate("vla_subtask", "e1", "e3", "on"), [source, unseen, target])
    cached = entity("e2", "bowl", .2, visible=False, geometry="cached_perception_shape_prior")
    assert subtask_prompt(Candidate("vla_subtask", "e1", "e3", "on"), [source, cached, target]) == (
        "put the leftmost bowl on the plate")


def test_instance_descriptions_are_invariant_to_id_randomization_and_entity_order():
    a = [entity("e98", "bowl", -.2), entity("e43", "bowl", .2), entity("e22", "plate", .4)]
    b = [entity("e3", "plate", .4), entity("e1", "bowl", .2), entity("e90", "bowl", -.2)]
    assert subtask_prompt(Candidate("vla_subtask", "e98", "e22", "on"), a) == (
        subtask_prompt(Candidate("vla_subtask", "e90", "e3", "on"), b))


def test_aliases_that_render_the_same_category_do_not_hide_duplicate_instances():
    measured = [entity("e1", "frypan", -.2), entity("e2", "frying pan", .2), entity("e3", "plate", .4)]
    assert subtask_prompt(Candidate("vla_subtask", "e2", "e3", "on"), measured) == (
        "put the rightmost frying pan on the plate")


def test_ambiguous_macros_are_excluded_without_changing_other_typed_candidates():
    measured = [entity("e1", "bowl"), entity("e2", "bowl"), entity("e3", "plate", .4)]
    assert subtask_candidates(measured, "put the bowl on the plate", (0, 0, 1.2), None) == []


@pytest.mark.parametrize("name,geometry", [
    ("cabinet top surface", "measured_top_surface"),
    ("cabinet top surface", None),
    ("cabinet", "measured_top_surface"),
])
def test_top_surface_allows_on_but_never_in_even_when_name_contains_cabinet(name, geometry):
    measured = [entity("e22", "cream cheese"), entity("e50", name, .2, geometry=geometry)]
    choices = subtask_candidates(measured, "put the cream cheese in the cabinet", (0, 0, 1.2), None)
    assert Candidate("vla_subtask", "e22", "e50", "in") not in choices
    assert Candidate("vla_subtask", "e22", "e50", "on") in choices
    with pytest.raises(ValueError, match="not a top surface"):
        subtask_prompt(Candidate("vla_subtask", "e22", "e50", "in"), measured)
    assert subtask_prompt(Candidate("vla_subtask", "e22", "e50", "on"), measured) == (
        f"put the cream cheese on the {name}")


def test_real_drawer_remains_an_in_target():
    measured = [entity("e1", "butter"), entity("e2", "cabinet top drawer", .2)]
    assert Candidate("vla_subtask", "e1", "e2", "in") in subtask_candidates(
        measured, "put the butter in the cabinet top drawer", (0, 0, 1.2), None)


def test_duplicate_fixture_instances_and_invalid_axes_are_explicit():
    measured = [entity("e1", "microwave", -.2), entity("e2", "microwave", .2)]
    assert subtask_prompt(Candidate("vla_subtask", "e2", mode="open"), measured) == (
        "open the rightmost microwave")
    with pytest.raises(ValueError, match="planar view axes"):
        subtask_prompt(Candidate("vla_subtask", "e2", mode="open"), measured, ((0, 0, 0), (0, -1, 0)))
