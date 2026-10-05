"""Original recipe parameters, failed steps and evaluation isolation."""

import hashlib
import json
import random
from types import SimpleNamespace

import pytest

from robots.libero.v5_rpent_recipe import OriginalRecipe, add_recipe_choice
from robots.libero.v5_state import Candidate, serialize


def recipe_file(tmp_path, commands):
    path = tmp_path / "task_recipe.jsonl"
    path.write_text("".join(json.dumps(c) + "\n" for c in commands))
    index = tmp_path / "index.json"
    index.write_text(json.dumps({"evaluation_only": True, "training_allowed": False,
        "files": [{"name": path.name, "path": str(path),
                   "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}]}))
    return index


def executor(reply):
    calls = []
    def execute(name, parameters):
        calls.append((name, parameters))
        if isinstance(reply, Exception):
            raise reply
        return SimpleNamespace(result=reply)
    obj = SimpleNamespace(toolkit=SimpleNamespace(execute_tool=execute),
        p=SimpleNamespace(env=SimpleNamespace(terminated=False), _last_obs_gripper=.08),
        scene=SimpleNamespace(entities={}, vocabulary=[], refresh=lambda names: None),
        capture=lambda **kwargs: None, receipts=[], held=None, held_offset=None)
    return obj, calls


def test_recipe_preserves_raw_move_parameters_and_keeps_coordinates_out_of_public_text(tmp_path):
    command = {"action": "move_to", "xyz": [.15, -.21, 1.12], "gripper": -1, "max_steps": 135}
    recipe = OriginalRecipe(recipe_file(tmp_path, [command, {"action": "release"}]))
    obj, calls = executor({"final_dist_m": .01})
    receipt = recipe.execute(obj)
    assert calls == [("move_to", {k:v for k,v in command.items() if k != "action"})]
    assert recipe.last_execution["command"] == command
    assert recipe.index == 1 and receipt["recipe_step"] == 1
    state = serialize("move the cup", [], .08, None, [receipt], card=recipe.view())
    assert "1.12" not in state and "-0.21" not in state and '"xyz"' not in state
    assert "card step=2/2" in state


def test_failed_pick_keeps_next_original_step_pending_after_planner_recovery(tmp_path):
    recipe = OriginalRecipe(recipe_file(tmp_path, [{"action": "pi0_pick", "prompt": "pick up the bowl", "max_chunks": 67}]))
    obj, calls = executor({"success": False, "chunks_used": 67})
    receipt = recipe.execute(obj)
    assert receipt["verification"] == "failed" and recipe.index == 0
    obj.receipts.append({"tool": "clear_view", "executed": True})
    recipe.execute(obj)
    assert len(calls) == 2 and calls[0] == calls[1]
    assert recipe.index == 0


def test_captured_tool_envelope_uses_primitive_outcome_without_images_or_truth(tmp_path):
    recipe = OriginalRecipe(recipe_file(tmp_path, [{"action": "pi0_pick", "prompt": "pick up the bowl"}]))
    obj, _ = executor({"log": {"result": {"success": False, "chunks_used": 24}},
                       "_image_bytes": b"private-image", "state": {"object_pos": [1, 2, 3]}})
    assert recipe.execute(obj)["verification"] == "failed"
    assert recipe.index == 0
    assert recipe.last_execution["result"] == {"success": False, "chunks_used": 24}
    json.dumps(recipe.last_execution)


def test_captured_primitive_error_retains_step_and_triggers_error_cooldown(tmp_path):
    recipe = OriginalRecipe(recipe_file(tmp_path, [{"action": "move_to", "xyz": [0, 0, 1]}]))
    obj, _ = executor({"log": {"result": {"error": "servo unavailable"}}})
    receipt = recipe.execute(obj)
    assert receipt["verification"] == "execution_error" and recipe.index == 0
    assert add_recipe_choice([], recipe, obj.receipts, random.Random(1), True) == []


def test_intermediate_contact_task_not_yet_complete_advances_unverified(tmp_path):
    recipe = OriginalRecipe(recipe_file(tmp_path, [{"action": "pi0_doubled", "prompt": "open drawer"}]))
    obj, _ = executor({"log": {"result": {"success": False, "contact_skill_executed": True}}})
    receipt = recipe.execute(obj)
    assert receipt["verification"] == "unverified" and recipe.index == 1


def test_recipe_error_is_cooled_down_only_for_the_same_step(tmp_path):
    recipe = OriginalRecipe(recipe_file(tmp_path, [{"action": "release"}, {"action": "retreat"}]))
    obj, _ = executor(ValueError("original tool unavailable"))
    receipt = recipe.execute(obj)
    assert receipt["verification"] == "execution_error" and recipe.index == 0
    base = [Candidate("retreat"), Candidate("ask_help")]
    assert add_recipe_choice(base, recipe, obj.receipts, random.Random(1), True) == base
    recipe.index = 1
    choices = add_recipe_choice(base, recipe, obj.receipts, random.Random(1), True)
    assert Candidate("rpent_step", mode="2") in choices
    assert Candidate.from_text("rpent_step(2)") == Candidate("rpent_step", mode="2")


def test_recipe_finish_is_rejected_without_native_success(tmp_path):
    recipe = OriginalRecipe(recipe_file(tmp_path, [{"action": "finish"}]))
    obj, calls = executor({})
    assert recipe.execute(obj)["verification"] == "environment_incomplete"
    assert recipe.index == 0 and calls == []


def test_training_and_oracle_arms_reject_recipe_before_loading_any_file():
    from harness_v5_eval import run_episode
    with pytest.raises(ValueError, match="evaluation-only"):
        run_episode(SimpleNamespace(provider="oracle", rpent_recipe_index="/must-not-be-opened"))
    with pytest.raises(ValueError, match="evaluation-only"):
        run_episode(SimpleNamespace(provider="jev", rpent_recipe_index="/must-not-be-opened"), collection=object())
