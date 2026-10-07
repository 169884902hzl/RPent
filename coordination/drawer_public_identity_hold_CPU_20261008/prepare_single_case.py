"""Prepare the already-visited t23/s20 original drawer identity smoke."""

import argparse
import copy
import hashlib
import json
from pathlib import Path


def ref(path):
    path = Path(path).resolve(strict=True)
    return {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--parent", type=Path, required=True)
    parser.add_argument("--parent-sha", required=True)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--source-archive", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    parent_ref = ref(args.parent)
    if parent_ref["sha256"] != args.parent_sha:
        raise ValueError("original registered parent changed")
    plan = json.loads(args.parent.read_text())
    old = [case for case in plan["cases"] if case["type"] == "drawer_close"
           and case["episode"] == {"suite": "libero_90", "task": 23, "seed": 20}]
    if len(old) != 1 or plan["cohort"] != "selection" or plan["qualification_authorized"]:
        raise ValueError("expected the single already-visited original drawer identity failure")
    old = old[0]
    method = "native_public_endpoint_hold_v9_160"
    condition = copy.deepcopy(plan["conditions"][old["condition"]])
    condition["overrides"].update(drawer_public_stop_v6=True, drawer_endpoint_hold_v9=True)
    condition["private_fixture_sync"] = True
    case = copy.deepcopy(old)
    case.update(name="drawer_endpoint_hold_v9_t23_s20", condition=method, parent_case_name=old["name"])
    snapshot = copy.deepcopy(plan["source_snapshot"])
    snapshot.update(path=str(args.source), commit=args.source_commit, archive=ref(args.source_archive))
    for item in snapshot["files"]:
        item.update(ref(args.source / item["relative_path"]))
    new_relative = "robots/libero/v5_drawer_endpoint_hold.py"
    if not any(item["relative_path"] == new_relative for item in snapshot["files"]):
        snapshot["files"].append({**ref(args.source / new_relative), "relative_path": new_relative})
    plan.update(version="drawer-public-endpoint-hold/9-dev", cases=[case], cases_count=1,
        conditions={method: condition}, source_snapshot=snapshot, parent_manifest=parent_ref,
        producer=ref(__file__), producer_dependencies=[parent_ref],
        preregistered_requests_by_type_arm={"drawer_close/" + method: 1},
        purpose="Public face-identity abstention smoke; collect every-block public RGB-D/proprioception",
        qualification_authorized=False, new_training_rows=0, new_physical_trials=0,
        run_status="CPU_prepared_not_submitted", state_repetition="same visited original t23/s20; not confirmation",
        public_stop_contract={"poll_every_chunks": 1, "neutral_hold_controls": 6,
            "control_dt_s": .05, "gripper_command": "zero_delta_preserves_actuator_target",
            "close_admission": "unmeasured until public moving-face identity verifier is qualified",
            "open_threshold_m": .141, "close_geometry_threshold_m": .0005,
            "second_frame_required": "new source_step, current endpoint, stable fixed frame and <=5mm panel drift",
            "private_inputs_used_for_control": False})
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x") as handle:
        handle.write(json.dumps(plan, indent=2) + "\n")
    print(json.dumps({"manifest": ref(args.output), "case": case["name"], "source": snapshot["commit"],
                      "new_gpu_jobs": 0, "qualification_authorized": False}))


if __name__ == "__main__":
    main()
