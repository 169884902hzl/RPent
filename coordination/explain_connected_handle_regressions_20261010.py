"""Explain preserved pan regressions from closed evidence, without rescoring."""
import argparse
import hashlib
import json
from pathlib import Path


def pin(path):
    return {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def extract(parent, method):
    rows, cache = {}, {}
    for row in map(json.loads, (parent / "rows.jsonl").open()):
        if row["type"] != "grasp_frypan" or row["layout_seed"] not in (9301401, 9301410):
            continue
        if method not in row["group"]:
            continue
        path = Path(row["input"])
        if path not in cache:
            if pin(path)["sha256"] != row["input_sha256"]:
                raise ValueError("closed physical evidence changed")
            cache[path] = list(map(json.loads, path.open()))
        raw = cache[path][row["line"] - 1]
        first = raw.get("first_attempt") or {}
        receipt = first.get("receipt") or {}
        truth = first.get("private_hold_truth_v3") or {}
        checks = truth.get("checks") or []
        if not checks or type(row["registered_v3"]) is not bool:
            raise ValueError("known locked-v3 physical evidence required")
        rows[row["layout_seed"]] = {
            "case": row["case"], "state_sha256": row["state_sha256"],
            "physical_input": {**pin(path), "line": row["line"]},
            "registered_v3": row["registered_v3"], "public": row["public"],
            "plan": receipt.get("analytic_grasp_plan"),
            "restore_max_absolute_error": (raw.get("private_registered_reset_evidence") or {}).get(
                "restore_max_absolute_error"),
            "hold_frames": len(checks),
            "dual_contact_frames": sum(c.get("dual_finger_contact") is True for c in checks),
            "clearance_min_m": min(c["clearance_m"] for c in checks),
            "clearance_max_m": max(c["clearance_m"] for c in checks),
            "maximum_relative_tcp_slip_m": max(c.get("relative_com_displacement_m", 0.) for c in checks),
            "required_clearance_m": truth["required_clearance_m"],
            "private_diagnostic_only": True,
        }
    if set(rows) != {9301401, 9301410}:
        raise ValueError("both preserved regressions required")
    return rows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--before", type=Path, required=True)
    parser.add_argument("--after", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    before = extract(args.before, "servo_only")
    after = extract(args.after, "connected_handle")
    rows = []
    for seed in sorted(before):
        a, b = before[seed], after[seed]
        if a["state_sha256"] != b["state_sha256"]:
            raise ValueError("registered initial states differ")
        rows.append({"layout_seed": seed, "before": a, "after": b,
            "cause_supported_by_locked_v3": "whole_pan_bottom_not_clear_of_original_support_plane",
            "limits": "Dual contact and low slip alone do not establish whole-object lift. A 10cm TCP lift does not establish 3cm clearance of the pan's bottom.",
            "runtime_remedy_to_test": "Measure the pan body after lift; refine contact near the handle root and compare a lift that checks public bottom clearance. No private coordinate or label may select a pose.",
            "training_allowed": False, "qualification_allowed": False})
    args.output.mkdir(parents=True, exist_ok=False)
    records = args.output / "rows.jsonl"
    records.write_text("".join(json.dumps(row) + "\n" for row in rows))
    manifest = {"producer": pin(Path(__file__)), "records": pin(records),
        "before": pin(args.before / "rows.jsonl"), "after": pin(args.after / "rows.jsonl"),
        "n": len(rows), "labels_unchanged": True,
        "private_evidence_usage": "diagnosis only, never runtime control",
        "training_allowed": False, "qualification_allowed": False}
    (args.output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps({"n": len(rows), "records": pin(records)}))


if __name__ == "__main__":
    main()
