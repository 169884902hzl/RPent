"""Unique original probe objects may lack goal-predicate bindings."""

from scripts.summarize_v5_geometry_probe import reference_binding


def test_unique_category_probe_uses_saved_original_reference():
    private = {"bindings": {}, "reference": {"chocolate_pudding_1": {"xyz": [0, 0, 1]}}}
    assert reference_binding(private, {"name": "chocolate pudding"}, "e9") == (
        "chocolate_pudding_1", "unique_original_reference_category")


def test_two_same_category_references_remain_unresolved():
    private = {"bindings": {}, "reference": {"akita_black_bowl_1": {}, "white_bowl_1": {}}}
    assert reference_binding(private, {"name": "bowl"}, "e9") == (
        None, "unresolved_reference_category")


def test_saved_oracle_binding_wins_over_category_ambiguity():
    private = {"bindings": {"akita_black_bowl_1": "e9"},
               "reference": {"akita_black_bowl_1": {}, "white_bowl_1": {}}}
    assert reference_binding(private, {"name": "bowl"}, "e9") == (
        "akita_black_bowl_1", "oracle_binding")
