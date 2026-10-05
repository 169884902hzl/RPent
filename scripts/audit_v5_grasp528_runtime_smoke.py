"""Read-only audit of explicit category-runtime grasp smoke ledgers.

This smoke records metadata/clouds but not SAM masks. Missing masks are a
declared evidence limit, not an execution failure. Public instantaneous frames
and the later private 0.5 s hold are never substituted for one another.
"""

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

import numpy as np


def identity(path):
    return {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def artifact(output, name, step):
    if Path(name).name != name:
        raise ValueError("artifact declaration is not a base name")
    return output / name / f"{step:02d}{Path(name).suffix}"


def audit_case(row, registered):
    case = row["case"]
    if registered.get(case["name"]) != case or case["episode"]["suite"] not in {
            "libero_spatial", "libero_object", "libero_goal", "libero_10"}:
        raise ValueError("case differs from explicit original-task registration")
    output = Path(row["output_dir"])
    choices = identity(output / "choices.jsonl")
    if choices["sha256"] != row["choices_sha256"]:
        raise ValueError("closed choices SHA changed")
    stages = [json.loads(line) for line in (output / "choices.jsonl").read_text().splitlines()]
    expected_stages = [*row.get("setup", []), *([row["first_attempt"]] if row.get("first_attempt") else [])]
    if stages != expected_stages:
        raise ValueError("choices content differs from closed ledger stages")
    errors, counts = [], Counter(episodes=1, closed_choices_match=1)
    first = row.get("first_attempt")
    summary = {"case": case["name"], "category": case["group"], "phase": case["phase"],
               "episode": case["episode"], "status": row["status"], "choices": choices,
               "wall_s": row["wall_s"], "setup": row.get("setup", []), "errors": errors}
    counts["infrastructure_errors"] += int(row["status"] == "probe_error" or bool(row.get("raised_error")))
    counts["execution_errors"] += sum(int(s.get("receipt", {}).get("verification") == "execution_error"
                                             or bool(s.get("receipt", {}).get("error"))) for s in stages)
    if not first:
        counts["first_attempt_unavailable"] += 1
        summary.update(counts=dict(counts), binding_error=row.get("binding_error"), raised_error=row.get("raised_error"))
        return summary
    expected_tool = case["runtime_tool"]
    if not first["selected"].startswith(expected_tool + "("):
        errors.append("actual selected tool differs from registered runtime tool")
    receipt = first["receipt"]
    expected_profile = "C" if case["group"] in {"bottle", "bowl"} else "B"
    profile = receipt.get("grasp_profile")
    if profile is not None and profile != expected_profile:
        errors.append("actual B/C category profile differs from registration")
    if profile:
        name = next(e["name"] for e in first["public_before"]["entities"] if e["id"] == receipt["object"])
        prompt = (f"pick up the {name} first, then {case['original_instruction']}"
                  if profile == "C" else f"pick up the {name}")
        if receipt.get("contact_prompt") != prompt or receipt.get("contact_max_chunks") != 160:
            errors.append("actual category prompt or max_chunks differs from frozen recipe")
    public = receipt.get("grasp_verified")
    if public not in (True, False, None):
        errors.append("public grasp_verified is not nullable Boolean")
    if public is True and first["held_after"] != receipt["object"]:
        errors.append("verified grasp did not assign public held object")
    if public is not True and first["held_after"] is not None:
        errors.append("unverified grasp assigned public held object")
    counts[f"public_{public}"] += 1
    evidence = first.get("contact_evidence", {})
    sync = evidence.get("private_frame_sync")
    if sync is None or not sync.get("enabled") or sync.get("new_robot_actions") != 0:
        errors.append("registered zero-action synchronous frame metadata missing")
    else:
        states_path = output / "states.json"
        states = json.loads(states_path.read_text())
        steps = {s["step_idx"]: s for s in states["steps"]}
        summary["states"] = identity(states_path)
        for index, sample in enumerate(sync["samples"]):
            step_id = sample["source_step"]
            step = steps[step_id]
            declared = set(step["artifacts"])
            name = f"private_frame_sync_{index:04d}.json"
            meta_path = artifact(output, name, step_id)
            if (name not in declared or str(meta_path) != sample["metadata"]["path"]
                    or identity(meta_path)["sha256"] != sample["metadata"]["sha256"]
                    or json.loads(meta_path.read_text()) != {k: v for k, v in sample.items() if k != "metadata"}):
                errors.append(f"sample {index}: metadata identity/content/declaration mismatch")
            raw, saved = sample["robot_observation"], step["state"]
            if any(not np.array_equal(raw[k], saved[k]) for k in (
                    "robot0_eef_pos", "robot0_eef_quat", "robot0_gripper_qpos")):
                errors.append(f"sample {index}: capture robot pose mismatch")
            times = (sample["private_contact_before_read"]["sim_time"], sample["private_contact"]["sim_time"],
                     sample["sim_time"])
            counts["private_bracket_same_time"] += int(len(set(times)) == 1)
            if sample["same_physics_time"] != (times[0] == times[1]):
                errors.append(f"sample {index}: private bracket-time declaration mismatch")
            reference, instant = sync["pregrasp_reference"], sample["private_contact"]
            clearance = instant["lower_extent_m"] - reference["lower_extent_m"]
            touching = sorted(set(reference["other_contact_geoms"]) & set(instant["other_contact_geoms"]))
            instant_truth = bool(clearance >= .03 and instant["finger_contact"] and not touching)
            if (instant["target"] != case["object_symbol"] or sample["private_clearance_m"] != clearance
                    or sample["touching_original_support_geoms"] != touching
                    or sample["private_contact_clear_instant"] is not instant_truth):
                errors.append(f"sample {index}: private instantaneous label recomputation mismatch")
            frame = sample.get("frame")
            if frame is not None:
                known = set()
                for camera, verdict in frame["per_view"].items():
                    values = list(verdict["conditions"].values())
                    expected = False if False in values else None if None in values else True
                    if verdict["verified"] is not expected:
                        errors.append(f"sample {index}: {camera} nullable Boolean contradiction")
                    if verdict["verified"] is not None:
                        known.add(verdict["verified"])
                if frame["verified"] is not (next(iter(known)) if len(known) == 1 else None):
                    errors.append(f"sample {index}: aggregate nullable Boolean contradiction")
            for camera, view in sample["per_view"].items():
                points = view["points"]
                if points is None:
                    counts[f"{camera}_points_missing"] += 1
                    continue
                point_name = f"private_frame_sync_{index:04d}_{camera}_{points['object_id']}.npz"
                path = artifact(output, point_name, step_id)
                with np.load(path, allow_pickle=False) as data:
                    cloud = data["array"]
                if (point_name not in declared or str(path) != points["path"]
                        or identity(path)["sha256"] != points["sha256"]
                        or hashlib.sha256(cloud.tobytes(order="C")).hexdigest() != points["point_array_sha256"]
                        or list(cloud.shape) != points["shape"] or cloud.dtype.str != points["dtype"]
                        or not np.isfinite(cloud).all()):
                    errors.append(f"sample {index}: {camera} cloud identity mismatch")
                counts["declared_point_arrays"] += 1
            counts["frame_samples"] += 1
            counts[f"instant_private_{sample['private_contact_clear_instant']}"] += 1
            counts[f"instant_public_{sample['frame']['verified'] if sample.get('frame') else None}"] += 1
        hold = first.get("private_setup_hold")
        if hold is None:
            counts["sustained_truth_unknown"] += 1
        else:
            reference, samples, truth = sync["pregrasp_reference"], hold["samples"], hold["truth"]
            support = set(reference["other_contact_geoms"])
            checks = [{"elapsed_s": s["sim_time"] - samples[0]["sim_time"],
                       "clearance_m": s["lower_extent_m"] - reference["lower_extent_m"],
                       "finger_contact": s["finger_contact"],
                       "touching_original_support": bool(support & set(s["other_contact_geoms"]))} for s in samples]
            actual_truth = bool(checks[-1]["elapsed_s"] + 1e-8 >= .5 and all(
                c["clearance_m"] >= .03 and c["finger_contact"] and not c["touching_original_support"] for c in checks))
            if checks != truth["checks"] or actual_truth != truth["success"] or actual_truth != first.get("private_true_sustained_grasp"):
                errors.append("post-receipt sustained truth recomputation mismatch")
            counts[f"sustained_truth_{actual_truth}"] += 1
            bucket = ("TP" if actual_truth else "FP") if public is True else (("FN" if actual_truth else "TN") if public is False else "unknown")
            counts[f"verifier_{bucket}"] += 1
            summary["private_post_receipt_hold"] = {"success": actual_truth, "duration_s": truth["duration_s"],
                                                   "min_clearance_m": truth["min_clearance_m"],
                                                   "diagnostic_actions": hold["diagnostic_actions"]}
    summary.update(receipt=receipt, executed_actions=first["executed_actions"], physically_executed=first["physically_executed"],
                   public_before=first["public_before"], public_after=first["public_after"], counts=dict(counts))
    return summary


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--manifest-sha256", required=True)
    parser.add_argument("--ledger", type=Path, action="append", required=True)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    manifest_id = identity(args.manifest)
    if manifest_id["sha256"] != args.manifest_sha256:
        raise ValueError("registered manifest SHA changed")
    plan = json.loads(args.manifest.read_text())
    if plan["qualification_authorized"] or plan["new_training_rows"]:
        raise ValueError("runtime smoke is not independent confirmation or training")
    registered, seen, cases, total, groups = {c["name"]: c for c in plan["cases"]}, set(), [], Counter(), {}
    ledger_ids = []
    for ledger in args.ledger:
        ledger_ids.append(identity(ledger))
        for line in ledger.read_text().splitlines():
            row = json.loads(line)
            name = row["case"]["name"]
            if name in seen:
                raise ValueError("duplicate closed case")
            seen.add(name)
            result = audit_case(row, registered)
            cases.append(result)
            total.update(result["counts"])
            groups.setdefault(result["category"], Counter()).update(result["counts"])
    args.output.mkdir(parents=True, exist_ok=False)
    report = {"version": "category-runtime-original-smoke-audit/1", "manifest": manifest_id, "ledgers": ledger_ids,
              "source": {name: identity(args.source_root / name) for name in (
                  "robots/libero/v5_runtime.py", "robots/libero/v5_grasp_truth.py", "scripts/probe_v5_skill501_original.py")},
              "registered_cases": len(registered), "closed_cases": len(cases), "unclosed_cases": sorted(set(registered) - seen),
              "counts": dict(total), "by_category": {g: dict(c) for g, c in groups.items()}, "cases": cases,
              "audit_errors": sum(len(c["errors"]) for c in cases), "qualification": False, "training_rows": 0,
              "evidence_limits": ["SAM masks were not enabled; no mask-to-world reconstruction is claimed",
                                  "camera metadata has no independent capture sim_time; private read brackets do not prove pixel timestamps",
                                  "post-receipt private hold is later sustained metrology, never a per-frame label",
                                  "12 smoke cases are not the independent per-category confirmation batch"]}
    path = args.output / "report.json"
    path.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"report": identity(path), "closed_cases": len(cases), "counts": dict(total), "audit_errors": report["audit_errors"]}))


if __name__ == "__main__":
    main()
