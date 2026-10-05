"""Diagnose a fixed, hash-registered moka cohort from closed original trials.

This reads only the supplied report and its eight explicitly named snapshots.
Private contacts establish measurement labels, never runtime geometry/actions.
"""

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def runs(samples, predicate):
    selected, result = [], []
    for index, sample in enumerate(samples):
        if predicate(sample):
            selected.append((index, sample))
        elif selected:
            result.append(selected)
            selected = []
    if selected:
        result.append(selected)
    return result


def interval(segment):
    return {"sample_indices": [segment[0][0], segment[-1][0]],
            "sim_time_s": [segment[0][1]["sim_time"], segment[-1][1]["sim_time"]],
            "duration_s": segment[-1][1]["sim_time"] - segment[0][1]["sim_time"],
            "samples": len(segment)}


def object_measurement(state, identity):
    return next(entity for entity in state["entities"] if entity["id"] == identity)


def analyze(row, source, record):
    attempt = row["first_attempt"]
    phase = row["private_grasp_phase"]
    reference = phase["reference"]
    samples = phase["samples"]
    supports = set(reference["other_contact_geoms"])

    def lifted(sample):
        return sample["lower_extent_m"] - reference["lower_extent_m"] >= .03

    def held(sample):
        return (lifted(sample) and sample["finger_contact"]
                and not supports.intersection(sample["other_contact_geoms"]))

    held_runs = runs(samples, held)
    sustained = any(segment[-1][1]["sim_time"] - segment[0][1]["sim_time"] + 1e-8 >= .5
                    for segment in held_runs)
    if sustained != phase["true_sustained_grasp_during_skill"]:
        raise ValueError("existing sustained-grasp label differs from its own samples")
    final_sustained = bool(held_runs and held_runs[-1][-1][0] == len(samples) - 1
                           and held_runs[-1][-1][1]["sim_time"] - held_runs[-1][0][1]["sim_time"] + 1e-8 >= .5)
    if final_sustained != phase["true_sustained_grasp_at_end"]:
        raise ValueError("existing final sustained-grasp label differs from its own samples")
    receipt = attempt["receipt"]
    identity, target = receipt["object"], receipt["target"]
    before = object_measurement(attempt["public_before"], identity)
    after = object_measurement(attempt["public_after"], identity)
    motions, chunks, moves, action_lookup, offset = [], [], [], [], 0
    for motion in attempt["motion_evidence"]:
        count = motion.get("actions_used", motion.get("executed_action_count", 0))
        compact = {key: motion[key] for key in (
            "name", "target_xyz", "final_eef_pos", "final_dist_m", "steps_used",
            "actions_used", "executed_action_count", "instruction", "gripper_opening") if key in motion}
        compact["sample_index_range"] = [offset, offset + count - 1]
        compact["sim_time_range_s"] = ([samples[offset]["sim_time"], samples[offset + count - 1]["sim_time"]]
                                         if count and offset + count <= len(samples) else None)
        if motion["name"] == "vla_act_chunk":
            compact["chunk"] = len(chunks) + 1
            actions = motion["actions"]
            if len(actions) != count:
                raise ValueError("chunk actions do not match executed count")
            compact["gripper_commands"] = [action[6] for action in actions]
            action_lookup.extend({"motion": len(motions), "chunk": compact["chunk"],
                                  "action_in_chunk": i, "gripper_command": action[6]}
                                 for i, action in enumerate(actions))
            chunks.append(compact)
        else:
            action_lookup.extend({"motion": len(motions), "chunk": None,
                                  "action_in_chunk": i,
                                  "gripper_command": motion.get("gripper_command")}
                                 for i in range(count))
            moves.append(compact)
        motions.append(compact)
        offset += count
    if offset != len(samples):
        raise ValueError("contact sample count does not align with motion execution counts")
    loss = None
    witness = phase.get("first_sustained_grasp")
    witness_contacts = None
    if witness:
        witness_samples = [sample for sample in samples if
                           witness["start_sim_time"] <= sample["sim_time"] <= witness["end_sim_time"]]
        witness_contacts = dict(Counter(contact for sample in witness_samples
                                       for contact in sample["other_contact_geoms"]))
        for index, sample in enumerate(samples):
            if sample["sim_time"] > witness["end_sim_time"] and not sample["finger_contact"]:
                action = action_lookup[index]
                motion = motions[action["motion"]]
                loss = {"sample_index": index, "sim_time_s": sample["sim_time"],
                        "clearance_m": sample["lower_extent_m"] - reference["lower_extent_m"],
                        "other_contact_geoms": sample["other_contact_geoms"],
                        "executed_action": action,
                        "chunk_endpoint_eef_xyz": motion.get("final_eef_pos"),
                        "chunk_endpoint_gripper_m": motion.get("gripper_opening"),
                        "endpoint_scope": "end of enclosing executed chunk, not exact loss-frame pose"}
                break
    max_lift = max(sample["lower_extent_m"] - reference["lower_extent_m"] for sample in samples)
    truth = attempt["private_after"]["satisfied"]
    if truth:
        diagnosis = "target_satisfied"
    elif not sustained and max_lift < .03:
        diagnosis = "finger_contact_without_3cm_lift"
    elif not sustained:
        diagnosis = "brief_lift_without_0p5s_sustained_hold"
    elif loss and loss["executed_action"]["gripper_command"] is not None and loss["executed_action"]["gripper_command"] > 0:
        diagnosis = "contact_lost_while_commanded_closed_target_not_satisfied"
    else:
        diagnosis = "sustained_grasp_target_not_satisfied_cause_unresolved"
    existing = {"sustained_during": sustained, "sustained_at_end": final_sustained,
                "target_truth": truth, "public_place_verified": receipt.get("place_verified")}
    if any(record[key] != value for key, value in existing.items()):
        raise ValueError("fixed report labels changed")
    return {"case": row["case"]["name"], "episode": row["case"]["episode"],
            "input_snapshot": source, "choices": record["choices"],
            "choices_sha256": record["choices_sha256"], "existing_labels": existing,
            "original_failure_category": record["failure"], "diagnostic_category": diagnosis,
            "prompt": receipt["subtask_prompt"], "prompt_scope": row["case"]["prompt_scope"],
            "stop": receipt["stop"], "chunks": receipt["chunks"],
            "contact_samples": len(samples), "motion_sample_count_match": True,
            "finger_contact_samples": sum(sample["finger_contact"] for sample in samples),
            "dual_finger_contact_samples": sum(sample["dual_finger_contact"] for sample in samples),
            "lift_ge3cm_samples": sum(lifted(sample) for sample in samples),
            "finger_and_lift_ge3cm_samples": sum(lifted(sample) and sample["finger_contact"] for sample in samples),
            "max_clearance_m": max_lift, "qualifying_hold_intervals": [interval(segment) for segment in held_runs],
            "first_existing_sustained_witness": witness,
            "first_witness_nonfinger_contact_counts": witness_contacts,
            "first_contact_loss_after_sustained": loss,
            "end_contact_geoms": samples[-1]["other_contact_geoms"],
            "public_object_before": before, "public_object_after": after,
            "public_target_before": object_measurement(attempt["public_before"], target),
            "verification_measurements": attempt["verification_measurements"],
            "approach_target_xyz": receipt["approach_target_xyz"],
            "approach_residual_m": receipt["approach_residual_m"],
            "move_traces": moves, "chunk_traces": chunks,
            "private_coordinate_use": "diagnosis only; no executor, public perception, action or label changed"}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--prefix-report", type=Path, required=True)
    parser.add_argument("--choices-sha-check", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report_bytes = args.prefix_report.read_bytes()
    report = json.loads(report_bytes)
    fixed = {record["case"]: record for record in report["records"]
             if record["class"] == "moka pot" and record["condition"] == "centre_full_subtask160"
             and record["initial_state_repetition"] == 0}
    if len(fixed) != 11:
        raise ValueError("diagnosis is restricted to the previously frozen 11-case cohort")
    checks_bytes = args.choices_sha_check.read_bytes()
    checks = json.loads(checks_bytes)
    if checks["report_sha256"] != sha(report_bytes) or checks["checked"] != len(fixed):
        raise ValueError("choices check has a different fixed cohort")
    for check in checks["checks"]:
        record = fixed[check["case"]]
        if not check["match"] or check["actual_sha256"] != record["choices_sha256"] or check["path"] != record["choices"]:
            raise ValueError("remote choices SHA failed")
    records, snapshots, seen = [], [], set()
    for source in report["sources"]:
        path = args.prefix_report.parent / Path(source["closed_snapshot"]).name
        raw = path.read_bytes()
        if sha(raw) != source["closed_sha256"]:
            raise ValueError("immutable snapshot changed")
        snapshots.append({"path": str(path), "sha256": sha(raw)})
        for line_number, line in enumerate(raw.splitlines(), 1):
            if not line.strip():
                continue
            row = json.loads(line)
            name = row["case"]["name"]
            if name not in fixed:
                continue
            if name in seen or row["choices_sha256"] != fixed[name]["choices_sha256"]:
                raise ValueError("duplicated or changed registered trial")
            seen.add(name)
            records.append(analyze(row, {"path": str(path), "sha256": sha(raw),
                                         "line": line_number}, fixed[name]))
    if seen != set(fixed):
        raise ValueError("fixed cohort missing from explicit snapshots")
    records.sort(key=lambda record: record["episode"]["seed"])
    result = {"scope": "fixed report6 closed original moka trials; CPU root-cause diagnosis only",
              "job": report["job"], "prefix_report": {"path": str(args.prefix_report), "sha256": sha(report_bytes)},
              "script_sha256": sha(Path(__file__).read_bytes()),
              "choices_sha_check": {"path": str(args.choices_sha_check), "sha256": sha(checks_bytes),
                                    "checked": checks["checked"], "mismatches": 0},
              "explicit_snapshot_inputs": snapshots, "rows": len(records), "label_changes": 0,
              "new_physics_trials": 0, "new_training_rows": 0,
              "diagnostic_counts": dict(Counter(record["diagnostic_category"] for record in records)),
              "unknown_public_place": sum(record["existing_labels"]["public_place_verified"] is None for record in records),
              "public_final_visible": sum(record["public_object_after"]["visible"] for record in records),
              "records": records,
              "limits": ["Eleven exploratory scenes do not establish class qualification or a causal effect.",
                         "Complete transfer prompts permit later release; final non-held state cannot erase earlier true grasp.",
                         "The official final target label is preserved even when support-contact evidence is ambiguous.",
                         "Private contact/clearance is measurement only and does not enter runtime text, perception or control.",
                         "Legacy grasp trace excludes only original support contacts: a later target-surface contact can coexist with its held-at-end flag. Preserve that flag without claiming exclusive gripper support.",
                         "Cached/invisible end measurements do not establish final placement; public unknown stays unknown.",
                         "Contact-loss command alignment uses exact accumulated executed counts; chunk endpoint is not exact loss pose."]}
    args.output.mkdir(parents=True, exist_ok=False)
    (args.output / "report.json").write_text(json.dumps(result, indent=2) + "\n")
    lines = ["# Moka centre: fixed 11 closed original trials", "",
             "CPU diagnosis of the report6 cohort. Existing labels and all raw trials remain unchanged. No new physics run, runtime change, training row, or qualification claim.", "",
             "| Original seed | Sustained / target | Max clearance | Finger / dual samples | Public final visible / place | Diagnostic |",
             "|---|---|---|---|---|---|"]
    for record in records:
        label = record["existing_labels"]
        lines.append(f"| {record['episode']['seed']} | {label['sustained_during']} / {label['target_truth']} | {record['max_clearance_m']*100:.2f} cm | {record['finger_contact_samples']} / {record['dual_finger_contact_samples']} | {record['public_object_after']['visible']} / {label['public_place_verified']} | {record['diagnostic_category']} |")
    lines += ["", "All initial approach endpoints were within approximately 0.8–1.2 cm. The five no-sustained-hold failures are not endpoint-servo failures: seeds3/4/7 had no clearance; seed5 reached only1.72cm despite dual contact; seed2 had only a brief >=3cm contact lift.", "",
              "Seed8 formed the existing sustained witness at18.70–19.20s. The first subsequent contact loss at19.35s still had a positive (closed) gripper command; the enclosing chunk ended with the opening narrowing from about50mm to6mm. Opening commands began only in the following chunk. Final table contact and false official target support a transport-slip diagnosis, rather than deliberate successful release.", "",
              "Five final targets are true despite all stop reasons being chunk_budget. Seven public placement verdicts remain unknown; seven final object measurements are invisible cached measurements. Cached locations must not supply a missing final placement verdict.", "",
              "The official labels, including seed5's false final target despite burner contact, are unchanged. Contact with a target surface alone does not replace the official predicate. Fixed11 is exploratory and cannot select or qualify a class skill card.", "",
              "Legacy trace limitation: seed13's held-at-end flag coexists with burner contact and a single finger contact. The original truth helper excludes only the original table support; this flag is preserved and cannot be described as exclusive support by the gripper. Its earlier first sustained witness had no non-finger contact. Seed9's first witness contains one burner-contact sample, also retained as raw evidence.", "",
              f"Report SHA256: {sha((args.output/'report.json').read_bytes())}"]
    (args.output / "REPORT.md").write_text("\n".join(lines) + "\n")
    print(json.dumps({"rows": len(records), "diagnostic_counts": result["diagnostic_counts"],
                      "report_sha256": sha((args.output / "report.json").read_bytes())}))


if __name__ == "__main__":
    main()
