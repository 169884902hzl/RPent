"""Audit C's saved target motion and release evidence without new physics.

Body-origin rise and dual-pad contact are diagnostic proxies. This script never
changes the registered whole-geometry/sustained-hold truth or training labels.
All input files are explicit; no artifact discovery is performed.
"""

import argparse
import ast
from collections import Counter, defaultdict
import hashlib
import json
import math
from pathlib import Path
import statistics


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def distance_xy(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


def quantiles(values):
    values = sorted(value for value in values if value is not None)
    if not values:
        return {"n": 0, "median": None, "p95": None, "max": None}
    return {"n": len(values), "median": statistics.median(values),
            "p95": values[math.ceil(.95 * len(values)) - 1], "max": values[-1]}


def source_function(path, name):
    source = path.read_text()
    function = next(node for node in ast.walk(ast.parse(source))
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                    and node.name == name)
    return {"path": str(path), "sha256": sha(path), "function": name,
            "line_start": function.lineno, "line_end": function.end_lineno,
            "text": "\n".join(source.splitlines()[function.lineno - 1:function.end_lineno])}


def touching_geoms(sample, symbol):
    others = []
    for contact in sample["contacts"]:
        a, b = contact["geom1"] or "<unnamed_geom>", contact["geom2"] or "<unnamed_geom>"
        if a.startswith(symbol + "_") and not b.startswith(symbol + "_"):
            others.append(b)
        elif b.startswith(symbol + "_") and not a.startswith(symbol + "_"):
            others.append(a)
    return sorted(set(others))


def object_motion(row, choice, symbol):
    initial = row["initial_private_reference"]["objects"][symbol]["xyz"]
    final = row["final_private_contact"]["objects"][symbol]
    motions = [event for event in choice["motion_evidence"] if event["name"] == "vla_act_chunk"]
    samples = row["contact_samples"]
    if len(motions) != len(samples):
        raise ValueError("VLA/contact sample pairing is not one-to-one")
    trace = []
    for index, (sample, motion) in enumerate(zip(samples, motions)):
        body = sample["objects"][symbol]
        xyz = body["xyz"]
        geoms = touching_geoms(sample, symbol)
        trace.append({"chunk": index + 1, "sim_time": sample["sim_time"], "xyz_m": xyz,
                      "xy_displacement_m": distance_xy(initial, xyz),
                      "body_origin_rise_m": xyz[2] - initial[2],
                      "dual_finger_contact": body["dual_finger_contact"],
                      "any_finger_contact": any("finger" in name and "gripper" in name for name in geoms),
                      "touching_geoms": geoms,
                      "gripper_opening_m": motion["gripper_opening"],
                      "eef_xyz_m": motion["final_eef_pos"]})
    lifts = [sample for sample in trace
             if sample["dual_finger_contact"] and sample["body_origin_rise_m"] >= .03]
    finger_lifts = [sample for sample in trace
                    if sample["any_finger_contact"] and sample["body_origin_rise_m"] >= .03]
    first_dual_lift = lifts[0]["chunk"] if lifts else None
    first_lift = finger_lifts[0]["chunk"] if finger_lifts else None
    after_lift = [sample for sample in trace if first_lift and sample["chunk"] > first_lift]
    losses = [sample for sample in after_lift if not sample["any_finger_contact"]]
    open_losses = [sample for sample in losses if sample["gripper_opening_m"] >= .06]
    # A returned-to-support-height, open-gripper sample after a lift is a
    # release/settling proxy, not proof of task-correct placement or intention.
    returned = [sample for sample in open_losses if sample["body_origin_rise_m"] <= .015]
    other_contacts = touching_geoms(row["final_private_contact"], symbol)
    return {"symbol": symbol, "initial_xyz_m": initial, "final_xyz_m": final["xyz"],
            "final_xy_displacement_m": distance_xy(initial, final["xyz"]),
            "final_body_origin_rise_m": final["xyz"][2] - initial[2],
            "max_chunk_xy_displacement_m": max((x["xy_displacement_m"] for x in trace), default=0),
            "max_chunk_body_origin_rise_m": max((x["body_origin_rise_m"] for x in trace), default=0),
            "first_dual_contact_and_3cm_body_rise_chunk": first_dual_lift,
            "first_any_finger_contact_and_3cm_body_rise_chunk": first_lift,
            "post_lift_loss_of_any_finger_contact_chunks": [sample["chunk"] for sample in losses],
            "post_lift_open_gripper_loss_chunks": [sample["chunk"] for sample in open_losses],
            "post_lift_open_gripper_return_to_support_height_proxy_chunks": [sample["chunk"] for sample in returned],
            "final_dual_finger_contact": final["dual_finger_contact"],
            "final_contact_geoms": sorted(set(other_contacts)), "chunk_trace": trace}


def diagnose(row, choice, cohort):
    if row["case"]["condition"] != "rpent_start_bound_full160":
        raise ValueError("this diagnosis only accepts registered C trials")
    symbol = row["final_private_contact"]["selected_symbol"]
    target = object_motion(row, choice, symbol)
    other = [object_motion(row, choice, name) for name in row["initial_private_reference"]["objects"]
             if name != symbol]
    other_lifted = [motion for motion in other if motion["first_any_finger_contact_and_3cm_body_rise_chunk"]]
    # Keep the entire selected target trajectory and just the relevant other
    # object evidence; never classify ordinary XY approach as placement.
    for motion in other_lifted:
        motion.pop("chunk_trace")
    checks = row["sustained_hold"]["truth"]["checks"]
    target_settled_after_release = bool(
        target["post_lift_open_gripper_loss_chunks"]
        and not checks[-1]["finger_contact"]
        and (checks[-1]["touching_original_support"] or checks[-1]["clearance_m"] <= .015))
    tail = row["sustained_hold"]["samples"][-5:]
    # Also check a possible raised support. This remains a settling proxy,
    # because support identity/goal correctness is not evaluated here.
    supported_tail = all(not sample["finger_contact"] and any(
        name and not name.startswith(("gripper", "robot")) for name in sample["other_contact_geoms"])
        for sample in tail)
    target_stable_supported_after_release = bool(target["post_lift_open_gripper_loss_chunks"]
        and supported_tail
        and max(sample["lower_extent_m"] for sample in tail)
            - min(sample["lower_extent_m"] for sample in tail) <= .005)
    first_dual_lift = target["first_dual_contact_and_3cm_body_rise_chunk"]
    target_dual_lift_release_supported = bool(target_stable_supported_after_release
        and first_dual_lift and any(chunk > first_dual_lift
                                  for chunk in target["post_lift_open_gripper_loss_chunks"]))
    public = row["rpent_pick_result"]
    diagnostics = public["diagnostics"]
    heuristic_stop = bool(diagnostics["descent_done"]
                          and public["peak_lift_m"] >= diagnostics["lift_thresh"]
                          and diagnostics["gripper_open_thresh"] <= public["final_gripper_opening"]
                          < diagnostics["gripper_closed_thresh"])
    return {"case": row["case"], "cohort": cohort, "output_dir": row["output_dir"],
            "choices_sha256": row["choices_sha256"], "prompt": row["contact_prompt"],
            "original_full_prompt": row.get("original_full_prompt"),
            "original_truth_unchanged": row["true_sustained_grasp"],
            "original_visual_verified": row["visual_verified"],
            "target_motion": target, "other_lifted_objects_proxy": other_lifted,
            "target_released_then_final_settled_proxy": target_settled_after_release,
            "target_released_then_final_stable_support_proxy": target_stable_supported_after_release,
            "target_dual_lift_then_release_then_stable_support_proxy": target_dual_lift_release_supported,
            "private_hold_truth_unchanged": row["sustained_hold"]["truth"],
            "public_pick_result": public, "public_heuristic_stop_at_last_chunk": heuristic_stop,
            "public_at_chunk_budget": public["chunks_used"] >= public["max_chunks"],
            "public_budget_failure": public["chunks_used"] >= public["max_chunks"] and not public["success"],
            "final_robot_measurement": choice["post_robot_measurement"],
            "initial_robot_measurement": choice["robot_measurement"],
            "result_official_success": row["result"].get("official_success"),
            "receipt_unchanged": row["first_receipt"]}


def summarize(rows):
    groups = defaultdict(list)
    for row in rows:
        groups[row["case"]["group"]].append(row)
    summaries = []
    for group, trials in sorted(groups.items()):
        counts = Counter()
        for row in trials:
            target = row["target_motion"]
            counts["trials"] += 1
            counts["registered_true_sustained_grasp"] += row["original_truth_unchanged"] is True
            counts["registered_visual_verified"] += row["original_visual_verified"] is True
            counts["public_pick_success"] += row["public_pick_result"]["success"] is True
            counts["public_heuristic_stop"] += row["public_heuristic_stop_at_last_chunk"]
            counts["public_at_chunk_budget"] += row["public_at_chunk_budget"]
            counts["public_budget_failure"] += row["public_budget_failure"]
            counts["public_native_terminated"] += row["public_pick_result"]["terminated"] is True
            counts["target_dual_contact_and_3cm_body_rise_proxy"] += bool(target["first_dual_contact_and_3cm_body_rise_chunk"])
            counts["target_any_finger_contact_and_3cm_body_rise_proxy"] += bool(target["first_any_finger_contact_and_3cm_body_rise_chunk"])
            counts["target_lost_any_finger_contact_after_lift_proxy"] += bool(target["post_lift_loss_of_any_finger_contact_chunks"])
            counts["target_open_gripper_after_lift_proxy"] += bool(target["post_lift_open_gripper_loss_chunks"])
            counts["target_open_gripper_and_return_to_support_height_proxy"] += bool(target["post_lift_open_gripper_return_to_support_height_proxy_chunks"])
            counts["target_release_then_final_settled_proxy"] += row["target_released_then_final_settled_proxy"]
            counts["target_release_then_final_stable_support_proxy"] += row["target_released_then_final_stable_support_proxy"]
            counts["target_dual_lift_then_release_then_stable_support_proxy"] += row["target_dual_lift_then_release_then_stable_support_proxy"]
            counts["other_object_contact_and_body_rise_proxy"] += bool(row["other_lifted_objects_proxy"])
            counts["other_object_release_and_return_to_support_height_proxy"] += any(
                motion["post_lift_open_gripper_return_to_support_height_proxy_chunks"]
                for motion in row["other_lifted_objects_proxy"])
        fields = ("final_xy_displacement_m", "final_body_origin_rise_m", "max_chunk_xy_displacement_m",
                  "max_chunk_body_origin_rise_m")
        summaries.append({"class": group, "counts": dict(counts),
            "motion_m": {field: quantiles([row["target_motion"][field] for row in trials]) for field in fields},
            "chunks_used": quantiles([row["public_pick_result"]["chunks_used"] for row in trials]),
            "final_gripper_opening_m": quantiles([row["public_pick_result"]["final_gripper_opening"] for row in trials])})
    return summaries


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ledger", action="append", type=Path, required=True)
    parser.add_argument("--frozen-source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    rows, sources, seen = [], [], set()
    for ledger in args.ledger:
        raw = ledger.read_bytes()
        if not raw.endswith(b"\n"):
            raise ValueError("closed ledger must end with a complete newline")
        inputs = raw.splitlines()
        if len(inputs) != 100:
            raise ValueError("expected a complete 100-trial C shard")
        sources.append({"path": str(ledger), "sha256": hashlib.sha256(raw).hexdigest(), "rows": len(inputs)})
        for line in inputs:
            row = json.loads(line)
            path = Path(row["output_dir"]) / "choices.jsonl"
            if path in seen or sha(path) != row["choices_sha256"]:
                raise ValueError("duplicate or changed choices")
            seen.add(path)
            choices = list(map(json.loads, path.read_text().splitlines()))
            if len(choices) != 1:
                raise ValueError("registered first-grasp probe must contain exactly one decision")
            rows.append(diagnose(row, choices[0], ledger.parent.name))
    source_refs = [source_function(args.frozen_source / "robots/libero/tools.py", "pi0_pick"),
                   source_function(args.frozen_source / "scripts/probe_v5_grasp449_20261005.py", "vla_act"),
                   source_function(args.frozen_source / "robots/libero/v5_env_client.py", "complete_skill")]
    report = {"scope": "CPU only; selected-object and other-object saved motion; no new physics, policy or labels",
              "recorded": len(rows), "choices_sha256_checked": len(seen), "sources": sources,
              "script_sha256": sha(__file__), "frozen_source_functions": source_refs,
              "by_class": summarize(rows), "new_training_rows": 0, "new_physics_trials": 0,
              "private_diagnostic_labels_enter_runtime": False,
              "limits": ["Chunk-boundary samples can miss shorter contact/release events within the five-step block.",
                         "Body-origin lift plus dual contact is a proxy, not whole-geometry clearance or0.5s hold truth.",
                         "Release/settling proxy cannot establish intentional or task-correct placement.",
                         "No goal-region/BDDL or PRO task file was read; finalXYZ is private diagnosis only.",
                         "Finite-skill scope withholds native termination until the measured grasp skill completes.",
                         "Final XYZ precedes the private0.5s truth hold; hold checks are reported separately."]}
    args.output.mkdir(parents=True)
    with (args.output / "trials.jsonl").open("x") as handle:
        for row in rows:
            handle.write(json.dumps(row) + "\n")
    (args.output / "summary.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"recorded": len(rows), "choices_sha256_checked": len(seen),
                      "by_class": report["by_class"], "summary_sha256": sha(args.output / "summary.json"),
                      "trials_sha256": sha(args.output / "trials.jsonl")}))


if __name__ == "__main__":
    main()
