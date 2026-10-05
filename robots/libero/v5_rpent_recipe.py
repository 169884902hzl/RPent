"""Evaluation-only execution of hash-pinned original RPent recipe commands."""

import hashlib
import json
from pathlib import Path

from robots.libero.v5_state import Candidate, grasp_verified


class OriginalRecipe:
    """Keep a failed primitive pending while the planner chooses recovery."""

    def __init__(self, index: Path):
        manifest = json.loads(index.read_text())
        if manifest.get("evaluation_only") is not True or manifest.get("training_allowed") is not False:
            raise ValueError("original recipes are evaluation-only")
        files = [f for f in manifest["files"] if f["name"].endswith("_recipe.jsonl")]
        if len(files) != 1:
            raise ValueError("register exactly one matched original recipe")
        record = files[0]
        payload = Path(record["path"]).read_bytes()
        self.sha256 = hashlib.sha256(payload).hexdigest()
        if self.sha256 != record["sha256"]:
            raise ValueError("original recipe changed")
        self.commands = [json.loads(line) for line in payload.decode().splitlines() if line.strip()]
        if not self.commands or any(not isinstance(c, dict) or not isinstance(c.get("action"), str)
                                    for c in self.commands):
            raise ValueError("invalid original primitive commands")
        self.index = 0
        self.last_execution = None

    def view(self):
        """Reuse the existing card line; numerical recipe parameters stay out."""
        if self.index >= len(self.commands):
            return None
        command = self.commands[self.index]
        next_action = command["action"]
        if isinstance(command.get("prompt"), str):
            next_action += " " + command["prompt"]
        return {"step": self.index + 1, "total": len(self.commands), "next": next_action}

    def execute(self, executor):
        """Pass the recorded parameters unchanged to the original tool API."""
        if self.index >= len(self.commands):
            raise ValueError("original recipe is exhausted")
        command = self.commands[self.index]
        tool = command["action"]
        receipt = {"tool": "rpent_step", "primitive": tool, "executed": False,
                   "verification": "unverified", "recipe_step": self.index + 1,
                   "mode": str(self.index + 1),
                   "recipe_total": len(self.commands)}
        self.last_execution = {"step": self.index + 1, "command": dict(command),
                               "recipe_sha256": self.sha256}
        if tool == "finish" and not executor.p.env.terminated:
            receipt.update(verification="environment_incomplete", message="环境报告任务未完成")
            executor.receipts.append(receipt)
            return receipt
        before = dict(executor.scene.entities)
        try:
            response = executor.toolkit.execute_tool(tool, {k:v for k,v in command.items() if k != "action"}).result
            # Stateful RPent tools return a captured environment envelope.
            # The primitive outcome lives in log.result; the envelope also
            # contains image bytes and simulator state, neither a receipt.
            result = response["log"]["result"] if "log" in response else response
            self.last_execution["result"] = result
            if response.get("error") or result.get("error"):
                receipt.update(executed=True, verification="execution_error",
                               error=f"original RPent {tool} execution failed")
                self.last_execution["error"] = str(response.get("error") or result["error"])
                self.last_execution["advanced"] = False
                executor.receipts.append(receipt)
                return receipt
            executor.capture(sync_robot=True)
            executor.scene.refresh(sorted(executor.scene.vocabulary))
            # State held remains a measured fact, independent of recipe truth.
            lifted = [e for eid,e in before.items() if grasp_verified(
                e, executor.scene.entities.get(eid), executor.p._last_obs_gripper)]
            if tool in ("pi0_pick", "pi0_doubled") and len(lifted) == 1:
                after = executor.scene.entities[lifted[0].id]
                executor.held = after.id
                import numpy as np
                executor.held_offset = executor.p._last_obs_eef_pos - np.asarray([
                    (after.lower[0]+after.upper[0])/2,
                    (after.lower[1]+after.upper[1])/2, after.lower[2]])
            elif tool == "release" or tool == "set_gripper" and command.get("gripper", 0) < 0:
                executor.held = executor.held_offset = None
            # pi0_doubled.success is the whole task's native termination,
            # not verification of an intermediate articulation. Keep it
            # unverified and allow the next recorded primitive to execute.
            failed = tool == "pi0_pick" and result.get("success") is False
            # Preserve move_to's raw result; do not throw away recoverable misses.
            if "final_dist_m" in result and float(result["final_dist_m"]) > .08:
                failed = True
            receipt.update(executed=True, verification="failed" if failed else "unverified")
            if failed:
                receipt["failure_reason"] = "original_primitive_not_successful"
            else:
                self.index += 1
        except Exception as error:
            receipt.update(verification="execution_error", error=f"original RPent {tool} execution failed")
            self.last_execution["error"] = f"{type(error).__name__}: {error}"
        self.last_execution["advanced"] = self.index == receipt["recipe_step"]
        executor.receipts.append(receipt)
        return receipt


def add_recipe_choice(choices, recipe, receipts, rng, cooldown=False):
    """Keep the same candidate cap and cool down exceptions before retries."""
    if recipe.view() is None:
        return choices
    from robots.libero.v5_state import execution_error_blocked
    action = Candidate("rpent_step", mode=str(recipe.index + 1))
    if cooldown and execution_error_blocked(action, receipts):
        return choices
    choices = list(choices)
    if len(choices) == 24:
        position = next(i for i in reversed(range(len(choices)))
                        if choices[i].tool in ("grasp", "place", "articulate"))
        choices.pop(position)
    choices.append(action)
    rng.shuffle(choices)
    return choices
