# Copyright 2026 Zhilun Hu.
# SPDX-License-Identifier: Apache-2.0
"""Prepare explicit box continuation and mug infrastructure rerun manifests."""

import argparse
import copy
import hashlib
import json
from pathlib import Path

PARENT_SHA = "dfa8c31e0568d52e9ffb19ca4d7d338284eb08460aa6424e523d9fe012a67ac9"
CHOICE_FILES = ("tokenizer_config.json", "tokenizer.json", "merges.txt", "vocab.json",
                "schema_config.json", "parallel_schema.py")


def identity(path):
    path = path.resolve(strict=True)
    return {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def prepare(parent, remaining, *, parent_record, remaining_record, choice_files, old_ledgers,
            prior_rows, smoke_dependency):
    """Keep the registered recipes/states and the unknown box truth untouched."""
    boxes = [case for case in parent["cases"] if case["group"] == "box"]
    mugs = [case for case in parent["cases"] if case["group"] == "mug"]
    if len(boxes) != 100 or len(mugs) != 100:
        raise ValueError("the original confirmation must contain box100 and mug100")
    expected = boxes[48:]
    if remaining["cases"] != expected:
        raise ValueError("box continuation must be the exact 52 unexecuted registered states")
    prior_by_name = {}
    for row in prior_rows:
        name = row["case"]["name"]
        receipt = row.get("first_receipt", {})
        executed = bool(receipt.get("executed") or row.get("executed_vla_actions")
                        or row.get("contact_samples") or row.get("rpent_pick_result", {}).get("chunks_used"))
        prior_by_name[name] = prior_by_name.get(name, False) or executed
    retry_policy = {"version": "grasp-infrastructure-repair/1", "same_state_retries": 1,
                    "maximum_infrastructure_failure_rate": .02,
                    "rate_denominator": "all registered cases in this manifest",
                    "failure_ledger": "infrastructure_attempts.jsonl",
                    "physical_failures_retried": False,
                    "physically_executed_infrastructure_faults_retried": False,
                    "environment_restart": "run_episode closes each owned environment; retry creates a new daemon"}
    outputs = {}
    for group, cases, label in (("box", expected, "box52"), ("mug", mugs, "mug100")):
        plan = copy.deepcopy(parent)
        plan.update(groups=[group], cases=copy.deepcopy(cases),
                    conditions={"confirm_" + group: copy.deepcopy(parent["conditions"]["confirm_" + group])},
                    cohort="registered_infrastructure_repair_" + label,
                    new_training_rows=0, qualification_authorized=False,
                    original_confirmation=parent_record, prior_infrastructure_ledgers=old_ledgers,
                    infrastructure_retry_policy=retry_policy,
                    smoke_dependency=smoke_dependency,
                    choice_package_files=choice_files,
                    selection="Original registered state order only; no physical-score filtering or replacements")
        for case in plan["cases"]:
            if prior_by_name.get(case["name"], False):
                raise ValueError("confirmation must never reexecute a prior physical attempt")
            case["infrastructure_repair_run"] = {
                "kind": "unexecuted_continuation" if group == "box" else "requested_full_infrastructure_rerun",
                "old_artifacts_preserved": True,
                "independent_new_state": False,
                "replace_prior_physical_outcome": False,
                "prior_physical_execution": False,
                "not_previsited_by_grasp_smoke": True,
                "original_case_name": case["name"], "original_state_sha256": case["state_sha256"]}
        if group == "box":
            plan["continuation"] = copy.deepcopy(remaining["continuation"])
            plan["continuation_manifest"] = remaining_record
        else:
            plan["rerun_notice"] = ("Requested full100 rerun after infrastructure repair. Retain all prior attempts; "
                                    "this repeated-state run cannot erase a physical failure or create independent states.")
        outputs[label] = plan
    return outputs


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--parent", type=Path, required=True)
    parser.add_argument("--remaining-box", type=Path, required=True)
    parser.add_argument("--old-ledger", type=Path, action="append", required=True)
    parser.add_argument("--smoke-dependency-job", type=int, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("use a new preparation directory; old artifacts are immutable")
    parent_record = identity(args.parent)
    if parent_record["sha256"] != PARENT_SHA:
        raise ValueError("registered original400 confirmation changed")
    parent = json.loads(args.parent.read_text())
    base = identity(Path(parent["base_config"]["path"]))
    if base["sha256"] != parent["base_config"]["sha256"]:
        raise ValueError("registered base config changed")
    if json.loads(Path(base["path"]).read_text()).get("libero_type") != "standard":
        raise ValueError("only standard original LIBERO is supported")
    parent["base_config"] = base
    choice = Path(parent["choice_package"]).resolve(strict=True)
    parent["choice_package"] = str(choice)
    choice_files = [identity(choice / name) for name in CHOICE_FILES]
    remaining = json.loads(args.remaining_box.read_text())
    records = [identity(path) for path in args.old_ledger]
    prior_rows = [json.loads(line) for path in args.old_ledger for line in path.read_text().splitlines()]
    smoke_dependency = {"job_id": args.smoke_dependency_job,
                        "cohort": "main_harness_original10_and_development10",
                        "must_complete_without_unresolved_infrastructure_failures": True,
                        "status_at_preparation": "pending_runtime_result",
                        "confirmation_states_are_not_smoke_inputs": True}
    outputs = prepare(parent, remaining, parent_record=parent_record,
                      remaining_record=identity(args.remaining_box), choice_files=choice_files,
                      old_ledgers=records, prior_rows=prior_rows, smoke_dependency=smoke_dependency)
    args.output.mkdir(parents=True, exist_ok=False)
    inventory = {}
    for label, plan in outputs.items():
        path = args.output / (label + ".json")
        path.write_text(json.dumps(plan, indent=2) + "\n")
        inventory[label] = {**identity(path), "cases": len(plan["cases"])}
    registration = {"producer": identity(Path(__file__)), "manifests": inventory,
                    "old_artifacts_preserved": True, "new_training_rows": 0,
                    "qualification_authorized": False, "smoke_dependency": smoke_dependency,
                    "confirmation_states_not_physically_previsited": True}
    (args.output / "registration.json").write_text(json.dumps(registration, indent=2) + "\n")
    print(json.dumps(registration, indent=2))


if __name__ == "__main__":
    main()
