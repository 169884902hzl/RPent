"""Audit explicitly registered original-task grasp recipes on CPU."""

import argparse
import ast
from collections import Counter, defaultdict
import hashlib
import json
import math
from pathlib import Path
import sys


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def wilson(successes, trials):
    if not trials:
        return None
    z = 1.959963984540054
    p = successes / trials
    divisor = 1 + z * z / trials
    centre = (p + z * z / (2 * trials)) / divisor
    radius = z * math.sqrt(p * (1 - p) / trials + z * z / (4 * trials * trials)) / divisor
    return [centre - radius, centre + radius]


def source_functions(path, names):
    text = path.read_text()
    lines = text.splitlines(keepends=True)
    result = {}
    for node in ast.walk(ast.parse(text)):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in names:
            code = "".join(lines[node.lineno - 1:node.end_lineno])
            result[node.name] = {"path": str(path), "line": node.lineno,
                "sha256": hashlib.sha256(code.encode()).hexdigest()}
    return result


def family(condition):
    if condition["profile"] == "start_full":
        return "reset_pose"
    return "overhead_measured_handle" if condition.get("contact_approach") == "measured_handle" else "overhead_bounds_centre"


def executed(row):
    actions = row.get("executed_vla_actions")
    if actions is not None:
        return actions > 0
    return bool(row.get("contact_prompt") and (row.get("rpent_pick_result") or {}).get("chunks_used", 0) > 0)


def metrics(rows):
    matrix, physical_failures, operational, labels = Counter(), Counter(), Counter(), Counter()
    states = Counter((r["case"]["episode"]["suite"], r["case"]["episode"]["task"],
        r["case"]["episode"]["seed"]) for r in rows)
    contact_known = contact_success = 0
    for row in rows:
        truth, visual = row.get("true_sustained_grasp"), row.get("visual_verified")
        contact = executed(row)
        receipt = row.get("first_receipt", {})
        reason = receipt.get("failure_reason", receipt.get("stop"))
        if not contact:
            operational[reason or "contact_not_executed"] += 1
        if row.get("raised_error") or receipt.get("verification") == "execution_error":
            operational["execution_or_metrology_exception"] += 1
        if not isinstance(truth, bool):
            labels["unknown_truth"] += 1
            continue
        labels["truth_success" if truth else "truth_failure"] += 1
        if isinstance(visual, bool):
            matrix["TP" if truth and visual else "FN" if truth else "FP" if visual else "TN"] += 1
        else:
            matrix["unknown_visual"] += 1
        if contact:
            contact_known += 1
            contact_success += truth
        if truth or not contact:
            continue
        checks = row.get("sustained_hold", {}).get("truth", {}).get("checks", [])
        if any(c.get("clearance_m", -math.inf) >= .03 and c.get("finger_contact") for c in checks):
            physical_failures["hold_not_sustained"] += 1
        elif any(c.get("clearance_m", -math.inf) >= .03 for c in checks):
            physical_failures["lift_without_finger_support"] += 1
        elif any(c.get("finger_contact") for c in checks):
            physical_failures["finger_contact_without_support_clearance"] += 1
        else:
            physical_failures["no_target_lift_or_hold"] += 1
    known = labels["truth_success"] + labels["truth_failure"]
    compared = sum(matrix[k] for k in ("TP", "TN", "FP", "FN"))
    return {"recorded": len(rows), "known_truth": known, "unknown_truth": labels["unknown_truth"],
        "truth_success": labels["truth_success"], "truth_success_rate": labels["truth_success"] / known if known else None,
        "wilson95": wilson(labels["truth_success"], known),
        "actual_contact_attempts": sum(executed(r) for r in rows),
        "actual_contact_known_truth": contact_known, "actual_contact_success": contact_success,
        "actual_contact_success_rate": contact_success / contact_known if contact_known else None,
        "confusion": dict(matrix), "verifier_compared": compared,
        "verifier_agreement": (matrix["TP"] + matrix["TN"]) / compared if compared else None,
        "FP": {"count": matrix["FP"], "negative_denominator": matrix["FP"] + matrix["TN"]},
        "FN": {"count": matrix["FN"], "positive_denominator": matrix["FN"] + matrix["TP"]},
        "unique_init_tuples": len(states), "repeated_init_rows": len(rows) - len(states),
        "maximum_repetitions": max(states.values(), default=0),
        "physical_failure_counts_after_actual_contact": dict(physical_failures),
        "operational_failure_counts": dict(operational),
        "interval_scope": "nominal binomial interval; repeated initial states disclosed, not independent trials"}


def audit_run(registration):
    manifest = Path(registration["manifest"]["path"])
    if sha(manifest) != registration["manifest"]["sha256"]:
        raise ValueError("registered manifest SHA mismatch")
    plan = json.loads(manifest.read_text())
    expected = {c["name"]: c for c in plan["cases"]}
    rows, seen, sources = [], set(), []
    for name in registration["ledgers"]:
        path = Path(name)
        raw = path.read_bytes()
        if not raw.endswith(b"\n"):
            raise ValueError("incomplete ledger tail")
        sources.append({"path": str(path), "sha256": sha(path)})
        for line in raw.splitlines():
            row = json.loads(line)
            case = row["case"]
            if case != expected.get(case["name"]) or case["name"] in seen:
                raise ValueError("unregistered or duplicated case")
            seen.add(case["name"])
            if sha(Path(row["output_dir"]) / "choices.jsonl") != row["choices_sha256"]:
                raise ValueError("raw choices SHA mismatch")
            rows.append(row)
    grouped = defaultdict(list)
    for row in rows:
        c = row["case"]
        grouped[(c["condition"], c.get("group", c.get("object_category")))].append(row)
    arms = []
    for (condition_name, group), members in grouped.items():
        condition = plan["conditions"][condition_name]
        item = {"condition": condition_name, "class": group, "condition_fields": condition,
            "physical_approach_family": family(condition)}
        if registration["scope"] == "first_grasp":
            item.update(metrics(members))
        else:
            item.update(recorded=len(members),
                scope="complete transfer subtask; not a first-grasp confirmation arm",
                sustained_grasp_during=sum(r["private_grasp_phase"].get("true_sustained_grasp_during_skill") is True for r in members),
                sustained_grasp_at_end=sum(r["private_grasp_phase"].get("true_sustained_grasp_at_end") is True for r in members),
                target_success=sum(r["first_attempt"]["private_after"].get("satisfied") is True for r in members),
                public_place_verdicts=dict(Counter(str(r["first_attempt"]["receipt"].get("place_verified")) for r in members)),
                actual_actions=sum(r["first_attempt"].get("executed_actions", 0) for r in members),
                qualification_authorized=False)
        arms.append(item)
    source = Path(registration["source"])
    return {"job": registration["job"], "scope": registration["scope"],
        "manifest": {"path": str(manifest), "sha256": sha(manifest)},
        "source": str(source), "source_sha256": {name: sha(source / name) for name in registration["source_files"]},
        "sources": sources, "planned": len(expected), "recorded": len(rows),
        "complete": seen == expected.keys(), "choices_sha_checked": len(rows), "arms": arms}


def first4_plan(registration):
    manifest = Path(registration["manifest"]["path"])
    if sha(manifest) != registration["manifest"]["sha256"]:
        raise ValueError("first4 manifest SHA mismatch")
    plan = json.loads(manifest.read_text())
    source = Path(registration["source"])
    probe = source / "scripts/probe_v5_grasp449_20261005.py"
    functions = source_functions(probe, {"probe_contact_prompt", "rpent_pick_then_measure", "stage_grasp", "vla_act"})
    tree = ast.parse(probe.read_text())
    prompt_node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "probe_contact_prompt")
    namespace = {}
    exec(compile(ast.Module(body=[prompt_node], type_ignores=[]), str(probe), "exec"), namespace)
    entries = []
    for group in plan["groups"]:
        condition = plan["conditions"]["confirm_" + group]
        cases = [c for c in plan["cases"] if c["group"] == group]
        example = cases[0]
        prompt, detail = namespace["probe_contact_prompt"](condition, example, example["instruction"],
            example["category"], plan["frypan_full_prompt"])
        entries.append({"class": group, "condition": condition,
            "prompt_example": {"category": example["category"], "original_instruction": example["instruction"],
                "prompt": prompt, "detail": detail},
            "public_controller": "pi0_pick(prompt,max_chunks=160), then refresh and original measured verifier",
            "verifier": "rpent_pick_then_measure; contact_verification key is absent; do not substitute strict/wrist/independent verifier",
            "staging": "exact episode reset pose; probe only checks residual<=1.2cm and does not move/reset robot" if group in ("bottle", "bowl")
                else "measured bounds XY centre, measured top+10cm, inherited safe segmented stage_grasp",
            "runtime_port_limitation": "first grasp tested at reset pose; restoring that pose later is a new unvalidated intervention" if group in ("bottle", "bowl")
                else "public high-short approach can be ported; full sequential task validation still required"})
    return {"status": "concrete proposal only, no runtime edits or jobs", "qualification_authorized": False,
        "manifest": {"path": str(manifest), "sha256": sha(manifest)},
        "source_snapshot": str(source), "source_sha256": {name: sha(source / name) for name in registration["source_files"]},
        "source_functions": functions, "entries": entries, "runtime_differences": [
            "Current default vla_act tests opening and measured grasp within each chunk; confirmed B/C uses RPent descent/ascent stop then visual measurement.",
            "Bottle/bowl C uses target_first plus complete current instruction. selected_only is a different recipe and is not their confirmation condition.",
            "Default approach uses mode-specific 4/10cm and optional yaw; confirmed B/C mode is direct with disabled retry/refinement/profile flags.",
            "Do not read BDDL or object simulator coordinates for dynamic prompt, reset pose, approach, stop or verifier.",
            "Retain public receipt schema. Any verifier/control replacement requires independent validation; absent/null metrology stays unknown.",
            "The incomplete box/mug truth cohorts retain their one executed unknown each, and cannot be declared complete qualification."],
        "integration_order": [
            "Extract exact public helpers behind an explicit opt-in manifest; keep the frozen source and condition hash.",
            "Bind class from perceived category and instruction from runtime request only; preserve exact selected_only versus target_first.",
            "For C, apply only at demonstrated reset pose first; register any actual reset-pose movement as a separate intervention.",
            "Validate complete sequential original tasks, then new/old development pairs under the same enabled recipe; do not infer from first-grasp rates.",
            "Keep pan/moka unqualified and excluded from the first4 mapping until their methods and independent confirmation satisfy unchanged gates."]}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    registration = json.loads(args.manifest.read_text())
    runs = [audit_run(run) for run in registration["runs"]]
    by_class = {}
    for group in ("bottle", "bowl", "box", "mug", "frypan", "moka_pot"):
        arms = [arm for run in runs if run["scope"] == "first_grasp" for arm in run["arms"] if arm["class"] == group]
        families = sorted({arm["physical_approach_family"] for arm in arms})
        executed100 = sorted({arm["physical_approach_family"] for arm in arms if arm["actual_contact_attempts"] >= 100})
        by_class[group] = {"observed_first_grasp_approach_families": families,
            "families_with_100_executed_contacts_in_an_arm": executed100,
            "five_distinct_methods_sufficient_evidence": False,
            "reason": "Only two or three physical approach families in these explicit registrations; budget/name/verifier variants are retained but not counted as independent approach methods. Full-subtask smoke arms each contain one case only."}
    report = {"scope": "closed original-task method evidence; not training admission or a model score",
        "registration": {"path": str(args.manifest), "sha256": sha(args.manifest)},
        "script": {"path": str(Path(__file__)), "sha256": sha(__file__), "python": sys.executable},
        "runs": runs, "by_class_method_evidence": by_class,
        "method_counting": {"max_chunks160_vs320": "same approach family, budget experiment",
            "frypan_vs_frying_pan": "prompt alias, not a new physical approach family",
            "moka3550_B_vs_BA": "identical condition except an unused frypan alias; stochastic repeats",
            "target_first_vs_selected_only": "different prompt/control recipe within reset family; separately reported",
            "trial_lift_and_two_frame_verifier": "different public control/verifier recipe; not secretly pooled with old receipts",
            "full_subtask_vs_first_grasp": "different skill scope and end condition, never pooled into first-grasp qualification"},
        "five_method_stop_rule_triggered_by_sufficient_evidence": False,
        "qualification_authorized": False, "new_training_rows": 0, "new_physics_trials": 0,
        "limits": ["Explicit listed runs only; no claim that all earlier experiments were exhaustively audited.",
            "Repeated official initial-state tuples are not 100 independent states.",
            "A missing measured handle is a registered operational failure with no contact attempt, not an executed physical branch.",
            "Unknown truth or public verdict is retained; conditional verifier rates disclose denominators.",
            "Confirm all six classes on new non-overlapping states before applying overall95/class90/verifier95 qualification."]}
    integration = first4_plan(registration["first4"])
    args.output.mkdir(parents=True, exist_ok=False)
    (args.output / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    (args.output / "first4_runtime_integration_plan.json").write_text(json.dumps(integration, indent=2) + "\n")
    lines = ["# Original-task grasp method evidence", "", "No complete five-distinct-method evidence for pan or moka is established by the explicitly audited registrations. Gates remain overall95/class90/verifier95; no qualification or new runtime implementation.", "",
        "| Job | Condition/class | Truth success | Wilson95 | Actual contacts | Agreement | FP / negatives | FN / positives | Unique states / repeats |",
        "|---|---|---|---|---|---|---|---|---|"]
    for run in runs:
        for arm in run["arms"]:
            if run["scope"] != "first_grasp":
                continue
            interval = arm["wilson95"]
            ci = "unknown" if interval is None else f"{100*interval[0]:.2f}–{100*interval[1]:.2f}%"
            agreement = arm["verifier_agreement"]
            percent = "unknown" if agreement is None else f"{100*agreement:.1f}%"
            lines.append(f"| {run['job']} | {arm['condition']}/{arm['class']} | {arm['truth_success']}/{arm['known_truth']} | {ci} | {arm['actual_contact_attempts']} | {percent} | {arm['FP']['count']}/{arm['FP']['negative_denominator']} | {arm['FN']['count']}/{arm['FN']['positive_denominator']} | {arm['unique_init_tuples']}/{arm['repeated_init_rows']} |")
    lines += ["", "160/320 budgets and pan naming aliases are not additional approach families. Moka3550 B/BA are the same physical control with the frypan alias unused. Missing-handle trials remain operational failures. Nominal Wilson intervals do not remove dependence of repeated initial states.", "", "## Complete-subtask smoke, separate scope", ""]
    for run in runs:
        if run["scope"] == "first_grasp":
            continue
        for arm in run["arms"]:
            lines.append(f"- {run['job']} {arm['condition']}/{arm['class']}: n={arm['recorded']}, sustained during={arm['sustained_grasp_during']}, sustained at end={arm['sustained_grasp_at_end']}, target success={arm['target_success']}. Successful release is not a prior grasp failure.")
    lines += ["", "## Fixed first4 runtime proposal", "", "The exact confirmation source is retained in first4_runtime_integration_plan.json. Bottle/bowl C is target_first + complete current instruction, exact reset pose and RPent stop160; box/mug B is measured top+10cm and selected category short prompt. Both use the old rpent_pick_then_measure helper, not the later wrist/strict/independent verifier. Applying C after a robot move requires validation of the added movement.", "", f"Report SHA256: {sha(args.output/'report.json')}", f"Plan SHA256: {sha(args.output/'first4_runtime_integration_plan.json')}"]
    (args.output / "REPORT.md").write_text("\n".join(lines) + "\n")
    print(json.dumps({"recorded": sum(run["recorded"] for run in runs), "choices_sha_checked": sum(run["choices_sha_checked"] for run in runs),
        "five_methods_sufficient": False, "report": str(args.output / "report.json"), "report_sha256": sha(args.output / "report.json"),
        "plan_sha256": sha(args.output / "first4_runtime_integration_plan.json")}))


if __name__ == "__main__":
    main()
