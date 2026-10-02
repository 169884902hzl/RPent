# Copyright 2026 Zhilun Hu.
# SPDX-License-Identifier: Apache-2.0
"""Collect original-task physics branches without changing visible requests."""

from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import random
from pathlib import Path

from robots.libero.v5_progress import (
    PROGRESS_CHOICES,
    PROGRESS_QUESTION,
    measured_progress,
)
from robots.libero.v5_state import Candidate, entity_record, serialize
from robots.libero.v5_termination import V2_CATEGORIES


def file_sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def wire_request(request):
    return {"state": request["context"], "questions": {"action": {
        "type": "choice", "instructions": request["instruction"],
        "criteria": {f"C{i}": text for i, text in enumerate(request["options"])},
    }}}


def accepted_branch(action, receipt, before, after, *, required_objects=None):
    """Judge only the tested action; untested candidates remain unknown."""
    if action.tool == "card_next" and receipt.get("card_action"):
        action = Candidate.from_text(receipt["card_action"])
    if action.tool == "finish":
        return bool(before["done"])
    if before["done"]:
        return False
    if action.tool == "ask_help":
        return None
    if receipt.get("error"):
        return False
    if after["done"] and action.tool in ("grasp", "place", "adjust_place", "articulate"):
        # Some original goals become true before the skill's lift verification.
        # A separately evaluated completed goal still accepts that branch;
        # action_outcome keeps the failed/unverified skill receipt unchanged.
        return True
    if action.tool == "grasp":
        if required_objects is None or action.object not in required_objects:
            return None
        return bool(receipt.get("grasp_verified"))
    if action.tool in ("place", "adjust_place"):
        # Private predicates judge executed training branches. Visual receipts
        # remain unchanged: an in-container object often fails the above-rim
        # visual placement check even though its physical subgoal is true.
        return any(
            new and not old for old, new in zip(before["satisfied"], after["satisfied"])
        ) and not any(old and not new for old, new in zip(before["satisfied"], after["satisfied"]))
    if action.tool == "articulate":
        pending_storage = {goal[2] for goal, complete in zip(before.get("goals", []), before["satisfied"])
                           if not complete and goal[0] == "in" and len(goal) == 3}
        for region in pending_storage:
            was_open = before.get("storage_open", {}).get(region)
            now_open = after.get("storage_open", {}).get(region)
            if was_open is False and now_open is True:
                return True
            if was_open is True and now_open is False:
                return False
        return any(new and not old for old, new in zip(before["satisfied"], after["satisfied"]))
    return None


class OriginalCollection:
    """Write live training states and judge-only truth into explicit files."""

    def __init__(self, config, output, args):
        self.output = Path(output)
        self.args = args
        self.config = config
        schema = Path(config["shared_schema"])
        if file_sha(schema) != config["shared_schema_sha256"]:
            raise ValueError("shared schema changed after collection registration")
        spec = importlib.util.spec_from_file_location("libero_collection_schema", schema)
        self.shared = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.shared)
        self.split = config.get("split", "train")
        if self.split == "train":
            allowed = range(10, 40)
        elif self.split == "validation":
            allowed = config["validation_init_indices"]
            if set(allowed) - set(range(5)):
                raise ValueError("validation only uses the registered original development init0-4")
        else:
            raise ValueError("unsupported collection split")
        if args.seed not in allowed:
            raise ValueError("init index is outside the registered collection split")
        self.rng = random.Random(910000 + args.task * 100 + args.seed)
        self.counts = {"next_skill": 0, "auxiliary": 0, "premature_finish_negative": 0,
                       "zero_signal": 0, "over_token": 0, "branches": 0}
        self.files = {name: self.output / f"{name}.jsonl" for name in
                      ("train", "auxiliary", "premature_finish_negative", "zero_signal", "branches")}
        self.handles = {}
        root = Path(__file__).resolve().parents[2]
        names = ["harness_v5_eval.py", "robots/libero/v5_state.py", "robots/libero/v5_runtime.py",
                 "robots/libero/v5_oracle_policy.py", "robots/libero/v5_oracle_server.py",
                 "robots/libero/v5_collection.py", "robots/libero/v5_branch_state.py", "robots/libero/v5_progress.py",
                 "robots/libero/v5_env_client.py", "robots/libero/env_client.py",
                 "robots/libero/robot_spec.py", "robots/libero/tools.py", "robots/libero/v5_env_server.py"]
        names += ["robots/libero/v5_termination.py", "robots/libero/v5_cards.py",
                  "robots/libero/v5_fixture_parts.py", "robots/libero/v5_verification.py"]
        self.variant = None
        if getattr(args, "counterfactual_spec", None):
            self.variant = json.loads(Path(args.counterfactual_spec).read_text())
            names.extend(("robots/libero/v5_env_server.py", "robots/libero/v5_counterfactual.py"))
        self.source = {name: file_sha(root / name) for name in names}
        self.source["shared_schema"] = file_sha(schema)
        self.last_post = None
        self.last_status = None

    def write(self, bucket, row):
        if not self.handles:
            self.handles = {name: path.open("x") for name, path in self.files.items()}
        self.handles[bucket].write(json.dumps(row, ensure_ascii=False, allow_nan=False) + "\n")
        self.handles[bucket].flush()

    def admit(self, bucket, row, tokenizer, prompt_module):
        try:
            _, prepared = self.shared.prepare_example(row, tokenizer, prompt_module, limit=3072)
        except ValueError as error:
            if "token" not in str(error).lower() and "3072" not in str(error):
                raise
            self.counts["over_token"] += 1
            self.write("zero_signal", {"reason": "over_token", "row": row})
            return False
        row["prompt_tokens"] = len(prepared.full_ids[0])
        if row["prompt_tokens"] > 3072:
            raise AssertionError("renderer returned an over-limit prompt")
        row["runtime_source_sha256"] = self.source["robots/libero/v5_state.py"]
        row["source_hashes"] = self.source
        row["source_key"] = {"request_hash": self.shared.digest(row["request"]),
                             "scene": row["scene_id"], "stage": row["stage"], "step": row["step"]}
        self.write(bucket, row)
        return True

    def before_action(self, args, step, request, action, choices, scene, executor,
                      toolkit, rpc, policy, tokenizer, prompt_module, *, card=None):
        self.tokenizer, self.prompt_module = tokenizer, prompt_module
        before = rpc.call("oracle.status", timeout_s=120)
        before["official_solved"] = bool(toolkit.solved())
        before["done"] = bool(before["done"] or before["official_solved"])
        physical = rpc.call("oracle.snapshot", timeout_s=120)
        public = {name: copy.deepcopy(getattr(scene, name)) for name in
                  ("entities", "vocabulary", "last_measurement_s", "_scores", "_ids",
                   "support_z", "fixture_measurement_evidence", "rejected_fixture_measurements")}
        execution = {name: copy.deepcopy(getattr(executor, name)) for name in
                     ("held", "held_offset", "receipts", "target_cache", "last_verification_measurements", "motion_evidence")}
        cached_observation = copy.deepcopy(executor.p._last_obs)
        flags = (executor.p.env.terminated, executor.p.env.truncated, toolkit._solved)
        snapshot_sha = hashlib.sha256(json.dumps(physical, sort_keys=True, default=lambda a: a.tolist()).encode()).hexdigest()
        codes = [f"C{i}" for i in range(len(choices))]
        selected = [choices.index(action)]
        terminal = next(i for i, c in enumerate(choices) if c.tool == ("ask_help" if before["done"] else "finish"))
        if terminal not in selected:
            selected.append(terminal)
        alternatives = [i for i, c in enumerate(choices) if i not in selected and c.tool in ("grasp", "place", "articulate", "adjust_place", "card_next")]
        if alternatives:
            selected.append(self.rng.choice(alternatives))
        branches, good, evaluated = [], [], []
        required_objects = {
            policy._bindings.get(goal[1])
            for goal, satisfied in zip(before["goals"], before["satisfied"])
            if not satisfied and goal[0] in ("in", "on")
        } - {None}
        for index in selected:
            candidate = choices[index]
            try:
                receipt = executor.execute(candidate, card=card)
                after = rpc.call("oracle.status", timeout_s=120)
                after["done"] = bool(after["done"] or toolkit.solved())
                accepted = accepted_branch(candidate, receipt, before, after,
                                           required_objects=required_objects)
                branch = {"code": codes[index], "action": candidate.text(), "receipt": receipt,
                          "accepted": accepted, "before": before, "after": after,
                          "snapshot_sha256": snapshot_sha,
                          "verification_measurements": copy.deepcopy(executor.last_verification_measurements),
                          "post_measurements": [entity_record(e) for e in scene.entities.values()]}
            finally:
                rpc.call("oracle.restore", args=[physical], timeout_s=120)
                executor.p.env.terminated, executor.p.env.truncated, toolkit._solved = flags
                # Physics is checked by oracle.restore. The request used the
                # cached measured observation; restoring physics must also
                # restore that cache instead of replacing it with a fresh read.
                executor.p.env.last_obs = copy.deepcopy(cached_observation)
                executor.p.set_obs(copy.deepcopy(cached_observation))
                for name, value in public.items():
                    setattr(scene, name, copy.deepcopy(value))
                for name, value in execution.items():
                    setattr(executor, name, copy.deepcopy(value))
                # The RPC validates exact restored physics; this validates the public side.
                restored = serialize(args.instruction_override, list(scene.entities.values()),
                                     executor.p._last_obs_gripper, executor.held, executor.receipts,
                                     view_axes=scene.view_axes, choices=choices, card=card,
                                     failure_counts=getattr(args, "candidate_failure_counts_v1", False))
                if restored.encode() != request["context"].encode():
                    self.write("zero_signal", {"reason": "public_restore_mismatch",
                                               "expected": request["context"], "actual": restored})
                    raise RuntimeError("restored public state differs from the branch request")
            self.counts["branches"] += 1
            self.write("branches", {"step": step, **branch})
            branches.append(branch)
            if accepted is not None:
                evaluated.append(codes[index])
                if accepted:
                    good.append(codes[index])
        scene_id = f"original/{args.suite}/t{args.task}/init{args.seed}"
        if self.variant is not None:
            scene_id += "/cf_" + self.variant["variant_bddl_sha256"][:12]
        attempt = self.config.get("collection_attempt")
        if attempt:
            scene_id += "/replay_" + attempt
        row = {"schema_version": "entities-plan-receipt/3.1", "domain": "libero", "split": self.split,
               "bucket": "expert", "seed": args.seed, "suite": args.suite, "task_id": args.task,
               "init_state_index": args.seed, "init_state_sha256": args.init_state_sha256,
               "scene_id": scene_id, "episode_id": scene_id, "task_family": args.suite,
               "stage": "skill", "step": step, "request": wire_request(request),
               "acceptable_actions": good, "evaluated_actions": evaluated,
               "unknown_actions": [c for c in codes if c not in evaluated],
               "source": self.source, "label_evidence": {"physical_branch_checked": True,
               "branches": branches, "original_expert_selected": choices.index(action)},
               "instruction_sha256": hashlib.sha256(args.instruction_override.encode()).hexdigest(),
               "wording_bank_sha256": self.config["wording_bank_sha256"]}
        row = self.shared.next_skill(row)
        if attempt:
            row["collection_attempt"] = attempt
            row["replay_of"] = self.config["replay_of"]
        if self.variant is not None:
            row["bucket"] = "counterfactual"
            row["counterfactual_spec_sha256"] = file_sha(args.counterfactual_spec)
        if good:
            if self.admit("train", row, tokenizer, prompt_module):
                self.counts["next_skill"] += 1
        else:
            self.counts["zero_signal"] += 1
            self.write("zero_signal", {"reason": "no_physically_acceptable_tested_candidate", "row": row})
        finish = next(c for c, a in zip(codes, choices) if a.tool == "finish")
        if finish in evaluated and finish not in good:
            self.write("premature_finish_negative", {"source_request_sha256": self.shared.digest(row["request"]),
                                                      "finish_code": finish, "row": row})
            self.counts["premature_finish_negative"] += 1
        self.add_aux(row, "goal_done", "Have all requirements of the instruction been achieved?",
                     {"yes": "All instruction requirements are complete.", "no": "The instruction is not yet complete."},
                     "yes" if before["official_solved"] else "no",
                     {"kind": "measured_goal", "official_solved_before": before["official_solved"]})
        values = before["satisfied"]
        completed = sum(bool(x) for x in values)
        progress, evidence = measured_progress(completed, len(values))
        self.add_aux(row, "progress", PROGRESS_QUESTION, PROGRESS_CHOICES, progress, evidence)
        visible = {e.id for e in scene.entities.values() if e.visible}
        for goal, satisfied in zip(before["goals"], values):
            ids = [policy._bindings.get(symbol) for symbol in goal[1:]]
            if goal[0] not in ("in", "on") or not all(eid in visible for eid in ids):
                continue
            question = f"Is {ids[0]} {goal[0]} {ids[1]} now?"
            self.add_aux(row, "subgoal_done", question,
                         {"yes": "The specified measured relationship is complete.",
                          "no": "The specified measured relationship is not complete."},
                         "yes" if satisfied else "no",
                         {"kind": "measured_subgoal", "predicate": goal, "satisfied": bool(satisfied)})
        return row

    def add_aux(self, row, kind, question, choices, answer, evidence):
        aux = self.shared.auxiliary(row, kind, question, choices, {answer: 1.0}, evidence)
        aux.update(suite=row["suite"], task_id=row["task_id"], init_state_index=row["init_state_index"],
                   init_state_sha256=row["init_state_sha256"])
        if self.admit("auxiliary", aux, self.tokenizer, self.prompt_module):
            self.counts["auxiliary"] += 1

    def after_action(self, row, record, scene, executor, rpc):
        post = copy.deepcopy(row)
        post["stage"] = "receipt"
        post["request"]["state"] = serialize(self.args.instruction_override, list(scene.entities.values()),
                                             executor.p._last_obs_gripper, executor.held, executor.receipts,
                                             view_axes=scene.view_axes,
                                             card=record.get("memory_card"),
                                             choices=[Candidate.from_text(text) for text in record['candidates']],
                                             failure_counts=getattr(self.args, "candidate_failure_counts_v1", False))
        receipt = record["receipt"]
        outcome = "failed" if receipt.get("verification") in ("failed", "execution_error") else (
            "verified" if receipt.get("verification") == "verified" else "unverified")
        self.add_aux(post, "action_outcome", "What evidence supports the outcome of the most recent action?",
                     {"verified": "The action outcome is verified.", "failed": "The action failed verification.",
                      "unverified": "The action was executed but its outcome is unverified."}, outcome,
                     {"kind": "evaluated_physical_branch", "executed_receipt": receipt})
        self.last_post = post
        self.last_status = rpc.call("oracle.status", timeout_s=120)

    def finish(self, result):
        terminal_choices = (
            "completion_judgment", "no_legal_candidate", "perception_missing_object",
            "skill_execution_failure", "over_token", "budget_exhausted", "startup_error"
        )
        if getattr(self.args, "termination_accounting_v2", False):
            terminal_choices += V2_CATEGORIES
        if self.last_post is not None and result.get("termination_category") in terminal_choices:
            choices = {c: c.replace("_", " ") for c in terminal_choices}
            self.add_aux(self.last_post, "failure_reason", "What is the recorded terminal cause of this episode?",
                         choices, result["termination_category"],
                         {"kind": "programmatic_receipt_reason", "termination_category": result["termination_category"]})
        for handle in self.handles.values():
            handle.close()
        for path in self.files.values():
            if not path.exists():
                path.touch(exist_ok=False)
        manifest = {"purpose": "original training collector partial shard, not admitted SFT data",
                    "split": self.split, "progress_bands": PROGRESS_CHOICES,
                    "source_hashes": self.source, "counts": self.counts, "episode_result": result,
                    "files": {name: {"path": str(p), "sha256": file_sha(p),
                                      "rows": sum(1 for _ in p.open())} for name, p in self.files.items()},
                    "exclusions": self.config["exclusions"], "counterfactual_rules": self.config["counterfactual_rules"],
                    "counterfactual_targets_generated": 0,
                    "remaining": "Counterfactual goals, failure injections and memory cards are pending; this first shard contains original goals, visible-bound subgoals and premature finish branches. Unsupported terminal causes do not receive invented auxiliary labels."}
        if self.config.get("collection_attempt"):
            manifest["collection_attempt"] = self.config["collection_attempt"]
            manifest["replay_of"] = self.config["replay_of"]
            manifest["new_independent_init_state"] = False
        if self.variant is not None:
            manifest["counterfactual_targets_generated"] = 1
            manifest["counterfactual_spec"] = str(self.args.counterfactual_spec)
            manifest["counterfactual_spec_sha256"] = file_sha(self.args.counterfactual_spec)
            manifest["counterfactual_physically_complete"] = bool(result.get("correct_finish"))
            manifest["counterfactual_admitted"] = bool(result.get("correct_finish"))
            manifest["remaining"] = "Only correct-finish counterfactual episodes are admitted; incomplete ones remain raw evidence. Failure injections and memory cards pending."
        (self.output / "training_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
