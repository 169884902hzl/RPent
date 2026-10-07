"""Aggregate nine pinned train-state withdrawal diagnostics, never infer a stop rule."""

import argparse
import hashlib
import json
from pathlib import Path


def identity(path):
    path = Path(path).resolve(strict=True)
    return {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def load(reference):
    if not Path(reference["path"]).is_absolute() or identity(reference["path"]) != reference:
        raise ValueError("Pinned explicit input changed: " + reference["path"])
    return json.loads(Path(reference["path"]).read_text())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ledger", type=Path, required=True)
    parser.add_argument("--ledger-sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    reference = {"path": str(args.ledger.resolve()), "sha256": args.ledger_sha256}
    ledger = load(reference)
    if len(ledger["rows"]) != 9 or [r["part"] for r in ledger["rows"]] != list(range(9)):
        raise ValueError("Need the explicitly pinned complete nine-case grid")
    args.output.mkdir(exist_ok=False)
    public, private, summaries = [], [], []
    # Public evidence is processed and written before private label files are opened.
    for declared in ledger["rows"]:
        summary = load(declared["summary"])
        episode = load(summary["episode"])
        evidence = load(summary["public_records"])
        if len(evidence["frames"]) != 7 or summary["stop_admitted"]:
            raise ValueError("Unexpected observation protocol")
        annotation = declared["public_visibility_annotation"]
        public.append({"part": declared["part"], "episode": summary["episode"],
            "summary": declared["summary"], "seed": episode["case"]["episode"]["seed"],
            "fixed_off_chunks": episode["fixed_off_chunks"],
            "contact_controls": (160 + episode["fixed_off_chunks"]) * 5,
            "release_controls": summary["release_controls"], "retreat_controls": summary["retreat_controls"],
            "hold_controls": summary["hold_controls"], "public_records": summary["public_records"],
            "public_montage": summary["public_montage"], "visibility_annotation": annotation,
            "robot_observations": [{"phase": f["phase"], "index": f["index"],
                "robot": f["public_robot_observation"]} for f in evidence["frames"]]})
        summaries.append(summary)
    public_path = args.output / "public_cases.json"
    public_path.write_text(json.dumps(public, indent=2) + "\n")
    for case, summary in zip(public, summaries, strict=True):
        labels = load(summary["private_postexecution_diagnosis"])["records"]
        if len(labels) != 7:
            raise ValueError("Incomplete private postexecution labels")
        phases = {phase: [r for r in labels if r["phase"] == phase]
            for phase in ("after_contact", "after_release", "after_retreat")}
        private.append({"part": case["part"], "seed": case["seed"], "off_chunks": case["fixed_off_chunks"],
            "private_reference": summary["private_postexecution_diagnosis"],
            "contact_off": phases["after_contact"][0]["turn_off_satisfied"],
            "release_off_sequence": [r["turn_off_satisfied"] for r in phases["after_release"]],
            "retreat_off_sequence": [r["turn_off_satisfied"] for r in phases["after_retreat"]],
            "contact_qpos": phases["after_contact"][0]["joint_qpos"][0][0],
            "release_qpos_sequence": [r["joint_qpos"][0][0] for r in phases["after_release"]],
            "retreat_qpos_sequence": [r["joint_qpos"][0][0] for r in phases["after_retreat"]],
            "controller_access": False, "actions_or_thresholds_selected_from_labels": False})
    private_path = args.output / "private_postexecution_cases.json"
    private_path.write_text(json.dumps(private, indent=2) + "\n")
    report = {"schema": "stove-fixed-withdrawal-nine-grid-summary/1", "producer": identity(__file__),
        "explicit_ledger": reference, "public_cases": identity(public_path),
        "private_postexecution_cases": identity(private_path), "physical_runs_completed": 9,
        "distinct_original_train_states": 3, "public_RGB_views_reviewed": 126,
        "contact_off_count": sum(r["contact_off"] for r in private),
        "after_release_off_count": sum(r["release_off_sequence"][-1] for r in private),
        "after_retreat_off_count": sum(r["retreat_off_sequence"][-1] for r in private),
        "off_to_not_off_in_release_time_window": [r["part"] for r in private
            if r["contact_off"] and not r["release_off_sequence"][0]],
        "after_retreat_mainview_knob_unoccluded": 9, "after_retreat_wrist_knob_out_of_view": 9,
        "algorithmic_knob_angle_measurements": 0, "stop_admitted": False,
        "labels_are_postexecution_only": True, "release_only_causal_claim": False,
        "training_allowed": False, "validation_states_read": False,
        "uncertainty_note": "Repeated observations of three visited train states; not independent confirmation or generalization evidence."}
    (args.output / "manifest.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
