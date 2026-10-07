"""Pin one unchanged development state to the actual opt-in scene runtime."""

import argparse
import hashlib
import json
from pathlib import Path


def ref(path):
    path = Path(path).resolve(strict=True)
    return {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--registered-case", type=Path, required=True)
    parser.add_argument("--registered-case-sha", required=True)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--source-archive", type=Path, required=True)
    parser.add_argument("--source-file-list", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    parent_ref = ref(args.registered_case)
    if parent_ref["sha256"] != args.registered_case_sha:
        raise ValueError("registered single development case changed")
    plan = json.loads(args.registered_case.read_text())
    if len(plan["cases"]) != 1 or plan["qualification_authorized"] or plan["confirmation"]:
        raise ValueError("expected one previously registered original development state")
    source_files = args.source_file_list.read_text().splitlines()
    plan["source_snapshot"] = {
        "path": str(args.source), "commit": args.source_commit,
        "archive": ref(args.source_archive),
        "files": [{**ref(args.source / name), "relative_path": name} for name in source_files if name],
    }
    case = plan["cases"][0]
    case["name"] = "place_runtime_identity_" + case["name"].removeprefix("place_trace_")
    condition = plan["conditions"][case["condition"]]
    condition["overrides"]["fixture_fragment_alias_v1"] = True
    condition["overrides"]["record_sam_masks_v6"] = True
    plan.update(
        version="original-runtime-fixture-identity/1-dev",
        producer=ref(__file__), producer_dependencies=[parent_ref, ref(args.source_file_list)],
        runtime_default_changed=False,
        public_trace_contract={
            "version": "public-runtime-identity-observer/1-dev",
            "runtime_path_only": True,
            "drawer_query_source": "MeasuredScene.refresh cabinet query adds independent same-capture drawer query",
            "canonicalization_source": "MeasuredScene.canonicalize_fixture_fragments before public rendering and binding",
            "extra_capture_query_intervention": False,
            "robot_controls_changed": False,
            "thresholds_changed": False,
            "state_fields_added": False,
            "private_inputs_used_for_control": False,
        },
        purpose="Validate actual opt-in runtime fixture identity path on an unchanged visited original development state",
        new_training_rows=0, qualification_authorized=False, new_physical_trials=1,
        run_status="CPU_prepared_not_submitted",
    )
    if args.output.exists():
        raise ValueError("runtime manifest output already exists")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(plan, indent=2) + "\n")
    print(json.dumps({"manifest": ref(args.output), "case": case["name"], "new_gpu_jobs": 0}))


if __name__ == "__main__":
    main()
