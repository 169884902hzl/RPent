"""Recipe categories preserve real nouns and reject unsupported composite actions."""

from robots.libero.rpent_semantic_cards import articulation_step, convert_recipe, grasp_category, measured_init0_anchors


def test_grocery_and_conjoined_mug_colours_keep_their_public_category():
    assert grasp_category("pick up the ketchup") == "ketchup"
    assert grasp_category("grasp the yellow and white mug") == "white yellow mug"
    assert grasp_category("pick up the white and yellow mug and put it on the plate") == "white yellow mug"
    assert grasp_category("Open the drawer and put the bowl inside") is None
    assert grasp_category("pick up the can") is None


def test_no_camera_measurement_stays_unmapped_after_a_valid_grasp():
    steps, _, unmapped = convert_recipe([
        {"action": "pi0_pick", "prompt": "pick up the ketchup"},
        {"action": "move_to", "xyz": [.1, .2, .3]},
        {"action": "release"},
    ], {"localization": "described in prose", "libero_terminated": True})
    assert steps == [{"skill": "grasp", "object_category": "ketchup", "mode": "direct"}]
    assert unmapped[0]["reason"] == "nearest measured init0 destination absent or ambiguous"
    assert measured_init0_anchors({"localization": {"method": 42}}) == []


def test_pick_primitive_with_placement_wording_still_maps_only_the_grasp():
    commands = [
        {"action": "pi0_pick", "prompt": "place the black bowl on the red ring plate"},
        {"action": "pi0_pick", "prompt": "put the wine bottle in the bowl"},
        {"action": "pi0_pick", "prompt": "Put the plate on the top of the drawer"},
    ]
    steps, evidence, unmapped = convert_recipe(commands, {})
    assert steps == [
        {"skill": "grasp", "object_category": "bowl", "mode": "direct"},
        {"skill": "grasp", "object_category": "wine bottle", "mode": "direct"},
        {"skill": "grasp", "object_category": "plate", "mode": "direct"},
    ]
    assert not unmapped and len(evidence) == len(commands)
    assert grasp_category("Open the top drawer and put the bowl inside") is None
    assert grasp_category("turn on the stove") is None


def test_contact_commands_with_single_fixture_operations_become_articulation():
    commands = [
        {"action": "pi0_pick", "prompt": "turn on the stove"},
        {"action": "pi0_doubled", "prompt": "close the bottom drawer of the cabinet"},
        {"action": "pi0_doubled", "prompt": "pull the lowest gray drawer handle outward"},
    ]
    steps, evidence, unmapped = convert_recipe(commands, {})
    assert steps == [
        {"skill": "articulate", "object_category": "stove", "mode": "turn_on"},
        {"skill": "articulate", "object_category": "cabinet bottom drawer", "mode": "close"},
        {"skill": "articulate", "object_category": "cabinet bottom drawer", "mode": "open"},
    ]
    assert len(evidence) == 3 and not unmapped
    assert articulation_step("pull the upper wooden drawer handle outward") == {
        "skill": "articulate", "object_category": "cabinet top drawer", "mode": "open"}
    for prompt in ("open the drawer", "open the top drawer and put the bowl inside",
                   "put the bowl on the stove", "push the bottle into the drawer"):
        assert articulation_step(prompt) is None


def test_unmapped_contact_operation_does_not_create_a_held_object_or_placement():
    steps, _, unmapped = convert_recipe([
        {"action": "pi0_doubled", "prompt": "push the tomato sauce can into the basket"},
        {"action": "move_to", "xyz": [.1, .2, .3]},
        {"action": "release"},
    ], {})
    assert not steps and len(unmapped) == 2
