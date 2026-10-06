"""Prepare same40 selection with VLA-only missing-placement remeasurement."""

import argparse
import ast
import copy
import hashlib
import importlib.util
import json
from pathlib import Path


PARENT_SHA = "82f102902091aeb74d25ff4c3205843208d2a8b9ad48e796dde360f605261424"
FLAG = "subtask_place_remeasure_v7"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def absolute(path):
    if not path.is_absolute():
        raise ValueError(f"absolute path required: {path}")
    return path.resolve(strict=True)


def prepare(args):
    previous_path, source, archive = (absolute(path) for path in (args.previous_manifest, args.source, args.source_archive))
    if args.previous_manifest_sha != PARENT_SHA or sha(previous_path) != PARENT_SHA:
        raise ValueError("the explicitly registered same40 parent manifest changed")
    if sha(archive) != args.source_archive_sha:
        raise ValueError("SOURCE560 archive SHA differs from the deployed identity")
    previous = json.loads(previous_path.read_text())
    if previous.get("cohort") != "selection" or previous.get("qualification_authorized") is not False or previous.get("new_training_rows") != 0:
        raise ValueError("same40 remains original-task development selection only")
    if len(previous["cases"]) != 40 or any(case["kind"] != "place" for case in previous["cases"]):
        raise ValueError("all 40 original placement case dictionaries are required")
    if set(previous["conditions"]) != {"current160", "vla_subtask160"}:
        raise ValueError("current and VLA arms must be preserved")
    if FLAG in previous["conditions"]["current160"]["overrides"] or FLAG in previous["conditions"]["vla_subtask160"]["overrides"]:
        raise ValueError("parent already contains the new remeasurement flag")
    helper_ref = previous["producer"]
    helper_path = absolute(Path(helper_ref["path"]))
    if sha(helper_path) != helper_ref["sha256"]:
        raise ValueError("registered complete-block CPU helper changed")
    spec = importlib.util.spec_from_file_location("registered_fullblocks553", helper_path)
    helper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helper)
    checks = helper.contract_check(source)
    runtime = source / "robots/libero/v5_runtime.py"
    tree = ast.parse(runtime.read_text())
    executor = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "V5Executor")
    constructor = next(node for node in executor.body if isinstance(node, ast.FunctionDef) and node.name == "__init__")
    if FLAG not in {arg.arg for arg in constructor.args.kwonlyargs}:
        raise ValueError("SOURCE560 executor does not accept the prepared override")
    subtask = next(node for node in executor.body if isinstance(node, ast.FunctionDef) and node.name == "execute_subtask")
    if FLAG not in ast.unparse(subtask):
        raise ValueError("SOURCE560 subtask does not consume the new override")
    source_refs = [{"path": str(source / ref["relative_path"]), "relative_path": ref["relative_path"],
                    "sha256": sha(source / ref["relative_path"])} for ref in previous["source_snapshot"]["files"]]
    plan = copy.deepcopy(previous)
    plan["conditions"]["vla_subtask160"]["overrides"][FLAG] = True
    expected_conditions = copy.deepcopy(previous["conditions"])
    expected_conditions["vla_subtask160"]["overrides"][FLAG] = True
    assert plan["conditions"] == expected_conditions
    assert plan["conditions"]["current160"] == previous["conditions"]["current160"]
    assert plan["cases"] == previous["cases"] and plan["budget"] == previous["budget"]
    plan.update(version="place560-missing-evidence-remeasure-selection/1",
                previous_selection_manifest={"path": str(previous_path), "sha256": PARENT_SHA},
                producer={"path": str(Path(__file__).resolve()), "sha256": sha(__file__)},
                source_snapshot={"path": str(source), "commit": args.source_commit, "files": source_refs,
                                 "archive": {"path": str(archive), "sha256": args.source_archive_sha}},
                unchanged_registered_identity={
                    "cases_and_setup": "all40 original dictionaries unchanged",
                    "conditions": "only vla_subtask160.overrides.subtask_place_remeasure_v7=true",
                    "current_control": "entire current160 dictionary unchanged",
                    "budget": "entire original budget unchanged; 160 chunks, 5 controls per chunk, 10000 external steps",
                    "standards": "strict_place/6 on=.90,in=.85 and all other gates unchanged; no qualification or relabeling",
                },
                remeasurement_development_contract={
                    "scope": "only missing two-frame transfer evidence gets fresh public observations",
                    "private_truth_controls_execution": False, "original_results_preserved": True,
                    "planned_physical_trials": 40, "cohort": "selection", "new_training_rows": 0,
                    "source_change": "missing verification_reason recorded by SOURCE560; strict_place/6 gates unchanged",
                })
    output = args.output
    if not output.is_absolute():
        raise ValueError("absolute output path required")
    output.mkdir(parents=True, exist_ok=False)
    manifest_path = output / "place560_same40_remeasure_selection.json"
    manifest_path.write_text(json.dumps(plan, indent=2) + "\n")
    report = {"version": "place560-CPU-prepare/1", "manifest": str(manifest_path), "manifest_sha256": sha(manifest_path),
              "parent_manifest": plan["previous_selection_manifest"], "source": plan["source_snapshot"],
              "cases": 40, "unique_raw_states": len({case["state_sha256"] for case in plan["cases"]}),
              "cases_setup_budget_identical": True, "current_condition_identical": True,
              "only_condition_change": "vla_subtask160.overrides." + FLAG + "=true",
              "complete_block_contract": checks, "helper": helper_ref, "script_sha256": sha(__file__),
              "GPU_jobs_submitted": 0, "new_physical_trials": 0, "new_training_rows": 0,
              "qualification_authorized": False}
    (output / "preparation.json").write_text(json.dumps(report, indent=2) + "\n")
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--previous-manifest", type=Path, required=True)
    parser.add_argument("--previous-manifest-sha", required=True)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--source-archive", type=Path, required=True)
    parser.add_argument("--source-archive-sha", required=True)
    parser.add_argument("--output", type=Path, required=True)
    print(json.dumps(prepare(parser.parse_args())))


if __name__ == "__main__":
    main()
