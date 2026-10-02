"""Recipe categories preserve real nouns and reject unsupported composite actions."""

from robots.libero.rpent_semantic_cards import convert_recipe, grasp_category, measured_init0_anchors


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
