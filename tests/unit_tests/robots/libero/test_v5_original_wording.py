from scripts.revise_original_wording_bank import revise


def test_plural_goal_keeps_plural_pronoun_and_explicit_destination():
    original = "put both the alphabet soup and the tomato sauce in the basket"
    assert revise("Pick up both the alphabet soup and the tomato sauce, then put it in the basket.", original) == (
        "Pick up both the alphabet soup and the tomato sauce, then put them into the basket."
    )


def test_source_relation_is_not_converted_to_a_destination():
    original = "pick up the black bowl on the stove and place it on the plate"
    assert revise("Move the black bowl on the stove on the plate.", original) == (
        "Move the black bowl on the stove onto the plate."
    )


def test_two_destinations_keep_distinct_target_mugs():
    original = "put the white mug on the left plate and put the yellow and white mug on the right plate"
    assert revise(original + ".", original) == (
        "put the white mug onto the left plate and put the yellow and white mug onto the right plate."
    )


def test_drawer_close_pronoun_is_not_pluralized():
    original = "put the black bowl in the bottom drawer of the cabinet and close it"
    assert revise(original + ".", original) == (
        "put the black bowl into the bottom drawer of the cabinet and close it."
    )
