"""Pin the next original-only public drawer face-identity investigation."""

import argparse
import hashlib
import json
from pathlib import Path


def ref(path):
    path = Path(path)
    return {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def pinned(item):
    if ref(item["path"])["sha256"] != item["sha256"]:
        raise ValueError("registered explicit input changed")
    return Path(item["path"])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--parent", type=Path, required=True)
    parser.add_argument("--parent-sha", required=True)
    parser.add_argument("--fit-manifest", type=Path, required=True)
    parser.add_argument("--fit-manifest-sha", required=True)
    parser.add_argument("--validation-report", type=Path, required=True)
    parser.add_argument("--validation-report-sha", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    parent = json.loads(pinned({"path": str(args.parent), "sha256": args.parent_sha}).read_text())
    fit = json.loads(pinned({"path": str(args.fit_manifest), "sha256": args.fit_manifest_sha}).read_text())
    validation = json.loads(pinned({"path": str(args.validation_report), "sha256": args.validation_report_sha}).read_text())
    predictions = [json.loads(line) for line in pinned(validation["predictions"]).read_text().splitlines()]
    cases = {case["state_sha256"]: case for case in parent["cases"]}
    failed = [row for row in predictions if row["mode"] == "close"
              and row["private_label_for_offline_analysis"] is not None
              and row["class_at_fixed_095"] != bool(row["private_label_for_offline_analysis"])]
    failure_refs = [{"sample_id": row["sample_id"], "group": row["raw_state_sha256"],
                     "episode": cases[row["raw_state_sha256"]]["episode"],
                     "failure": "false_stop" if row["class_at_fixed_095"] else "missed_endpoint",
                     "p_satisfied": row["p_satisfied"], "diagnostic_only": True} for row in failed]
    # Development investigations may reuse the observed validation failure,
    # but then it is consumed for development and never a fresh qualification.
    wanted = [{"suite": "libero_90", "task": 23, "seed": 20},
              {"suite": "libero_90", "task": 22, "seed": 30},
              {"suite": "libero_90", "task": 0, "seed": 20}]
    selected = []
    for episode in wanted:
        case = next(case for case in parent["cases"] if case["type"] == "drawer_close"
                    and case["episode"] == episode)
        selected.append({key: case[key] for key in ("name", "episode", "state_sha256", "mode", "bddl", "init_file")})
    output = {"version": "drawer-public-face-identity-tracking/1-dev",
        "producer": ref(__file__), "parent_manifest": ref(args.parent),
        "fixed_fit_manifest": ref(args.fit_manifest), "validation_report": ref(args.validation_report),
        "failure_diagnosis": failure_refs, "development_cases": selected,
        "case_purpose": "static-face substitution, contact endpoint loss, and missing-face evidence; visited development states only",
        "validation_consumed_for_next_development": True,
        "fresh_qualification_authorized": False, "runtime_admission": False,
        "new_physical_trials": 0, "gpu_submitted": False,
        "input_contract": {"cameras": ["agentview", "wrist"], "capture_every_completed_contact_chunk": 1,
            "files": ["raw RGB", "calibrated public world pointcloud", "selected moving-face measured cloud",
                      "fixed-frame measured cloud", "public EEF XYZ and gripper opening"],
            "crop_source": "before-contact measured selected drawer band + cabinet bounds and measured outward axis",
            "current_SAM_part_id_is_not_identity_evidence": True,
            "private_joint_or_goal_features": False,
            "after_endpoint_sampling": "six neutral controls preserving gripper target then a fresh second capture"},
        "public_tracking_proposal": {"reference": "persist first measured selected front-face points and appearance before contact",
            "match": "appearance correspondences from before/recent panel RGB projected into measured 3D; seek only current candidates supported by those correspondences",
            "motion_model": "rigid translation along measured cabinet outward axis; fixed cabinet border must remain stationary",
            "identity_checks": ["matches span the measured panel rather than only handle/arm",
                "tangent and vertical coordinates agree with reference panel",
                "temporal correspondence chain remains continuous across completed blocks",
                "both camera tracks agree when both are measurable",
                "candidate without sufficient matched panel pixels remains unmeasured"],
            "fit_procedure": "train-only selection data set all matching/coverage/noise thresholds before evaluating a new untouched state split",
            "pixel_texture_limitation": "white drawer panels may have too little texture; do not invent correspondence or turn pose continuity alone into proof",
            "fallback": "measured handle/edge correspondence and a part-focused public temporal encoder may be investigated on training states; no val tuning on this consumed six-state set"},
        "private_label_contract": {"source": "requested endpoint joint predicate",
            "storage": "separate private_labels.jsonl keyed by sample_id", "controller_access": False,
            "score_after_public_inputs_fixed": True},
        "training_boundary": "LIBERO90 selection frames only for endpoint diagnostic; never enter robot-decider training or change 40-task collection boundary",
        "gate": "do not admit new close verifier until new state-disjoint confirmation meets original 95% agreement and reports both error directions"}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x") as file:
        file.write(json.dumps(output, indent=2)+"\n")
    print(json.dumps({"protocol": ref(args.output), "failed_close_frames": len(failed),
                      "development_cases": [case["episode"] for case in selected]}))


if __name__ == "__main__":
    main()
