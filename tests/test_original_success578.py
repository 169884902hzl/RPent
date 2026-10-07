"""Private-label diagnostics must not change action selection or public output."""
from dataclasses import dataclass
from types import SimpleNamespace
import importlib.util
from pathlib import Path


def module(name):
    path = Path(__file__).resolve().parents[1] / "scripts" / (name + ".py")
    spec = importlib.util.spec_from_file_location(name, path)
    item = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(item)
    return item


def test_private_hook_keeps_exact_public_result_and_action():
    wrapper = module("run_original_success578")
    calls = []
    @dataclass
    class Action:
        tool: str = "grasp"
        object: str = "e17"
        target: str | None = None
        mode: str = "direct"
    action = Action()
    entity = SimpleNamespace(name="bowl", xyz=(.1, .2, .3))
    client = SimpleNamespace(call=lambda method, **kw: calls.append((method, kw)) or {"logged": True})
    executor = SimpleNamespace(scene=SimpleNamespace(entities={"e17": entity}),
                               p=SimpleNamespace(env=SimpleNamespace(_client=client)))
    result = ({"grasp_verified": False, "executed": True}, action)
    def original(e, a, v, c, r):
        assert a is action
        return result
    run = wrapper.instrument_execute(original)
    assert run(executor, action, None, None, {}) is result
    assert calls[0][0] == "diagnostic.action_begin"
    assert calls[1][0] == "diagnostic.action_end"
    assert calls[0][1]["source"] == {"name": "bowl", "xyz": [.1, .2, .3]}
    run(executor, action, None, None, {})
    assert calls[2][1]["sequence"] == 1
    assert "simulation_truth" not in result[0]


def test_private_binding_abstains_on_ambiguous_bowls():
    scorer = module("original_success578_server")
    source = {"name": "bowl", "xyz": [0., 0., 0.]}
    objects = {"akita_black_bowl_1": {"xyz": [.02, 0., 0.]},
               "akita_black_bowl_2": {"xyz": [.03, 0., 0.]}}
    assert scorer.match_source(source, objects)[0] is None
    assert scorer.match_source(source, {"akita_black_bowl_1": objects["akita_black_bowl_1"]})[0] == "akita_black_bowl_1"


def test_private_goal_mapping_rejects_another_compartment():
    scorer = module("original_success578_server")
    goals = [["in", "akita_black_bowl_1", "wooden_cabinet_1_bottom_region"]]
    action = {"mode": "in"}
    assert scorer.matching_goals(goals, action, "akita_black_bowl_1", {"name": "cabinet top drawer"}) == []
