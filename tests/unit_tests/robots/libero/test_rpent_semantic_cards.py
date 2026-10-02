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
