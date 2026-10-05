"""Original-only exploratory pairing and honest comparison denominators."""

import pytest

from scripts.prepare_v5_skill500_original_comparisons import ORIGINAL_SUITES, build_explorations


def original_catalog():
    tasks = [{"suite": suite, "task": index, "asset_family": "LIBERO-original",
              "instruction": "original task instruction", "trials": 50,
              "state_sha256": [f"{seed:064x}" for seed in range(50)],
              "oracle_goal_predicates": [], "symbol_categories": {},
              "bddl": {"path": f"original/{suite}/{index}.bddl", "sha256": "1" * 64},
              "init_file": {"path": f"original/{suite}/{index}.pruned_init", "sha256": "2" * 64}}
             for suite in ORIGINAL_SUITES for index in range(10)]
    by_key = {(task["suite"], task["task"]): task for task in tasks}
    changes = {
        ("libero_goal", 0): ([['open', 'wooden_cabinet_1_middle_region']],
                             {"wooden_cabinet_1_middle_region": "cabinet"}),
        ("libero_10", 3): ([['close', 'white_cabinet_1_bottom_region']],
                           {"white_cabinet_1_bottom_region": "cabinet"}),
        ("libero_10", 9): ([['close', 'microwave_1']], {"microwave_1": "microwave"}),
        ("libero_goal", 7): ([['turnon', 'flat_stove_1']], {"flat_stove_1": "stove"}),
        ("libero_goal", 8): ([['on', 'bowl_1', 'plate_1']], {"bowl_1": "bowl", "plate_1": "plate"}),
        ("libero_object", 1): ([['in', 'cream_cheese_1', 'basket_1']],
                              {"cream_cheese_1": "cream cheese", "basket_1": "basket"}),
        ("libero_10", 2): ([['on', 'moka_pot_1', 'flat_stove_1_cook_region']],
            {"moka_pot_1": "moka pot", "chefmate_8_frypan_1": "frypan", "flat_stove_1_cook_region": "stove"}),
    }
    for key, (goals, categories) in changes.items():
        by_key[key].update(oracle_goal_predicates=goals, symbol_categories=categories)
    return tasks


def test_each_type_has_hundred_paired_nominal_requests_per_arm_not_confirmation():
    plans = build_explorations(original_catalog(), {"path": "base", "sha256": "a" * 64}, "choice")
    assert {name: len(plan["cases"]) for name, plan in plans.items()} == {
        "full": 400, "fixtures": 1200, "place": 400}
    for plan in plans.values():
        assert all(count == 100 for count in plan["preregistered_requests_by_type_arm"].values())
        assert plan["new_training_rows"] == 0
        assert "never confirmation" in plan["purpose"]
        assert "50 unique scenes" in plan["state_repetition"]
        for condition in plan["conditions"].values():
            assert condition["overrides"]["vla_subtask_v1"] is True
            assert condition["overrides"]["measured_action_receipts_v1"] is True
            assert condition["overrides"]["measurement_progress_blocking_v1"] is True
        for kind in {case["type"] for case in plan["cases"]}:
            selected = [case for case in plan["cases"] if case["type"] == kind]
            for arm in plan["conditions"]:
                rows = [case for case in selected if case["condition"] == arm]
                assert {row["episode"]["seed"] for row in rows} == set(range(50))
                assert {row["initial_state_repetition"] for row in rows} == {0, 1}
                assert len({row["state_sha256"] for row in rows}) == 50


def test_actual_original_goal_source_and_registered_pan_counterfactual_are_distinguished():
    plan = build_explorations(original_catalog(), {}, "choice")["full"]
    pan = next(case for case in plan["cases"] if case["type"] == "pan_handle_full")
    moka = next(case for case in plan["cases"] if case["type"] == "moka_handle_full")
    assert pan["subtask_prompt"] == "put the frying pan on the stove"
    assert "registered_original_scene" in pan["prompt_origin"]
    assert "original_moka_transfer_clause" in moka["prompt_origin"]
    assert all(not arm.get("grasp_early_stop", False) for name, arm in plan["conditions"].items()
               if name == "handle_full_subtask160")
    assert "not sustained-grasp success" in plan["metrics"]["grasp_after_release"]


def test_first_place_requires_real_verified_setup_with_failures_preserved():
    plan = build_explorations(original_catalog(), {}, "choice")["place"]
    for case in plan["cases"]:
        assert case["setup"][0]["tool"] == "grasp"
        assert case["setup"][0]["required_public_receipt"] == "grasp_verified"
        assert case["setup"][0]["private_diagnostic"] == "true_sustained_grasp_record_only"
    assert "record not_attempted" in plan["setup_failures"]


@pytest.mark.parametrize("invalid", ["pro_suite", "missing_task", "empty_states"])
def test_invalid_asset_catalog_rejected_before_any_exploration_is_registered(invalid):
    tasks = original_catalog()
    if invalid == "pro_suite":
        tasks[0]["suite"] = "libero_spatial_swap"
    elif invalid == "missing_task":
        tasks.pop()
    else:
        tasks[0]["state_sha256"] = []
    with pytest.raises(ValueError):
        build_explorations(tasks, {}, "choice")
