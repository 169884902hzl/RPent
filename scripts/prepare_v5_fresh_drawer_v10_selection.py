"""Register unchanged original same40 for measured moving-target/cache repair."""

import argparse
import ast
import copy
import hashlib
import json
from pathlib import Path


PARENT_SHA = "76f4f8db4c6e3581af275bbe4823a9918193188fa6d8549e6872921fdd04900d"


def ref(path):
    path = Path(path).resolve(strict=True)
    return {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def strict_code(path):
    names = {"placement_unknown_reason", "strict_place_verified", "strict_place_verified_v2",
             "strict_place_verified_v3", "strict_place_verified_v4", "strict_place_verified_v5", "strict_place_verified_v6"}
    nodes = [n for n in ast.parse(path.read_text()).body if isinstance(n, ast.FunctionDef) and n.name in names]
    assert {n.name for n in nodes} == names
    return hashlib.sha256("\n".join(ast.unparse(n) for n in nodes).encode()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--parent-manifest", type=Path, required=True)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--source-archive", type=Path, required=True)
    parser.add_argument("--expected-source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not all(p.is_absolute() for p in (args.parent_manifest,args.source,args.source_archive,args.expected_source,args.output)):
        raise ValueError("all registered paths must be absolute")
    if ref(args.parent_manifest)["sha256"] != PARENT_SHA:
        raise ValueError("unchanged4311 v9 parent must be pinned")
    previous = json.loads(args.parent_manifest.read_text())
    assert previous["cohort"] == "selection" and previous["qualification_authorized"] is False
    assert len(previous["cases"]) == 40 and {c["kind"] for c in previous["cases"]} == {"place"}
    assert set(previous["conditions"]) == {"current160", "vla_subtask160"}
    expected = json.loads(args.expected_source.read_text())
    assert expected["commit"] == args.source_commit
    files = []
    for entry in expected["files"]:
        actual = ref(args.source / entry["relative_path"])
        if actual["sha256"] != entry["sha256"]:
            raise ValueError("fixed source differs from declared commit: " + entry["relative_path"])
        files.append({**actual,"relative_path":entry["relative_path"]})
    old_source = Path(previous["source_snapshot"]["path"])
    strict_sha = strict_code(args.source / "robots/libero/v5_verification.py")
    assert strict_sha == strict_code(old_source / "robots/libero/v5_verification.py")
    runtime = (args.source / "robots/libero/v5_runtime.py").read_text()
    assert ("moving_target_current_measurement_missing" in runtime
            and "refresh([current.name])" in runtime)
    binding = (args.source / "robots/libero/v5_subtasks.py").read_text()
    assert "canonical_fixture_scene" in binding
    helper = (args.source / "robots/libero/v5_public_fixture_identity.py").read_text()
    assert "allow_drawer_fragment_alias: bool = False" in helper
    archive = ref(args.source_archive)
    if archive["sha256"] != expected["archive_sha256"]:
        raise ValueError("code-only archive differs from registered source")
    plan = copy.deepcopy(previous)
    plan.update(version="fresh-moving-drawer-and-top-alias-v10-selection/1-dev",
        purpose="same40 public target/cache and proven horizontal-alias repair; full fixed source includes prior571 joint changes",
        source_snapshot={"path":str(args.source),"commit":args.source_commit,"files":files,"archive":archive},
        previous_selection_manifest=ref(args.parent_manifest),producer=ref(__file__),
        runtime_default_changed=True,
        pairing="all40 original episodes/raw states/setup/prompts retained; source joint changes and policy RNG unpaired; no isolated causal claim",
        unchanged_registered_identity={"cases_and_setup":"same40 dictionaries identical, no outcome filtering",
            "budget":"same160 full5controls,10000 external steps,3072 tokens","standards":"all strict placement AST functions identical; no qualification"},
        fresh_drawer_contract={"version":"fresh_moving_placement_target/10-dev",
            "moving_parts":"drawer/door names or measured_front_band/measured_door_surface geometry",
            "selection":"same selected ID requires visible current capture geometry; query existing RGB-D when stale",
            "verification":"remeasure at final placement and after actual release; missing current target null/unmeasured",
            "stationary_support":"pregrasp measured cabinet top cache retained",
            "aliases":"only thin drawer same-plane overlap>=.90 with explicit measured cabinet top at current capture",
            "cabinet_fragment_alias_default":False,"extra_drawer_query_vocabulary":False,
            "private_truth_controls_execution":False,"old_results_preserved":True,
            "footprint_thresholds_changed":False,"new_training_rows":0,"qualification_authorized":False})
    assert plan["cases"] == previous["cases"] and plan["conditions"] == previous["conditions"]
    assert plan["budget"] == previous["budget"]
    args.output.mkdir(parents=True,exist_ok=False)
    manifest=args.output/"fresh_drawer_v10_same40_category_selection.json"
    manifest.write_text(json.dumps(plan,indent=2)+"\n")
    report={"manifest":ref(manifest),"source":plan["source_snapshot"],"parent":ref(args.parent_manifest),
        "registered":40,"unique_raw_states":len({c["state_sha256"] for c in plan["cases"]}),
        "cases_setup_conditions_budget_identical":True,"strict_placement_functions_sha256":strict_sha,
        "GPU_jobs_submitted":0,"new_physical_trials":0,"qualification_authorized":False}
    (args.output/"preparation.json").write_text(json.dumps(report,indent=2)+"\n")
    print(json.dumps({"manifest":report["manifest"],"registered":40,"source_files":len(files),"qualification_authorized":False}))


if __name__ == "__main__":
    main()
