"""Prepare the original registered 10 microwave states with public-parent binding."""

import argparse
from collections import Counter
import copy
import hashlib
import json
from pathlib import Path


SOURCE = Path("/public/home/sunyihan/rpent_libero_eval/source_v5_drawer571_20261006")
COMMIT = "5da67d19fe8dde8564e06c39266bb1fedc330d2a"
ARCHIVE_SHA = "41afc849c146eae7db2220960d2057da95c03fba23465b15fa61d0caa7bed718"
PARENT_SHA = "8db78a69313c4b85468887a60cc103506119313c16a73940070d051e86eb43c6"
METHOD = "public_parent_current160"


def ref(path):
    path = Path(path).resolve(strict=True)
    return {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--parent", type=Path, required=True)
    parser.add_argument("--expected-source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not all(p.is_absolute() for p in (args.parent, args.expected_source, args.output)):
        parser.error("manifest input/output paths must be absolute")
    parent_ref = ref(args.parent)
    if parent_ref["sha256"] != PARENT_SHA:
        raise ValueError("only pinned4178 original30 parent is registered")
    parent = json.loads(args.parent.read_text())
    expected = json.loads(args.expected_source.read_text())
    if expected["commit"] != COMMIT or len(expected["files"]) != 24:
        raise ValueError("expected24 source identity changed")
    files = []
    for item in expected["files"]:
        checked = ref(SOURCE / item["relative_path"])
        if checked["sha256"] != item["sha256"]:
            raise ValueError("source snapshot differs from fixed commit: " + item["relative_path"])
        files.append({**checked, "relative_path": item["relative_path"]})
    archive = ref(str(SOURCE) + ".tar")
    if archive["sha256"] != ARCHIVE_SHA:
        raise ValueError("fixed code-only source archive changed")
    original = [c for c in parent["cases"] if c["type"] in ("microwave_open", "microwave_close")]
    if Counter(c["type"] for c in original) != {"microwave_open": 5, "microwave_close": 5}:
        raise ValueError("parent must retain original five open and five close cases")
    condition = copy.deepcopy(parent["conditions"]["measured_fixture_handle160"])
    condition.update(executor="current", contact_approach="none",
                     contact_prompt_source="registered_original_subtask", observation_pose_v1=False)
    if condition["max_chunks"] != 160 or condition["overrides"]["dual_view_fusion_v1"] is not True:
        raise ValueError("same complete160 budget and dual-view measurement required")
    cases = []
    for old in original:
        if (old["object_category"] != "microwave" or old["kind"] != "articulate"
                or old["subtask_prompt"] != old["mode"] + " the microwave"):
            raise ValueError("original public microwave template changed")
        case = copy.deepcopy(old)
        case.update(name=old["name"].removesuffix("_measured_fixture_handle160") + "_" + METHOD,
                    condition=METHOD, parent_case_name=old["name"])
        for key in ("episode", "setup", "state_sha256", "official_init_index", "mode", "type",
                    "object_symbol", "object_category", "bddl", "init_file", "subtask_prompt", "original_instruction"):
            if case[key] != old[key]:
                raise ValueError("registered original identity changed: " + key)
        cases.append(case)
    packet = Path(__file__).resolve().parent
    adapter = ref(packet / "probe_v5_microwave_public571.py")
    launcher = ref(packet / "run_v5_microwave_public571.sbatch")
    plan = copy.deepcopy(parent)
    plan.update(version="original-microwave-public-parent571/1-dev", purpose="public-parent plus current160 no-prehandle joint method selection",
                cohort="selection", cases=cases, conditions={METHOD: condition}, parent_manifest=parent_ref,
                producer=ref(__file__), producer_dependencies=[parent_ref, ref(args.expected_source), adapter, launcher],
                adapter=adapter, launcher=launcher,
                source_snapshot={"path": str(SOURCE), "commit": COMMIT, "files": files, "archive": archive},
                selection="all original4178 microwave cases in original ordering; no outcome filtering",
                confirmation="none; previously visited selection states never grant qualification",
                pairing="same original10 episodes/raw states/setup/prompts; policy RNG not paired, joint recipe changed",
                preregistered_requests_by_type_arm={"microwave_open/" + METHOD: 5, "microwave_close/" + METHOD: 5},
                qualification_authorized=False, new_training_rows=0, new_physical_trials=0, run_status="prepared_not_submitted",
                skill_chunk_contract={"controls_per_requested_chunk": 5, "native_success_stops_chunk": False,
                                      "private_joint_or_predicate_used_for_control": False, "external_budget": 10000},
                public_parent_contract={"required": "exactly one current visible measured microwave parent",
                    "missing_or_duplicate": "retain public_binding_missing; do not synthesize door/handle/geometry",
                    "instruction": "registered original public open/close the microwave sentence only",
                    "measurement": "actual agentview+wrist RGB-D before/after; SOURCE571 strict door validator unchanged",
                    "private_metadata": "endpoint scoring only; never selector, geometry, timing or stop"},
                recipe_difference={"source": "544/549 replaced by fixed571",
                    "contact": "current160 with measured_fixture_handle preapproach removed",
                    "binding": "owned purely public unique current visible parent selector",
                    "prompt": "same registered original public subtask, also scoped for setup",
                    "scope": "joint method selection; no single-factor causal or confirmation claim"})
    args.output.mkdir(parents=True, exist_ok=False)
    manifest = args.output / "microwave_public_parent_original10.json"
    manifest.write_text(json.dumps(plan, indent=2) + "\n")
    summary = {"manifest": ref(manifest), "source": plan["source_snapshot"], "adapter": adapter,
               "launcher": launcher, "cases": 10, "unique_raw_states": len({c["state_sha256"] for c in cases}),
               "by_type": dict(Counter(c["type"] for c in cases)), "setup_preserved": True,
               "original_case_order_preserved": True, "all_physical_failures_retained": True,
               "new_GPU_jobs": 0, "new_physical_trials": 0, "new_training_rows": 0,
               "qualification_authorized": False,
               "shards": [{"shard": i, "cases": [c["name"] for c in cases[i::5]]} for i in range(5)]}
    (args.output / "preparation.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps({"manifest": ref(manifest), "cases": 10, "source_files_checked": 24,
                      "adapter": adapter, "launcher": launcher}))


if __name__ == "__main__":
    main()
