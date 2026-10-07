"""Pin eight independent one-decision original-development trace manifests."""

import argparse
import copy
import hashlib
import json
from pathlib import Path


CASES = [
    "place548_place_on_libero_90_t25_s2_r0_place_vla_subtask160",
    "place548_place_on_libero_90_t25_s4_r0_place_vla_subtask160",
    "place548_place_in_libero_90_t24_s3_r0_place_vla_subtask160",
    "place548_place_on_libero_90_t10_s2_r0_place_current160",
    "place548_place_on_libero_90_t10_s2_r0_place_vla_subtask160",
    "place548_place_on_libero_90_t25_s1_r0_place_current160",
    "place548_place_on_libero_90_t25_s2_r0_place_current160",
    "place548_place_on_libero_90_t25_s0_r0_place_current160",
]


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
    parser.add_argument("--source-file-list", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    parent_ref = ref(args.parent)
    if parent_ref["sha256"] != args.parent_sha:
        raise ValueError("registered 4311 parent changed")
    parent = json.loads(args.parent.read_text())
    if parent["cohort"] != "selection" or parent["qualification_authorized"]:
        raise ValueError("expected already-visited original-development parent")
    files = [line for line in args.source_file_list.read_text().splitlines() if line]
    identity = {"path": str(args.source), "commit": args.source_commit,
                "archive": ref(args.source_archive),
                "files": [{**ref(args.source / name), "relative_path": name} for name in files]}
    args.output.mkdir(parents=True, exist_ok=False)
    manifests, exclusions = [], []
    for index, name in enumerate(CASES):
        old = next(case for case in parent["cases"] if case["name"] == name)
        case = copy.deepcopy(old)
        case.update(name="place_trace_" + name.removeprefix("place548_"), parent_case_name=name,
                    training_allowed=False, reservation_scope="permanent_original_development_diagnostic_exclusion")
        condition = copy.deepcopy(parent["conditions"][old["condition"]])
        condition["overrides"]["record_sam_masks_v6"] = True
        plan = copy.deepcopy(parent)
        plan.update(version="original-public-placement-trace/1-dev", cases=[case], cases_count=1,
                    conditions={case["condition"]: condition}, source_snapshot=identity,
                    parent_manifest=parent_ref, producer=ref(__file__),
                    producer_dependencies=[parent_ref, ref(args.source_file_list)],
                    qualification_authorized=False, new_training_rows=0,
                    permanent_training_exclusion=True,
                    public_trace_contract={
                        "version": "public-placement-carry-trace/1-dev",
                        "same_capture_additional_query": "drawer",
                        "canonicalization": "unique independent current drawer same-volume plus unique current cabinet; no blanket stale-peer deletion",
                        "carry_observation": "new public capture and object query after existing move_to segments; no new robot controls",
                        "persist": ["actual SAM masks", "per-view segmented clouds", "fused clouds",
                                    "EEF XYZ and body quaternion", "held_offset", "camera files and source_step"],
                        "private_inputs_used_for_control": False,
                        "old_scores_changed": False,
                        "thresholds_changed": False},
                    purpose="Original single-decision public evidence for remaining4311 binding/footprint roots; no confirmation or training",
                    run_status="CPU_prepared_not_submitted")
        output = args.output / f"case{index}_{old['condition']}_t{old['episode']['task']}_s{old['episode']['seed']}.json"
        output.write_text(json.dumps(plan, indent=2) + "\n")
        manifests.append({**ref(output), "case": case["name"], "case_index": index,
                          "episode": case["episode"], "state_sha256": case["state_sha256"]})
        exclusions.append({"episode": case["episode"], "state_sha256": case["state_sha256"],
                           "bddl": case["bddl"], "init_file": case["init_file"], "source_manifest": ref(output),
                           "registered_identity": "original_development_diagnostic",
                           "permanent_training_exclusion": True, "all_derived_snapshots_excluded": True})
    registry = args.output / "permanent_training_exclusion_registry.json"
    registry.write_text(json.dumps({"version": "explicit-skill-state-exclusion/1",
        "complete_global_registry": False, "scope": "only eight known original4311 development decisions",
        "states": exclusions, "source": parent_ref}, indent=2) + "\n")
    index = args.output / "manifest_index.json"
    index.write_text(json.dumps({"manifests": manifests, "exclusion_registry": ref(registry),
                                "new_GPU_jobs": 0}, indent=2) + "\n")
    print(json.dumps({"index": ref(index), "case_manifests": len(manifests), "exclusions": ref(registry)}))


if __name__ == "__main__":
    main()
