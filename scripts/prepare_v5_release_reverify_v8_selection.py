"""Pin the same40 place560 cases with real release re-verification enabled."""

import argparse
import ast
import copy
import hashlib
import importlib.util
import json
from pathlib import Path


PARENT_SHA = "327dd7044215829e46168d81f8bbb8743505a22ceab07493f76d4c1955217679"
FLAG = "subtask_release_reverify_v8"
COMMIT = "67a4d4bc67af5db89e31dd1f631c88a8eab6397b"
ARCHIVE_SHA = "712e72d29c2adc4a6d73ed3ce152f60393a3975da96d9190bc35de9ce9de91d8"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def prepare(args):
    paths = (args.parent_manifest, args.source, args.source_archive, args.output)
    if not all(path.is_absolute() for path in paths):
        raise ValueError("absolute manifest, source, archive and output paths required")
    if sha(args.parent_manifest) != PARENT_SHA or sha(args.source_archive) != ARCHIVE_SHA:
        raise ValueError("registered parent or pinned commit67a4d4b archive changed")
    previous = json.loads(args.parent_manifest.read_text())
    if previous["cohort"] != "selection" or previous["qualification_authorized"] is not False or previous["new_training_rows"] != 0:
        raise ValueError("same40 is development selection only")
    if len(previous["cases"]) != 40 or any(case["kind"] != "place" for case in previous["cases"]):
        raise ValueError("all40 original placement cases required")
    if set(previous["conditions"]) != {"current160", "vla_subtask160"}:
        raise ValueError("current and VLA conditions changed")
    if any(FLAG in condition["overrides"] for condition in previous["conditions"].values()):
        raise ValueError("parent already includes release re-verification")
    if previous["conditions"]["vla_subtask160"]["overrides"].get("subtask_place_remeasure_v7") is not True:
        raise ValueError("the prior VLA remeasurement remains enabled")
    runtime = args.source / "robots/libero/v5_runtime.py"
    tree = ast.parse(runtime.read_text())
    executor = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "V5Executor")
    constructor = next(node for node in executor.body if isinstance(node, ast.FunctionDef) and node.name == "__init__")
    defaults = dict(zip([arg.arg for arg in constructor.args.kwonlyargs], constructor.args.kw_defaults))
    if FLAG not in defaults or ast.literal_eval(defaults[FLAG]) is not False:
        raise ValueError("v8 must be accepted with default off")
    subtask = next(node for node in executor.body if isinstance(node, ast.FunctionDef) and node.name == "execute_subtask")
    if FLAG not in ast.unparse(subtask) or "self.p.release()" not in ast.unparse(subtask):
        raise ValueError("pinned source must perform an actual release")
    helper_path = args.source / "scripts/prepare_v5_place553_fullchunks_20261006.py"
    helper_sha = "612492e88cb138538a49ab7f604d57f52f6d0c83cfc6a747fefd69a1f0dc6e6a"
    if sha(helper_path) != helper_sha:
        raise ValueError("registered complete-block CPU helper changed")
    spec = importlib.util.spec_from_file_location("fullblocks_v8", helper_path)
    helper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helper)
    checks = helper.contract_check(args.source)
    for relative in ("robots/libero/v5_state.py", "robots/libero/v5_verification.py", "robots/libero/v5_subtasks.py"):
        old = Path(previous["source_snapshot"]["path"]) / relative
        if sha(old) != sha(args.source / relative):
            raise ValueError(f"strict thresholds, state or prompt changed: {relative}")
    relatives = [ref["relative_path"] for ref in previous["source_snapshot"]["files"]]
    relatives += [relative for relative in ("robots/libero/v5_state.py", "robots/libero/v5_verification.py",
                  "robots/libero/v5_subtasks.py", "robots/libero/tools.py", "harness_v5_eval.py")
                  if relative not in relatives]
    source = {"path": str(args.source), "commit": COMMIT,
              "files": [{"path": str(args.source / relative), "relative_path": relative,
                         "sha256": sha(args.source / relative)} for relative in relatives],
              "archive": {"path": str(args.source_archive), "sha256": ARCHIVE_SHA}}
    plan = copy.deepcopy(previous)
    plan["conditions"]["vla_subtask160"]["overrides"][FLAG] = True
    expected = copy.deepcopy(previous["conditions"])
    expected["vla_subtask160"]["overrides"][FLAG] = True
    assert plan["conditions"] == expected
    assert plan["cases"] == previous["cases"] and plan["budget"] == previous["budget"]
    plan.update(version="place-release-reverify-v8-selection/1", source_snapshot=source,
        previous_selection_manifest={"path": str(args.parent_manifest), "sha256": PARENT_SHA},
        producer={"path": str(Path(__file__).resolve()), "sha256": sha(__file__)},
        release_reverification_contract={
            "only_condition_change": "vla_subtask160.overrides.subtask_release_reverify_v8=true",
            "trigger": "same-action real open event; visible fresh stable withdrawn frames and unchanged strict6 geometry",
            "action": "actual release; two new frames; original strict6 with current real sensor opening",
            "missing_evidence": "null", "telemetry": "diagnostic only; no new state text fields",
            "strict6_thresholds_changed": False, "private_truth_controls_execution": False,
            "old_results_preserved": True, "new_training_rows": 0, "qualification_authorized": False})
    args.output.mkdir(parents=True, exist_ok=False)
    manifest = args.output / "release_reverify_v8_same40_selection.json"
    manifest.write_text(json.dumps(plan, indent=2) + "\n")
    report = {"manifest": {"path": str(manifest), "sha256": sha(manifest)}, "source": source,
        "parent": plan["previous_selection_manifest"], "cases": 40,
        "unique_raw_states": len({case["state_sha256"] for case in plan["cases"]}),
        "cases_setup_budget_identical": True, "current_condition_identical": True,
        "only_condition_change": plan["release_reverification_contract"]["only_condition_change"],
        "complete_block_contract": checks, "script_sha256": sha(__file__),
        "GPU_jobs_submitted": 0, "new_physical_trials": 0, "qualification_authorized": False}
    (args.output / "preparation.json").write_text(json.dumps(report, indent=2) + "\n")
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--parent-manifest", type=Path, required=True)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--source-archive", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    print(json.dumps(prepare(parser.parse_args())))


if __name__ == "__main__":
    main()
