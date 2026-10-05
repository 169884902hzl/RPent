# Copyright 2026 Zhilun Hu.
# SPDX-License-Identifier: Apache-2.0
"""Recover original oracle card steps from matched physical branch evidence."""

from __future__ import annotations

import hashlib
import json

from robots.libero.v5_cards import SKILLS, validate_card
from robots.libero.v5_state import Candidate

ORIGINAL_SUITES = {"libero_spatial", "libero_object", "libero_goal", "libero_10"}


def digest(value: dict) -> str:
    """Hash structured evidence without putting private truth in card steps."""
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def matched_branch(record: dict, labeled: dict) -> dict | None:
    """Match the same public request, candidate order, and selected action."""
    if labeled["step"] != record["decision"]:
        raise ValueError("physical label refers to another decision")
    request = labeled["request"]
    original = record["request"]
    if request["state"].encode() != original["context"].encode():
        raise ValueError("physical label has a different public state")
    criteria = request["questions"]["action"]["criteria"]
    if list(criteria.values()) != record["candidates"]:
        raise ValueError("physical label has a different candidate order")
    evidence = labeled["label_evidence"]
    if evidence.get("physical_branch_checked") is not True:
        return None
    branches = [b for b in evidence["branches"] if b["action"] == record["selected"]]
    if len(branches) != 1:
        return None
    return branches[0]


def predicate_effect(branch: dict) -> tuple[list[int], list[int]]:
    """Require aligned private predicates before calculating actual changes."""
    before, after = branch["before"], branch["after"]
    goals = before.get("goals")
    if not goals or after.get("goals") != goals:
        raise ValueError("physical branch predicate identity differs")
    previous, current = before["satisfied"], after["satisfied"]
    if len(previous) != len(goals) or len(current) != len(goals):
        raise ValueError("physical branch predicate counts differ")
    if any(type(value) is not bool for value in (*previous, *current)):
        raise ValueError("physical branch predicate values must be boolean")
    gains = [i for i, (old, new) in enumerate(zip(previous, current)) if not old and new]
    losses = [i for i, (old, new) in enumerate(zip(previous, current)) if old and not new]
    return gains, losses


def proven_step(record: dict, branch: dict) -> tuple[dict | None, dict]:
    """Never replace step-level evidence with the trajectory's final solved()."""
    action = Candidate.from_text(record["selected"])
    summary = {"decision": record["decision"], "action": action.text(),
               "branch_sha256": digest(branch), "reason": "unproven_action"}
    actual, tested = record["receipt"], branch["receipt"]
    if actual.get("error") or actual.get("executed") is not True:
        return None, {**summary, "reason": "rollout_action_not_executed_without_error"}
    if branch.get("accepted") is not True or tested.get("error") or tested.get("executed") is not True:
        return None, {**summary, "reason": "physical_branch_not_accepted_without_error"}
    gains, losses = predicate_effect(branch)
    summary.update(predicate_gains=gains, predicate_losses=losses)
    if losses or branch["before"].get("done") is True:
        return None, {**summary, "reason": "goal_destroyed_or_already_done"}
    if action.tool in ("grasp", "regrasp_restage"):
        if gains:
            # A full-instruction contact policy can also place the object.
            # That macro is not evidence for an invented explicit place step.
            return None, {**summary, "reason": "goal_progress_inside_grasp_macro"}
        if actual.get("grasp_verified") is not True or tested.get("grasp_verified") is not True:
            return None, {**summary, "reason": "grasp_has_no_positive_measured_branch"}
    elif action.tool in ("place", "adjust_place", "articulate"):
        if not gains:
            return None, {**summary, "reason": "no_new_predicate_evidence"}
        allowed = {action.mode}
        if action.tool == "articulate":
            allowed |= {action.mode.replace("turn_", "turn") if action.mode else None}
        if any(branch["after"]["goals"][i][0] not in allowed for i in gains):
            return None, {**summary, "reason": "predicate_relation_does_not_match_action"}
    else:
        return None, {**summary, "reason": "not_a_physical_card_step"}
    skill = "grasp" if action.tool == "regrasp_restage" else "place" if action.tool == "adjust_place" else action.tool
    entities = {e["id"]: e for e in record["measurements"]}
    step = {"skill": skill}
    for field in ("object", "target"):
        identifier = getattr(action, field)
        if identifier is not None:
            measured = entities.get(identifier)
            if measured is None or measured.get("src", "perception") != "perception":
                return None, {**summary, "reason": "no_public_perception_category_binding"}
            step[field + "_category"] = measured["name"]
    if action.mode:
        step["mode"] = "above_10cm" if action.tool == "regrasp_restage" else action.mode
    return step, {**summary, "reason": "matched_positive_physical_branch", "step": step}


def reconstruct_card(card: dict, records: list[dict], labels: dict[int, dict]) -> tuple[dict | None, dict]:
    """Return only an original plan with positive evidence for every goal."""
    validate_card(card)
    identity = card["source_episode"]
    if card["origin"] != "original_oracle" or identity["suite"] not in ORIGINAL_SUITES or not 10 <= identity["seed"] < 40:
        raise ValueError("card source is outside original training tasks/init10..39")
    audit = {"source_episode": identity, "source_choices_sha256": card["source_choices_sha256"],
             "legacy_steps": card["steps"], "decisions": [], "status": "needs_original_recollection"}
    if not records or records[-1].get("official_success") is not True:
        audit["reason"] = "source_trajectory_has_no_official_success"
        return None, audit
    # Existing non-finish card steps came from a hashed original trace and are
    # retained only when their own receipt is positive.  A later final
    # ``official_success`` never upgrades a failed/unverified step.
    steps, proofs, covered, goal_count = [], [], set(), None
    for legacy in card["steps"]:
        if legacy.get("skill") == "finish":
            continue
        matched = []
        for record in records:
            action = Candidate.from_text(record["selected"])
            if action.tool != legacy.get("skill"):
                continue
            entities = {e["id"]: e for e in record.get("measurements", [])}
            if legacy.get("object_category") and entities.get(action.object, {}).get("name") != legacy["object_category"]:
                continue
            if legacy.get("target_category") and entities.get(action.target, {}).get("name") != legacy["target_category"]:
                continue
            receipt = record.get("receipt", {})
            if (receipt.get("executed") is True and not receipt.get("error")
                    and receipt.get("verification") not in ("failed", "execution_error")
                    and all(receipt.get(key) is not False for key in
                            ("grasp_verified", "place_verified", "articulate_verified"))):
                matched.append(record)
        if len(matched) == 1:
            steps.append(legacy)
            proofs.append({"action": matched[0]["selected"], "decision": matched[0]["decision"],
                           "reason": "hashed_legacy_positive_receipt"})
        else:
            audit["decisions"].append({"action": legacy, "reason":
                                      "legacy_step_has_no_unique_positive_receipt"})
    for record in records:
        action = Candidate.from_text(record["selected"])
        if action.tool not in SKILLS | {"adjust_place", "regrasp_restage"} or action.tool in ("finish", "release", "retreat"):
            continue
        labeled = labels.get(record["decision"])
        if labeled is None:
            audit["decisions"].append({"decision": record["decision"], "action": action.text(),
                                      "reason": "no_matching_physical_label"})
            continue
        branch = matched_branch(record, labeled)
        if branch is None:
            audit["decisions"].append({"decision": record["decision"], "action": action.text(),
                                      "reason": "selected_branch_missing_or_ambiguous"})
            continue
        count = len(branch["before"]["goals"])
        if goal_count is not None and count != goal_count:
            raise ValueError("source trace changed its instruction goal count")
        goal_count = count
        step, proof = proven_step(record, branch)
        audit["decisions"].append(proof)
        if step is not None:
            covered.update(proof["predicate_gains"])
            # Do not duplicate a grasp already retained from the same hashed
            # trace.  A physically evidenced place/articulate still gets
            # appended; identical repeated actions are represented once in a
            # category plan because card steps have no recovery coordinates.
            if step not in steps:
                steps.append(step)
                proofs.append({k: v for k, v in proof.items() if k != "step"})
    audit.update(proven_steps=steps, covered_goal_indices=sorted(covered), goal_count=goal_count)
    if not goal_count or covered != set(range(goal_count)):
        audit["reason"] = "not_every_goal_has_positive_selected_action_evidence"
        return None, audit
    rebuilt = {**card, "steps": [*steps, {"skill": "finish"}],
               "reconstruction": {"version": "original-branch-card/1-dev", "judge": "physics_branch",
                                  "proofs": proofs, "private_truth_in_steps": False}}
    validate_card(rebuilt)
    audit.update(status="physically_evidenced_plan", reason="all_goals_have_positive_selected_action_evidence")
    return rebuilt, audit
