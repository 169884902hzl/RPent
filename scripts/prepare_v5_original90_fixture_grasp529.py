"""CPU-register explicit original90 confirmation pools after state-SHA access audit.

Read benchmark metadata/init files and only registered ledgers; do not create
an environment, execute physics, inspect PRO tasks or infer visits from a
catalog. Unknown executed measurements remain visited. Pool registration is
not skill qualification and does not authorize a confirmation run.
"""

import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path


TASKS = {"frypan": [18, 21, 40, 41, 42, 45], "moka_pot": [18, 19, 20, 21],
         "mug": [65, 66, 67, 68], "microwave": [33, 35]}
ORIGINAL_SUITES = {"libero_spatial", "libero_object", "libero_goal", "libero_10", "libero_90"}


def identity(path):
    path = Path(path)
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return {"path": str(path), "sha256": digest.hexdigest()}


def pinned_json(record):
    path = Path(record["path"])
    actual = identity(path)
    if actual["sha256"] != record["sha256"]:
        raise ValueError("registered input SHA changed: " + str(path))
    return json.loads(path.read_text()), actual


def episode_key(case):
    ep = case["episode"]
    if ep["suite"] not in ORIGINAL_SUITES:
        raise ValueError("only explicitly registered original episodes are allowed")
    return ep["suite"], int(ep["task"]), int(ep["seed"])


def audit_ledgers(run, state_hash):
    plan, plan_file = pinned_json(run["manifest"])
    expected = {c["name"]: c for c in plan["cases"]}
    seen, hashes, records, unknown = set(), set(), [], []
    for ref in run["ledgers"]:
        record = {"path": ref} if isinstance(ref, str) else ref
        path = Path(record["path"])
        source = identity(path)
        if record.get("sha256") is not None and record["sha256"] != source["sha256"]:
            raise ValueError("closed access ledger changed: " + str(path))
        raw = path.read_bytes()
        if raw and not raw.endswith(b"\n"):
            raise ValueError("closed access ledger has incomplete tail")
        rows = []
        for line in raw.splitlines():
            row = json.loads(line)
            case = row["case"]
            if case != expected.get(case["name"]) or case["name"] in seen:
                raise ValueError("access row differs from its explicit registered case")
            seen.add(case["name"])
            digest = state_hash(*episode_key(case))
            if case.get("state_sha256") not in (None, digest):
                raise ValueError("case state SHA differs from registered original asset")
            # Access, not a successful label, excludes this state from another
            # independent confirmation. Do not replay instrument-unknown rows.
            hashes.add(digest)
            rows.append(case["name"])
            if not isinstance(row.get("true_sustained_grasp"), bool):
                unknown.append({"case": case["name"], "state_sha256": digest,
                    "status": row.get("status"), "raised_error": row.get("raised_error"),
                    "visited_even_when_private_truth_unknown": True})
        records.append({**source, "rows": len(rows), "registered_cases": rows})
    if run.get("require_complete", False) and seen != expected.keys():
        raise ValueError("registered closed run is missing cases")
    return hashes, {"job": run["job"], "manifest": plan_file, "ledger_files": records,
        "planned_rows": len(expected), "recorded_rows": len(seen), "unique_visited_state_sha": len(hashes),
        "missing_case_count": len(expected) - len(seen), "unknown_rows_retained_as_visited": unknown}


def make_pool(tasks, metadata, state_hash, visited, reserved):
    cases, seen = [], set()
    for task in tasks:
        info = metadata(task)
        for seed in range(info["trials"]):
            digest = state_hash("libero_90", task, seed)
            if digest in seen:
                continue
            seen.add(digest)
            cases.append({"episode": {"suite": "libero_90", "task": task, "seed": seed},
                "state_sha256": digest, "bddl": info["bddl"], "init_file": info["init_file"],
                "original_instruction": info["instruction"],
                "visited": digest in visited, "reserved_by_explicit_prior_plan": digest in reserved})
    unvisited = [c for c in cases if not c["visited"]]
    return cases, {"explicit_tasks": tasks, "official_states": sum(metadata(t)["trials"] for t in tasks),
        "unique_state_sha": len(cases), "duplicate_official_states": sum(metadata(t)["trials"] for t in tasks) - len(cases),
        "visited_state_sha": len(cases) - len(unvisited), "unvisited_state_sha": len(unvisited),
        "unvisited_already_reserved": sum(c["reserved_by_explicit_prior_plan"] for c in unvisited),
        "unvisited_unreserved_state_sha": sum(not c["reserved_by_explicit_prior_plan"] for c in unvisited),
        "has_100_unvisited_unique_states": len(unvisited) >= 100}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--closed-index", type=Path, required=True)
    parser.add_argument("--closed-index-sha256", required=True)
    parser.add_argument("--additional-index", type=Path, required=True)
    parser.add_argument("--additional-index-sha256", required=True)
    parser.add_argument("--original-catalog", type=Path, required=True)
    parser.add_argument("--original-catalog-sha256", required=True)
    parser.add_argument("--libero-config-path", type=Path, required=True)
    parser.add_argument("--expected-asset-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    closed, closed_record = pinned_json({"path": args.closed_index, "sha256": args.closed_index_sha256})
    extra, extra_record = pinned_json({"path": args.additional_index, "sha256": args.additional_index_sha256})
    catalog, catalog_record = pinned_json({"path": args.original_catalog, "sha256": args.original_catalog_sha256})
    config = args.libero_config_path / "config.yaml"
    if not config.is_file():
        raise ValueError("explicit existing LIBERO config required")
    os.environ["LIBERO_TYPE"] = "standard"
    os.environ["LIBERO_CONFIG_PATH"] = str(args.libero_config_path)
    import numpy as np
    from libero.libero import get_libero_path
    from libero.libero.envs.bddl_utils import robosuite_parse_problem
    from rlinf.envs.libero.utils import benchmark

    roots = {k: Path(get_libero_path(k)).absolute() for k in ("bddl_files", "init_states")}
    if any(not p.resolve().is_relative_to(args.expected_asset_root.resolve()) for p in roots.values()):
        raise ValueError("runtime original asset root differs")
    suites, arrays, task_metadata = {}, {}, {}

    def state_hash(suite, task_id, seed):
        if suite not in ORIGINAL_SUITES:
            raise ValueError("non-original source suite")
        if suite not in suites:
            suites[suite] = benchmark.get_benchmark(suite)()
        if (suite, task_id) not in arrays:
            task = suites[suite].get_task(task_id)
            if task.problem_folder != suite:
                raise ValueError("original benchmark folder differs")
            arrays[suite, task_id] = np.asarray(suites[suite].get_task_init_states(task_id))
        states = arrays[suite, task_id]
        if not 0 <= seed < len(states):
            raise ValueError("official init index out of range")
        return hashlib.sha256(np.asarray(states[seed], dtype="<f8", order="C").tobytes()).hexdigest()

    # A catalog confirms asset identity; none of these entries is an executed
    # visit. Only the ledgers below can populate visited state hashes.
    if len(catalog) != 40 or {r["suite"] for r in catalog} != ORIGINAL_SUITES - {"libero_90"}:
        raise ValueError("expected explicit original40 task catalog")
    for info in catalog:
        for key in ("bddl", "init_file"):
            pinned_json_identity = identity(info[key]["path"])
            if pinned_json_identity["sha256"] != info[key]["sha256"]:
                raise ValueError("catalog original asset changed")
        if any(state_hash(info["suite"], info["task"], seed) != digest
               for seed, digest in enumerate(info["state_sha256"])):
            raise ValueError("catalog official state SHA changed")

    def metadata(task_id):
        if task_id in task_metadata:
            return task_metadata[task_id]
        state_hash("libero_90", task_id, 0)
        task = suites["libero_90"].get_task(task_id)
        bddl = roots["bddl_files"] / task.problem_folder / task.bddl_file
        init_file = roots["init_states"] / task.problem_folder / task.init_states_file
        problem = robosuite_parse_problem(str(bddl))
        language = " ".join(problem["language_instruction"])
        if language != task.language:
            raise ValueError("original benchmark language differs from BDDL")
        task_metadata[task_id] = {"suite": "libero_90", "task": task_id,
            "instruction": task.language, "instruction_sha256": hashlib.sha256(language.encode()).hexdigest(),
            "bddl": identity(bddl), "init_file": identity(init_file),
            "trials": len(arrays["libero_90", task_id]), "oracle_goal_predicates": problem["goal_state"],
            "metadata_read_is_physical_visit": False}
        return task_metadata[task_id]

    visits, visited = [], set()
    for run in [*[{**r, "require_complete": True} for r in closed["runs"]], *extra["runs"]]:
        hashes, report = audit_ledgers(run, state_hash)
        visits.append(report)
        visited |= hashes
    reserved, reserved_sources = set(), []
    for ref in [closed["first4"]["manifest"], *extra["reserved_manifests"]]:
        plan, record = pinned_json(ref)
        hashes = {state_hash(*episode_key(c)) for c in plan["cases"]}
        reserved |= hashes
        reserved_sources.append({**record, "planned": len(plan["cases"]), "unique_planned_state_sha": len(hashes),
                                 "plan_is_evidence_of_actual_visit": False})
    pools, counts = {}, {}
    for name, tasks in TASKS.items():
        pools[name], counts[name] = make_pool(tasks, metadata, state_hash, visited, reserved)
    microwave = pools["microwave"]
    if (len(microwave) != 100 or counts["microwave"]["visited_state_sha"]
            or counts["microwave"]["duplicate_official_states"]):
        raise ValueError("microwave task33/35 must have 100 unique unvisited original states")
    microwave_plan = []
    for mode in ("open", "close"):
        for item in microwave:
            task_id = item["episode"]["task"]
            # Fixed real setup based on the registered original task family,
            # not on simulator truth or a successful result observed later.
            setup = ([{"tool": "articulate", "object_category": "microwave", "mode": "close"}]
                     if mode == "open" and task_id == 33 else
                     [{"tool": "articulate", "object_category": "microwave", "mode": "open"}]
                     if mode == "close" and task_id == 35 else [])
            microwave_plan.append({**item, "requested_mode": mode, "fixed_real_setup": setup,
                "expected_opposite_before_skill_is_label_only": True,
                "already_satisfied_is_not_new_achievement": True,
                "setup_failure_preserved_no_state_replacement": True})
    report = {"version": "original90_fixture_grasp_pool529/1", "cpu_metadata_and_access_audit_only": True,
        "input_files": [closed_record, extra_record, catalog_record], "config": identity(config),
        "asset_roots": {k: str(v) for k, v in roots.items()},
        "scope": "only explicit original90 tasks already located; counts do not claim all90-task availability",
        "state_hash_encoding": "C contiguous little-endian float64",
        "ledger_access_count": sum(r["recorded_rows"] for r in visits),
        "unique_visited_scene_state_sha": len(visited), "visits": visits,
        "explicit_zero_call_infrastructure_exclusions": extra.get("zero_call_exclusions", []),
        "reserved_sources": reserved_sources, "per_pool": counts,
        "catalog_reads_count_as_visits": False,
        "unknown_recorded_trials_are_visited": True,
        "pi05_training_distribution": "pi0.5 was trained on original LIBERO90; these are unused confirmation states, not unseen-task generalization",
        "new_physical_trials": 0, "new_training_rows": 0, "confirmation_run_authorized": False,
        "confirmation_requires_recipe_and_public_verifier_freeze": True}
    args.output.mkdir(parents=True, exist_ok=False)
    for name, value in (("report.json", report), ("pools.json", pools),
                        ("microwave_open_close_reserved.json", microwave_plan),
                        ("original90_task_sources.json", [task_metadata[t] for t in sorted(task_metadata)])):
        (args.output / name).write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n")
    print(json.dumps({"per_pool": counts, "ledger_access_count": report["ledger_access_count"],
        "unique_visited_scene_state_sha": len(visited), "new_physical_trials": 0,
        "report": identity(args.output / "report.json")}, indent=2))


if __name__ == "__main__":
    main()
