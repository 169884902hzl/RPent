"""Audit only the two explicit original-LIBERO microwave reports and ledgers."""

import argparse
import ast
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import subprocess


REMOTE_ROOT = Path("/public/home/sunyihan/rpent_libero_eval")
REPORTS = {
    4128: ("20261006T134800Z", "cdb013ac1d9e70236db1836b1a39f9b12c453b5e9448cc45c85dda3c0f76c668"),
    4178: ("20261006T142400Z", "6bb8dddbf4aacd6df9f10b4633582cece4bb000667d325a2e2aca7ed875cf365"),
}
FIXED_COMMIT = "8fe6b188bac4d233f4c4d632a38d6dc5f724f583"
FLAGS = (
    "fixture_part_visibility_v2", "fixture_endpoint_geometry_v3",
    "microwave_recall_geometry_v3", "microwave_instance_geometry_v4",
    "appliance_support_crop_v5", "microwave_door_cloud_v6",
    "door_point_recall_v7", "door_plane_consensus_v1", "dual_view_fusion_v1",
)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def local(root, remote):
    return root / Path(remote).relative_to(REMOTE_ROOT)


def stage(stage):
    if not stage:
        return None
    receipt = stage.get("receipt") or {}
    motions = stage.get("motion_evidence", [])
    chunks = [m for m in motions if m.get("name") == "vla_act_chunk"]
    scene = stage.get("public_before") or {}
    return {
        "selected": stage.get("selected"),
        "entities": [e for e in scene.get("entities", []) if "microwave" in e["name"]],
        "public_after_entities": [e for e in (stage.get("public_after") or {}).get("entities", [])
                                  if "microwave" in e["name"]],
        "private_before": stage.get("private_before"),
        "private_after": stage.get("private_after"),
        "vla_requested_controls": sum(m.get("requested_action_count", 0) for m in chunks),
        "vla_executed_controls": sum(m.get("executed_action_count", 0) for m in chunks),
        "vla_short_chunks": sum(m.get("executed_action_count", 0) < m.get("requested_action_count", 0)
                                for m in chunks),
        "non_vla_servo_controls": sum(m.get("actions_used", 0) for m in motions
                                      if m.get("name") != "vla_act_chunk"),
        "receipt": {k: v for k, v in receipt.items() if k != "fixture_handle_approach"},
        "handle_approach": compact_approach(receipt.get("fixture_handle_approach") or {}),
        "verification_measurements": stage.get("verification_measurements"),
    }


def compact_approach(value):
    # Large motion/contact traces remain in the explicitly hashed raw ledger.
    result = {k: v for k, v in value.items() if k != "waypoints"}
    result["waypoints"] = [
        {"target_xyz": row.get("target_xyz"), "motion": {
            k: v for k, v in (row.get("motion") or {}).items() if k != "trajectory"}}
        for row in value.get("waypoints", [])
    ]
    return result


def audit(root):
    results = {}
    for job, (stamp, expected) in REPORTS.items():
        report_path = root / f"results/harness_v5/skill549_live_CPU_20261006/{stamp}/job{job}/report.json"
        assert sha(report_path) == expected
        report = json.loads(report_path.read_text())
        manifest_ref = report["manifests"][0]
        manifest_path = local(root, manifest_ref["path"])
        assert sha(manifest_path) == manifest_ref["sha256"]
        manifest = json.loads(manifest_path.read_text())
        groups, records = defaultdict(Counter), []
        for ref in report["ledgers"]:
            path = local(root, ref["path"])
            assert sha(path) == ref["sha256"]
            for number, line in enumerate(path.read_text().splitlines(), 1):
                raw = json.loads(line)
                case = raw["case"]
                if not case["type"].startswith("microwave_"):
                    continue
                first = stage(raw.get("first_attempt"))
                setup = [stage(item) for item in raw.get("setup", [])]
                counter = groups[case["type"] + "/" + case["condition"]]
                counter["registered"] += 1
                reason = (first or {}).get("receipt", {}).get("failure_reason") or raw["status"]
                counter["status:" + reason] += 1
                if first:
                    requested = first["vla_requested_controls"]
                    executed = first["vla_executed_controls"]
                    counter["first_vla_requested_controls"] += requested
                    counter["first_vla_executed_controls"] += executed
                    counter["first_vla_short_chunks"] += first["vla_short_chunks"]
                    counter["first_vla_contact_cases"] += executed > 0
                    counter["first_servo_only_cases"] += executed == 0 and first["non_vla_servo_controls"] > 0
                    counter["first_endpoint_true"] += (first.get("private_after") or {}).get("satisfied") is True
                    counter["first_endpoint_false"] += (first.get("private_after") or {}).get("satisfied") is False
                    counter["public_null_on_executed"] += executed > 0 and first["receipt"].get("articulate_verified") is None
                at_stop = raw.get("public_at_stop") or {}
                records.append({
                    "case": case["name"], "episode": case["episode"], "type": case["type"],
                    "condition": case["condition"], "state_sha256": case["state_sha256"],
                    "status": raw["status"], "binding_error": raw.get("binding_error"),
                    "public_at_stop_entities": [e for e in at_stop.get("entities", []) if "microwave" in e["name"]],
                    "setup": setup, "first": first,
                    "ledger": ref["path"], "ledger_sha256": ref["sha256"], "line": number,
                    "trajectory": raw["output_dir"] + "/choices.jsonl",
                    "trajectory_sha256": raw.get("choices_sha256"),
                    "server_chunk_execution": raw.get("server_chunk_execution"),
                })
        assert len(records) == (400 if job == 4128 else 10)
        results[str(job)] = {
            "report": str(report_path), "report_sha256": expected,
            "source": report["source"], "manifest": manifest_ref,
            "explicit_flag_overrides": {
                key: {flag: value.get("overrides", {}).get(flag, "not_explicitly_set") for flag in FLAGS}
                for key, value in manifest["conditions"].items()
            },
            "groups": {key: dict(value) for key, value in groups.items()},
            "records": records,
        }
    code = subprocess.check_output(["git", "show", FIXED_COMMIT + ":robots/libero/v5_runtime.py"],
                                   cwd=root, text=True)
    parsed = ast.parse(code)
    scene = next(n for n in parsed.body if isinstance(n, ast.ClassDef) and n.name == "MeasuredScene")
    init = next(n for n in scene.body if isinstance(n, ast.FunctionDef) and n.name == "__init__")
    defaults = {a.arg: ast.literal_eval(d) for a, d in zip(init.args.kwonlyargs, init.args.kw_defaults)
                if a.arg in FLAGS and d is not None}
    v9_manifest_path = root / "results/harness_v5/place_observe_retreat_v9_CPU_20261006/preparation/registered/observe_retreat_v9_same40_category_selection.json"
    assert sha(v9_manifest_path) == "76f4f8db4c6e3581af275bbe4823a9918193188fa6d8549e6872921fdd04900d"
    v9_manifest = json.loads(v9_manifest_path.read_text())
    return {
        "scope": "CPU read-only analysis of explicit original-LIBERO selection records; no PRO, replay, training, qualification or shared runtime change",
        "jobs": results,
        "fixed_place_v9_source": {
            "commit": FIXED_COMMIT, "runtime_sha256": hashlib.sha256(code.encode()).hexdigest(),
            "MeasuredScene_keyword_defaults": defaults,
            "manifest_sha256": sha(v9_manifest_path),
            "explicit_flag_overrides": {
                key: {flag: value.get("overrides", {}).get(flag, "not_explicitly_set") for flag in FLAGS}
                for key, value in v9_manifest["conditions"].items()
            },
            "scope": "place-specialized snapshot only; absence of flags here is not a claim about all current harness configurations",
        },
        "new_physical_trials": 0, "new_training_rows": 0, "qualification_authorized": False,
        "script_sha256": sha(Path(__file__)),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = audit(args.root.resolve())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"output": str(args.output), "sha256": sha(args.output),
                      "groups": {job: value["groups"] for job, value in result["jobs"].items()}}))


if __name__ == "__main__":
    main()
