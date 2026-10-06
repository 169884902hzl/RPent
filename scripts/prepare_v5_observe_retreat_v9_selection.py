"""Pin unchanged same40 cases with category setup and real view recovery."""

import argparse
import ast
import copy
import hashlib
import importlib.util
import json
from pathlib import Path


PARENT_SHA = "d58698cef76bbbad9189238adf025a4e75c797b00bc511af06d7388db5c01a24"
CALIBRATION_SHA = "d4d977a5e5c23a23d80983ab34a4958373c6103035c2156ced24038204e4ca1c"
SOURCE_COMMIT = "8fe6b18"
ARCHIVE_SHA = "13b608f53827aec3179ecc90f77bb37c8b4b10bf5a070afd74de4b4a37b7afae"
FLAG = "subtask_place_observe_retreat_v9"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def placement_code(path):
    tree = ast.parse(path.read_text())
    names = {"placement_unknown_reason", "strict_place_verified", "strict_place_verified_v2",
             "strict_place_verified_v3", "strict_place_verified_v4", "strict_place_verified_v5", "strict_place_verified_v6"}
    selected = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in names]
    assert {node.name for node in selected} == names
    return hashlib.sha256("\n".join(ast.unparse(node) for node in selected).encode()).hexdigest()


def prepare(args):
    paths = (args.parent_manifest, args.source, args.source_archive, args.calibration, args.output)
    if not all(path.is_absolute() for path in paths):
        raise ValueError("all registered paths must be absolute")
    if sha(args.parent_manifest) != PARENT_SHA or sha(args.source_archive) != ARCHIVE_SHA:
        raise ValueError("pinned parent manifest or source archive changed")
    if sha(args.calibration) != CALIBRATION_SHA or not args.source_commit.startswith(SOURCE_COMMIT):
        raise ValueError("calibration or source commit identity changed")
    previous = json.loads(args.parent_manifest.read_text())
    if previous["cohort"] != "selection" or previous["qualification_authorized"] is not False or previous["new_training_rows"] != 0:
        raise ValueError("same40 remains development selection")
    if len(previous["cases"]) != 40 or any(case["kind"] != "place" for case in previous["cases"]):
        raise ValueError("all40 existing registered placement cases required")
    if set(previous["conditions"]) != {"current160", "vla_subtask160"}:
        raise ValueError("both original arm identities are required")
    if any(step.get("object_category") != "bowl" or step.get("mode") != "direct"
           for case in previous["cases"] for step in case["setup"]):
        raise ValueError("this diagnostic changes only the existing bowl direct category route")
    tree = ast.parse((args.source / "robots/libero/v5_runtime.py").read_text())
    executor = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "V5Executor")
    constructor = next(node for node in executor.body if isinstance(node, ast.FunctionDef) and node.name == "__init__")
    defaults = dict(zip([arg.arg for arg in constructor.args.kwonlyargs], constructor.args.kw_defaults))
    if FLAG not in defaults or ast.literal_eval(defaults[FLAG]) is not False:
        raise ValueError("v9 must be accepted with default off")
    subtask = next(node for node in executor.body if isinstance(node, ast.FunctionDef) and node.name == "execute_subtask")
    if FLAG not in ast.unparse(subtask) or "self.retreat()" not in ast.unparse(subtask):
        raise ValueError("source must make a real observation retreat")
    old_source = Path(previous["source_snapshot"]["path"])
    for relative in ("robots/libero/v5_state.py", "robots/libero/v5_subtasks.py"):
        if sha(old_source / relative) != sha(args.source / relative):
            raise ValueError(f"state or prompt changed: {relative}")
    strict_sha = placement_code(args.source / "robots/libero/v5_verification.py")
    if strict_sha != placement_code(old_source / "robots/libero/v5_verification.py"):
        raise ValueError("original strict placement functions or missing-evidence reason changed")
    helper_path = args.source / "scripts/prepare_v5_place553_fullchunks_20261006.py"
    if sha(helper_path) != "612492e88cb138538a49ab7f604d57f52f6d0c83cfc6a747fefd69a1f0dc6e6a":
        raise ValueError("complete-block contract helper changed")
    spec = importlib.util.spec_from_file_location("place_v9_fullblocks", helper_path)
    helper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helper)
    checks = helper.contract_check(args.source)
    calibration = json.loads(args.calibration.read_text())
    relatives = [ref["relative_path"] for ref in previous["source_snapshot"]["files"]]
    for relative in ("robots/libero/v5_grasp_measurement.py", "robots/libero/v5_grasp_truth.py",
                     "robots/libero/v5_action_effect.py", "robots/libero/v5_fixture_parts.py",
                     "robots/libero/v5_perception_geometry.py"):
        if relative not in relatives:
            relatives.append(relative)
    source = {"path": str(args.source), "commit": args.source_commit,
              "files": [{"path": str(args.source / relative), "relative_path": relative,
                         "sha256": sha(args.source / relative)} for relative in relatives],
              "archive": {"path": str(args.source_archive), "sha256": ARCHIVE_SHA}}
    plan = copy.deepcopy(previous)
    common = {"grasp_category_profiles_v1": True, "grasp_independent_views_v1": True,
              "grasp_thin_aperture_v1": True, "grasp_measurement_calibration": calibration}
    for condition in plan["conditions"].values():
        condition["overrides"].update(common)
    plan["conditions"]["vla_subtask160"]["overrides"][FLAG] = True
    plan["conditions"]["vla_subtask160"]["overrides"]["retreat_clearance_v1"] = True
    assert plan["cases"] == previous["cases"] and plan["budget"] == previous["budget"]
    assert not plan["conditions"]["current160"]["overrides"].get(FLAG)
    assert plan["conditions"]["vla_subtask160"]["overrides"]["subtask_place_remeasure_v7"]
    assert plan["conditions"]["vla_subtask160"]["overrides"]["subtask_release_reverify_v8"]
    plan.update(version="place-observe-retreat-v9-category-setup-selection/1", source_snapshot=source,
        previous_selection_manifest={"path": str(args.parent_manifest), "sha256": PARENT_SHA},
        producer={"path": str(Path(__file__).resolve()), "sha256": sha(__file__)},
        robot_calibration_file={"path": str(args.calibration), "sha256": CALIBRATION_SHA},
        unchanged_registered_identity={"cases_and_setup": "all40 original dictionaries unchanged, no outcome filter",
            "budget": "original160 chunks x5 controls,10000 external steps,3072 prompt limit unchanged",
            "standards": "strict6 functions and state/prompt unchanged; no qualification"},
        category_setup_contract={"both_arms": common, "registered_category": "bowl", "runtime_profile": "C",
            "actual_route": "observed reset pose; pi0_pick160 with runtime original instruction; independent public paired grasp validator",
            "private_truth_controls_execution": False, "no_trial_lift_override": True,
            "scope": "same40 development selection; category qualification comes from separate prior evidence"},
        observation_retreat_contract={"enabled_arm": "vla_subtask160", "default_off": True,
            "trigger": "missing visible object after ordinary placement remeasurement",
            "motion": "actual existing retreat; zero gripper command preserves actuator target",
            "measured_clearance_route": "retreat_clearance_v1 enabled in VLA arm only; current arm unchanged",
            "evidence": "two newly visible strictly increasing source_step measurements >=0.3s apart",
            "motion_failure_or_missing_evidence": "null", "strict_placement_functions_sha256": strict_sha,
            "private_truth_controls_execution": False, "state_fields_added": False,
            "old_results_preserved": True, "qualification_authorized": False})
    args.output.mkdir(parents=True, exist_ok=False)
    manifest = args.output / "observe_retreat_v9_same40_category_selection.json"
    manifest.write_text(json.dumps(plan, indent=2) + "\n")
    report = {"manifest": {"path": str(manifest), "sha256": sha(manifest)}, "source": source,
        "parent": plan["previous_selection_manifest"], "cases": 40, "unique_raw_states": 20,
        "cases_and_setup_dictionaries_identical": True, "budget_identical": True,
        "common_overrides": common, "vla_only_overrides": {FLAG: True, "retreat_clearance_v1": True},
        "strict_placement_functions_sha256": strict_sha, "complete_block_contract": checks,
        "script_sha256": sha(__file__), "GPU_jobs_submitted": 0, "new_physical_trials": 0,
        "new_training_rows": 0, "qualification_authorized": False}
    (args.output / "preparation.json").write_text(json.dumps(report, indent=2) + "\n")
    return {key: report[key] for key in ("manifest", "cases", "budget_identical", "GPU_jobs_submitted", "qualification_authorized")}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--parent-manifest", type=Path, required=True)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--source-archive", type=Path, required=True)
    parser.add_argument("--calibration", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    print(json.dumps(prepare(parser.parse_args())))


if __name__ == "__main__":
    main()
