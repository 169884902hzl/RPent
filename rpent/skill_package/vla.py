"""Bounded fallback policy calls with public progress and explicit provenance."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from time import perf_counter

import numpy as np


@dataclass(frozen=True)
class VLABudget:
    blocks: int = 24
    no_progress_blocks: int | None = 3
    controls_per_check: int | None = 1
    minimum_progress_m: float = .005
    max_controls: int | None = None


def whole_instruction_budget(budget: VLABudget) -> VLABudget:
    """Use the existing original-development envelope for a complete task.

    Original90/own-layout development already pins 104 five-control blocks
    and 520 controls. Its original-initial-state selfcheck closed 106/110 on
    2026-10-22. Subtasks retain their budget. An explicit total-control cap
    remains authoritative, as do nondefault block profiles. PRO/D2 outcomes
    do not select this limit.
    """
    if budget.max_controls is not None or budget.blocks != VLABudget().blocks:
        return budget
    return replace(budget, blocks=104, max_controls=520)


class DevelopmentHistory:
    """Only explicitly allowlisted original-development logs may contribute."""

    def __init__(self, manifest_path: str | Path | None = None):
        self.rows: list[dict] = []
        self.sources: list[dict] = []
        self.manifest_sha256: str | None = None
        if manifest_path is None:
            return
        raw_manifest = Path(manifest_path).read_bytes()
        self.manifest_sha256 = hashlib.sha256(raw_manifest).hexdigest()
        manifest = json.loads(raw_manifest)
        for source in manifest["sources"]:
            if source["split"] != "development" or source["domain"] not in {"libero_original40", "libero_original90"}:
                raise ValueError("VLA history requires original development data")
            if source.get("confirmation_states_present") is not False:
                raise ValueError("confirmation states cannot contribute to VLA history")
            path = Path(source["path"])
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            if digest != source["sha256"]:
                raise ValueError("development history source hash mismatch")
            rows = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
            if any(r.get("split") != "development" or r.get("confirmed_state") is not False
                   or not isinstance(r.get("success"), bool) for r in rows):
                raise ValueError("history rows need explicit development/label provenance")
            self.rows.extend(rows)
            self.sources.append({"path": str(path), "sha256": digest})

    def estimate(self, action: str, category: str, context: str = "measured") -> dict:
        rows = [r for r in self.rows if (r["action"], r["category"], r["context"]) == (action, category, context)]
        n = len(rows)
        return {"success_rate": sum(r["success"] for r in rows)/n if n else None, "n": n,
                "expected_steps": int(round(np.mean([r["steps_used"] for r in rows]))) if n else None,
                "sources": self.sources}


def run_fallback(*, prompt: str, prepare, predict, step, observe, native_done,
                 handoff, native_stopped=None, budget: VLABudget = VLABudget()) -> dict:
    """Run a code-rendered subtask, checking public evidence within chunks.

    observe() returns only public data: progress_vector_m, completed,
    outside_region and evidence. The caller owns template construction; this
    low-level executor is never exposed as a free-text model tool.
    """
    started = perf_counter()
    timing = dict.fromkeys(('preparation', 'inference', 'public_observation', 'control', 'handoff'), 0.)
    def timed(category, function, *args):
        before = perf_counter()
        try:
            return function(*args)
        finally:
            timing[category] += perf_counter()-before
    preparation = timed('preparation', prepare)
    if not preparation["success"]:
        return {"outcome": "failure", "stop_reason": "preparation_not_reached",
                "steps_used": preparation.get("steps_used", 0), "blocks_used": 0,
                "preparation": preparation, "checks": [], "trace": [], "timing_s": timing}
    initial = timed('public_observation', observe)
    reference = np.asarray(initial["progress_vector_m"], float)
    no_progress, count = 0, 0
    checks, trace = [initial], []
    reason, outcome = "block_budget", "failure"
    stopped = native_stopped or native_done
    for block in range(budget.blocks):
        if native_done():
            reason, outcome = "native_success", "success"
            break
        if stopped():
            reason, outcome = "environment_budget", "interrupted"
            break
        actions = np.asarray(timed('inference', predict, prompt))
        if actions.ndim != 2 or actions.shape[1] != 7 or not len(actions) or not np.isfinite(actions).all():
            raise ValueError("VLA must return a finite nonempty Nx7 OSC action block")
        count += 1
        stop = False
        for index, action in enumerate(actions):
            if budget.max_controls is not None and len(trace) >= budget.max_controls:
                reason, outcome, stop = "control_budget", "failure", True
                break
            if native_done():
                reason, outcome, stop = "native_success", "success", True
                break
            if stopped():
                reason, outcome, stop = "environment_budget", "interrupted", True
                break
            before, after = timed('control', step, action)
            trace.append({"block": block, "control": index, "action": action.tolist(), "before": before, "after": after})
            check_due = (index == len(actions)-1 or (budget.controls_per_check is not None
                and (index+1) % budget.controls_per_check == 0))
            if not check_due:
                continue
            measurement = timed('public_observation', observe)
            checks.append(measurement)
            if measurement["completed"] or native_done():
                reason, outcome, stop = "measured_success", "success", True
            elif measurement["outside_region"]:
                reason, outcome, stop = "left_target_region", "failure", True
            if stop:
                break
        if stop:
            break
        current = np.asarray(checks[-1]["progress_vector_m"], float)
        # Missing observations cannot manufacture progress or success.
        progressed = current.shape == reference.shape and np.isfinite(current).all() and np.linalg.norm(current-reference) >= budget.minimum_progress_m
        no_progress = 0 if progressed else no_progress+1
        if progressed:
            reference = current
        if budget.no_progress_blocks is not None and no_progress >= budget.no_progress_blocks:
            reason = "no_progress_blocks"
            break
    handoff_result = timed('handoff', handoff, trace) if not stopped() else {"native_stop": True}
    skill_stop_reason = reason
    if handoff_result.get("executed") is False and handoff_result.get("reason") == "braking_screen_rejected":
        reason, outcome = "handoff_braking_screen_rejected", "interrupted"
    elif handoff_result.get('completed') is False:
        reason, outcome = 'handoff_'+handoff_result['reason'], 'interrupted'
    if native_done():
        reason, outcome = 'native_success', 'success'
    timing['other'] = max(0., perf_counter()-started-sum(timing.values()))
    return {"outcome": outcome, "stop_reason": reason,
            "skill_stop_reason": skill_stop_reason,
            "steps_used": len(trace)+preparation.get("steps_used", 0)+handoff_result.get("steps_used", 0),
            "blocks_used": count, "no_progress_blocks": no_progress, "checks": checks,
            "preparation": preparation, "handoff": handoff_result, "trace": trace,
            "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
            "timing_s": timing, "budget": asdict(budget)}
