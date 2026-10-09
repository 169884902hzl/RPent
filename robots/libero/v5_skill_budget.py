"""Public control-step accounting and prospective skill-cost estimates."""

from __future__ import annotations

import math
import statistics

VERSION = "public-skill-budget/1"


def action_costs(choices, receipts, *, max_chunks: int, policy_chunk_steps: int = 5):
    """Use only past receipts; cold-start estimates use configured skill caps.

    Estimates are planning hints, not success scores or reserved execution
    budgets. The server's action counter remains the sole budget owner.
    """
    contact = max_chunks * policy_chunk_steps
    servo = 9 * 80  # V5 move(): at most eight intermediate moves and the endpoint.
    estimates = {
        "vla_task": contact, "vla_subtask": contact + 2 * servo + 20,
        "grasp": max(max_chunks, 160) * policy_chunk_steps + 3 * servo,
        "regrasp_restage": contact + 3 * servo,
        "place": contact + 3 * servo + 20, "adjust_place": 2 * contact + 6 * servo + 20,
        "articulate": contact + servo, "release": 20,
        "retreat": 3 * servo, "clear_view": servo, "wrist_scan": 2 * servo,
        "finish": 0, "ask_help": 0, "reperceive": 0,
    }
    output = {}
    for action in choices:
        history = [r["sim_steps_used"] for r in receipts
                   if r.get("tool") == action.tool and r.get("mode") == action.mode
                   and isinstance(r.get("sim_steps_used"), int)
                   and r["sim_steps_used"] > 0 and not r.get("native_truncated")]
        if history:
            value = math.ceil(statistics.median(history[-16:]))
            source = "episode_history_median"
        else:
            value = estimates.get(action.tool)
            source = "configured_skill_caps" if value is not None else "unknown"
        output[action.text()] = {"estimated_sim_steps": value, "source": source}
    return output


def budget_end_kind(result, *, loop_exhausted: bool) -> str:
    """Keep native truncation distinct from a decision-loop limit."""
    if result.get("native_truncated"):
        return "sim_step_budget_exhausted"
    if loop_exhausted:
        return "decision_budget_exhausted"
    return "other_budget_end"


def summarize_skill_steps(receipts):
    totals = {}
    for receipt in receipts:
        if "sim_steps_used" not in receipt:
            continue
        tool = receipt["tool"]
        item = totals.setdefault(tool, {"attempts": 0, "sim_steps": 0})
        item["attempts"] += 1
        item["sim_steps"] += receipt["sim_steps_used"]
    return totals


def task_completion_receipt(receipt, *, native_terminated: bool, native_truncated: bool):
    """Task macros must account for an executed, incomplete native task."""
    if receipt.get("tool") not in ("vla_task", "vla_subtask") or not receipt.get("executed"):
        return
    receipt.update(native_terminated=native_terminated, native_truncated=native_truncated)
    if receipt.get("verification") == "execution_error":
        return
    receipt["subtask_verification"] = receipt.get("verification")
    receipt["task_completion_version"] = "native-task-completion/1"
    if native_terminated:
        receipt.update(verification="verified", task_completed=True)
    else:
        receipt.update(verification="task_not_completed", task_completed=False,
                       failure_reason="task_not_completed")
