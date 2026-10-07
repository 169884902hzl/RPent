"""Audit the real opt-in runtime single-case execution, without relabeling."""

import argparse
import json
from pathlib import Path

from analyze_place_remaining7 import checked, inspect_job, reference


SOURCE = "/public/home/sunyihan/rpent_libero_eval/source_v5_place_runtime_identity_r1_20261008"
MANIFEST = "/public/home/sunyihan/rpent_libero_eval/results/harness_v5/place4311_public_trace_CPU_20261008/preparation_runtime_identity_r1/registered/case0_runtime_identity_t25_s2.json"
MANIFEST_SHA = "3eb0eacbfb00a993d7da55f4e7af1750c43a56fcfc5378fbaf51078e765f85ce"
BASE = "/public/home/sunyihan/rpent_libero_eval/results/harness_v5/place_runtime_identity_dev_20261008/case0"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    submission_ref = {"path": BASE + "/submission_once.json", "sha256": "e2173913d192c0414fd87032888927f155630d4c58f8d143e6a3768ab8fc2182"}
    submission = json.loads(checked(submission_ref).read_text())
    if str(submission["job_id"]) != "4555":
        raise ValueError("expected the actually submitted runtime job")
    manifest_ref = {"path": MANIFEST, "sha256": MANIFEST_SHA}
    manifest = json.loads(checked(manifest_ref).read_text())
    snapshot = manifest["source_snapshot"]
    if snapshot["path"] != SOURCE or snapshot["commit"] != "a5e7aeae9829a6626be138f5695a8e91b33b5044":
        raise ValueError("runtime source differs from the registered package")
    checked(snapshot["archive"])
    for item in snapshot["files"]:
        checked(item)
    case = manifest["cases"][0]
    overrides = manifest["conditions"][case["condition"]]["overrides"]
    if overrides["fixture_fragment_alias_v1"] is not True or overrides["record_sam_masks_v6"] is not True:
        raise ValueError("runtime switch or mask recording was not registered")
    result = inspect_job({
        "job_id": "4555", "case_number": 0, "case_name": case["name"],
        "episode": case["episode"], "state_sha256": case["state_sha256"],
        "condition": case["condition"], "output_dir": BASE + "/job4555",
        "episodes_file": BASE + "/job4555/episodes.jsonl",
    })
    if result["readiness"] != "completed_record_present":
        raise ValueError("runtime job has no complete result yet")
    if result["target_environment_controls"] != 800 or result["target_vla_chunks"] != [5] * 160:
        raise ValueError("actual target complete chunks differ from the original registered 160 by 5 budget")
    all_frames = []
    for attempt in result["public_attempts"]:
        for frame in attempt["public_trace"]["frames"]:
            raw = json.loads(checked(frame["reference"]).read_text())
            if raw["runtime_identity_path_only"] is not True or raw["extra_capture_query_intervention"] is not False:
                raise ValueError("the physical evidence was collected through an extra-observation intervention")
            all_frames.append(frame)
    episode = json.loads(checked(result["episodes"]).read_text())
    before = episode["first_attempt"]["public_before"]["entities"]
    measured_cabinets = [entity for entity in before if entity["name"] == "cabinet" and entity["visible"]]
    measured_tops = [entity for entity in before if entity["name"] == "cabinet top surface" and entity["visible"]]
    if len(measured_cabinets) != 1 or len(measured_tops) != 1:
        raise ValueError("actual pre-action public identity remains ambiguous")
    result.update(
        schema="place4555-actual-runtime-fixture-identity-audit/1-dev",
        submission=submission_ref, manifest=manifest_ref,
        source_commit=snapshot["commit"], source_files_sha_checked=len(snapshot["files"]),
        analyzer=reference(Path(__file__)),
        pre_action_visible_cabinet_ids=[entity["id"] for entity in measured_cabinets],
        pre_action_visible_measured_top_ids=[entity["id"] for entity in measured_tops],
        pre_action_public_entities=before,
        runtime_path_only_public_frames=len(all_frames),
        extra_capture_query_intervention=False,
        runtime_scene_switch_explicitly_enabled=True,
        runtime_scene_switch_global_default=False,
        actual_opt_in_runtime_path_physically_exercised=True,
        qualification_authorized=False, old_results_changed=False,
        training_allowed=False, new_training_rows=0,
        meaning="one reused original development state verifies real scene-owner binding and target execution, not a global skill qualification",
    )
    encoded = json.dumps(result, indent=2) + "\n"
    if args.output.exists() and args.output.read_text() != encoded:
        raise ValueError("immutable runtime audit already differs")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(encoded)
    print(json.dumps({"report": str(args.output), "sha256": reference(args.output)["sha256"],
                      "target": result["target_selected"], "target_environment_controls": result["target_environment_controls"],
                      "public": result["target_public_place_verified"], "private_after": result["private_after_satisfied"],
                      "wall_s": result["case_wall_s"], "public_frames": len(all_frames)}))


if __name__ == "__main__":
    main()
