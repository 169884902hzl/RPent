"""Enumerate standard90 pan-presence states under explicit access exclusions."""

import hashlib
import json
import os
import sys
from collections import Counter
from pathlib import Path


ROOT, OUT = map(Path, sys.argv[1:3])
BASE = ROOT / "results/harness_v5/grasp_runtime546_monitor_CPU_20261006"
os.environ["LIBERO_TYPE"] = "standard"
os.environ["LIBERO_CONFIG_PATH"] = str(ROOT / "runtime_config")
import numpy as np
from rlinf.envs.libero.utils import benchmark


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


registration = json.loads((BASE / "pan_cross_view_development10/registration.json").read_text())
pool_path = Path(registration["access_pool"]["path"])
assert digest(pool_path) == registration["access_pool"]["sha256"]
pool = json.loads(pool_path.read_text())
audit_path = pool_path.parent / "report.json"
audit = json.loads(audit_path.read_text())
metadata_path = BASE / "pan_cross_view_development10/original90_pan_metadata_scan.json"
assert digest(metadata_path) == "14ef5eb94d9a137714aa1602909c3508844460201cdf3bf553ceb11d34023467"
metadata = json.loads(metadata_path.read_text())
init_root = Path(pool["frypan"][0]["init_file"]["path"]).parents[1]
suite = benchmark.get_benchmark("libero_90")()
candidates, sources = [], []
for task_metadata in metadata["pan_tasks"]:
    task_id = task_metadata["task"]
    task = suite.get_task(task_id)
    assert task.problem_folder == "libero_90"
    bddl = Path(task_metadata["bddl"]["path"])
    assert digest(bddl) == task_metadata["bddl"]["sha256"]
    init_file = init_root / task.problem_folder / task.init_states_file
    states = suite.get_task_init_states(task_id)
    sources.append({"task": task_id, "bddl": task_metadata["bddl"],
                    "init_file": {"path": str(init_file), "sha256": digest(init_file)}})
    for seed, initial in enumerate(states):
        state = np.asarray(initial, dtype="<f8", order="C")
        candidates.append({"episode": {"suite": "libero_90", "task": task_id, "seed": seed},
                           "state_sha256": hashlib.sha256(state.tobytes()).hexdigest(),
                           "original_instruction": task_metadata["instruction"],
                           "original_goal_predicates": task_metadata["goals"],
                           "pan_is_original_goal_target": task_metadata["goal_pan"],
                           "diagnostic_pan_symbol": "chefmate_8_frypan_1",
                           "bddl": task_metadata["bddl"], "init_file": sources[-1]["init_file"],
                           "single_skill_pan_diagnostic_is_original_task_success": False})
tuple_to_state = {(r["episode"]["suite"], r["episode"]["task"], r["episode"]["seed"]): r["state_sha256"] for r in candidates}
excluded_tuples, excluded_states, inputs, loaded = set(), set(), [], set()


def exclude_case(case):
    episode = case.get("episode")
    if episode:
        key = (episode["suite"], episode["task"], episode["seed"])
        excluded_tuples.add(key)
        if key in tuple_to_state:
            excluded_states.add(tuple_to_state[key])
    if case.get("state_sha256"):
        excluded_states.add(case["state_sha256"])


def exclude_manifest(path, expected=None, role="registered_access_or_reservation"):
    path = Path(path)
    if not path.is_absolute():
        path = ROOT / path
    actual = digest(path)
    if expected:
        assert actual == expected, (path, expected, actual)
    if str(path) in loaded:
        return
    loaded.add(str(path))
    value = json.loads(path.read_text())
    inputs.append({"path": str(path), "sha256": actual, "role": role})
    for case in value.get("cases", []):
        exclude_case(case)
    for episode in value.get("episodes", []):
        exclude_case(episode if "episode" in episode else {"episode": episode})
    for child in value.get("files", []):
        if child.get("cohort") == "development":
            continue
        exclude_manifest(child["path"], child["sha256"], "explicit_index_child")


for rows in pool.values():
    for row in rows:
        if row.get("visited") or row.get("reserved_by_explicit_prior_plan"):
            exclude_case(row)
for descriptor in registration["explicit_exclusions"] + [registration["manifest"]]:
    exclude_manifest(descriptor["path"], descriptor["sha256"])
for descriptor in audit["reserved_sources"]:
    exclude_manifest(descriptor["path"], descriptor["sha256"])
for visit in audit["visits"]:
    exclude_manifest(visit["manifest"]["path"], visit["manifest"]["sha256"], "historical_access_manifest")
extra = [
    ("grasp_next_methods_20261006/preparation/moka_methods_selection.json", "5f9044d6236128de6900b7b8ed15c0e792db615e117a6affe6be6dfc96061daa"),
    ("skill540_articulate_place_selection/preparation/fixtures.json", "59cc228e9aa4aa49349009c639f3312e6044a60201f8834b0f223b62ddace387"),
    ("skill540_articulate_place_selection/preparation/place.json", "23e97aeda7ae28c44ba15c74c10d4c80e92f12fd8de49e17b17c37fdb00abe93"),
    ("place548_measured_support_CPU_20261006/place_smoke40_selection_source548.json", "6ebcbe7ae6fd96dc0be54960137e14bc5c88f6be94757e26da175fec4e045917"),
    ("fixture540_measured_handle_selection/preparation_runtime549_smoke30/fixtures_measured_handle_selection.json", "8db78a69313c4b85468887a60cc103506119313c16a73940070d051e86eb43c6"),
    ("fixture540_measured_handle_selection/preparation_smoke30/fixtures_measured_handle_selection.json", "ae6feb7ab1933698fdb8e1fc5a53b949c1bc64a7d026e4fc23542cc6c16010b3"),
    ("stove555_fixed_prefix_CPU_20261006/stove_control_sampling10.json", "50fef3327c6d264d19a911ea5f3bd86807c683dab9bbbf25d4e9042874d83597"),
    ("stove555_fixed_prefix_CPU_20261006/stove_nearzero_selection100.json", "f1bb636b587e5a98bc581e3519c196d1d71e850744575cd95471f900c5eb8f83"),
    ("runtime550_smoke20_20261006/preparation/manifest.json", "8e66366f67ac7953c20935f2a8ff3aec2424f3c2636c68282af1c08911ad9d50"),
    ("runtime553_smoke20_20261006/preparation/manifest.json", "cbe9aed4af21ae060ff706d8cf5673e63b2dfd6392ee89f1dd2e664e9bf0a4fd"),
]
for name, expected in extra:
    exclude_manifest(ROOT / "results/harness_v5" / name, expected)
eligible = [r for r in candidates if r["state_sha256"] not in excluded_states
            and (r["episode"]["suite"], r["episode"]["task"], r["episode"]["seed"]) not in excluded_tuples]
report = {"scope": "Static original90 pan-presence pool under explicit historical and current registrations only",
          "producer_sha256": digest(Path(__file__)), "source_metadata_sha256": digest(metadata_path),
          "access_audit": {"path": str(audit_path), "sha256": digest(audit_path)},
          "access_pool": registration["access_pool"], "exclusion_inputs": inputs,
          "task_sources": sources, "candidate_scene_tuples": len(candidates),
          "candidate_unique_raw_states": len({r["state_sha256"] for r in candidates}),
          "eligible_under_explicit_audit": len(eligible),
          "eligible_unique_raw_states": len({r["state_sha256"] for r in eligible}),
          "eligible_by_task": dict(Counter(r["episode"]["task"] for r in eligible)),
          "complete_all_history_fresh_audit": False, "independent_confirmation_registered": False,
          "scope_limit": "Known access report and named manifests only; cannot claim all historical visits are covered",
          "off_target_pan_goal_policy": "Tasks19/20/43/44 retain their original goals and instruction; pan single-skill diagnostics do not certify those original tasks",
          "eligible_cases": eligible, "state_hash_encoding": "C contiguous little endian float64",
          "new_physics": 0, "new_model_calls": 0, "new_training_rows": 0, "qualification_authorized": False}
OUT.mkdir(parents=True, exist_ok=False)
(OUT / "report.json").write_text(json.dumps(report, indent=2) + "\n")
print(json.dumps({k: report[k] for k in ("candidate_scene_tuples", "candidate_unique_raw_states", "eligible_under_explicit_audit", "eligible_unique_raw_states", "eligible_by_task", "complete_all_history_fresh_audit")}))
