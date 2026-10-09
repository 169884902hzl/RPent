"""Public budget accounting and incomplete macros must remain observable."""

from types import SimpleNamespace

import numpy as np
import pytest

from robots.libero.v5_env_server import V5EnvFacade
from robots.libero.v5_recovery import MeasuredRecovery
from robots.libero.v5_skill_budget import action_costs, budget_end_kind, task_completion_receipt
from robots.libero.v5_state import Candidate, Entity, measurement_progress_blocked, serialize


def test_budget_rpc_uses_restored_episode_counter_and_exposes_no_task_truth():
    facade = V5EnvFacade.__new__(V5EnvFacade)
    facade._meta = {"max_episode_steps": 10000}
    facade._env = SimpleNamespace(_elapsed_steps=np.array([9000]))
    assert facade.execution_budget() == {
        "version": "public-action-budget/1", "used_sim_steps": 9000,
        "max_sim_steps": 10000, "remaining_sim_steps": 1000}
    facade._env._elapsed_steps[:] = 123  # Same counter restoration as a physical branch.
    assert facade.execution_budget()["remaining_sim_steps"] == 9877


@pytest.mark.parametrize("native,truncated,expected", [
    (True, False, "verified"), (False, False, "task_not_completed"),
    (False, True, "task_not_completed")])
@pytest.mark.parametrize("tool", ["vla_task", "vla_subtask"])
def test_native_task_completion_and_measured_subgoal_are_distinct(native, truncated, expected, tool):
    receipt = {"tool": tool, "executed": True, "verification": "verified", "place_verified": True}
    task_completion_receipt(receipt, native_terminated=native, native_truncated=truncated)
    assert receipt["verification"] == expected
    assert receipt["task_completed"] is native
    assert receipt["place_verified"] is True
    assert receipt["subtask_verification"] == "verified"


def test_startup_or_binding_failure_is_not_claimed_as_an_executed_task_macro():
    receipt = {"tool": "vla_subtask", "executed": False, "verification": "unmeasured"}
    task_completion_receipt(receipt, native_terminated=False, native_truncated=False)
    assert "task_completed" not in receipt


def test_execution_error_retains_the_exception_type():
    receipt = {"tool": "vla_task", "executed": True, "verification": "execution_error"}
    task_completion_receipt(receipt, native_terminated=False, native_truncated=False)
    assert receipt["verification"] == "execution_error"


def test_full_task_failure_blocks_once_until_a_measured_scene_change():
    from dataclasses import replace

    obj = Entity("e1", "bowl", (0., 0., 1.), (-.02, -.02, .98), (.02, .02, 1.02))
    state = MeasuredRecovery.snapshot([obj], None, .08)
    recovery = MeasuredRecovery(measurement_progress_blocking=True)
    action = Candidate("vla_task")
    receipt = {"verification": "task_not_completed", "failure_reason": "task_not_completed"}
    recovery.observe(action, state, state, receipt)
    assert measurement_progress_blocked(action, recovery.status())
    assert recovery.status()["action_failures"][action.text()]["count"] == 1
    recovery.observe(Candidate("reperceive"), state, state, {"verification": "perception"})
    assert measurement_progress_blocked(action, recovery.status())
    moved = replace(obj, xyz=(.03, 0., 1.), lower=(.01, -.02, .98), upper=(.05, .02, 1.02))
    after = MeasuredRecovery.snapshot([moved], None, .08)
    recovery.observe(Candidate("reperceive"), state, after, {"verification": "perception"})
    assert not measurement_progress_blocked(action, recovery.status())


def test_subtask_incompletion_counts_even_when_a_partial_relation_passed():
    recovery = MeasuredRecovery(measurement_progress_blocking=True)
    action = Candidate("vla_subtask", "e1", "e2", "on")
    state = MeasuredRecovery.snapshot([], None, .08)
    receipt = {"verification": "task_not_completed", "failure_reason": "task_not_completed",
               "place_verified": True}
    for _ in range(2):
        recovery.observe(action, state, state, receipt)
    assert measurement_progress_blocked(action, recovery.status())


def test_cost_estimate_uses_past_receipts_and_does_not_learn_from_truncated_attempts():
    action = Candidate("vla_task")
    costs = action_costs([action], [], max_chunks=160)
    assert costs[action.text()]["estimated_sim_steps"] == 800
    receipts = [{"tool": "vla_task", "sim_steps_used": 500},
                {"tool": "vla_task", "sim_steps_used": 700},
                {"tool": "vla_task", "sim_steps_used": 1, "native_truncated": True}]
    costs = action_costs([action], receipts, max_chunks=160)
    assert costs[action.text()] == {"estimated_sim_steps": 600, "source": "episode_history_median"}
    assert action_costs([Candidate("finish")], [], max_chunks=160)["finish()"]["estimated_sim_steps"] == 0


def test_budget_context_keeps_action_cost_and_remaining_steps_visible():
    choices = [Candidate("vla_task"), Candidate("finish")]
    text = serialize("put bowl on plate", [], .08, None, [], choices=choices,
                     failure_counts=True, candidate_costs=action_costs(choices, [], max_chunks=160),
                     execution_budget={"remaining_sim_steps": 27, "max_sim_steps": 10000})
    assert "remaining_sim_steps=27" in text
    assert "estimated_sim_steps=800" in text
    assert "estimated_sim_steps=0" in text
    assert "src=public_action_counter" in text


@pytest.mark.parametrize("result,loop,expected", [
    ({"native_truncated": True}, True, "sim_step_budget_exhausted"),
    ({"native_truncated": False}, True, "decision_budget_exhausted"),
    ({}, False, "other_budget_end")])
def test_budget_end_reasons_are_mutually_exclusive(result, loop, expected):
    assert budget_end_kind(result, loop_exhausted=loop) == expected


def test_runtime_records_contact_and_script_steps_from_the_same_public_counter():
    from robots.libero.v5_runtime import V5Executor

    env = SimpleNamespace(terminated=False, truncated=False, used=100)
    env.execution_budget = lambda: {"used_sim_steps": env.used,
                                  "remaining_sim_steps": 10000-env.used, "max_sim_steps": 10000}
    executor = V5Executor(SimpleNamespace(primitives=SimpleNamespace(env=env)), SimpleNamespace())
    executor.skill_budget_v1 = executor.task_completion_receipts_v1 = True

    def execute(action, receipt, card):
        env.used += 18
        receipt.update(executed=True, verification="unmeasured")

    executor._execute = execute
    receipt = executor.execute(Candidate("vla_task"))
    assert receipt["sim_steps_used"] == 18
    assert receipt["remaining_sim_steps"] == 9882
    assert receipt["verification"] == "task_not_completed"
