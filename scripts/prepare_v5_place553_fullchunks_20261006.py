"""Prepare the same 40 placement selection cases on a pinned full-block probe.

Only explicit manifest/source files are opened. The preparation does not start
services, run physics, submit a job, or use private labels to select an action.
"""

import argparse
import ast
import copy
import hashlib
import importlib.util
import json
from pathlib import Path


SOURCE_FILES = (
    "scripts/probe_v5_skill501_original.py",
    "scripts/v5_probe_preflight.py",
    "scripts/summarize_v5_skill501_original.py",
    "scripts/summarize_v5_skill543_selection_20261006.py",
    "robots/libero/v5_env_client.py",
    "robots/libero/v5_runtime.py",
)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def contract_check(source):
    """Exercise the real pinned CPU chunk helper, including a native latch."""
    import numpy as np

    probe = source / SOURCE_FILES[0]
    spec = importlib.util.spec_from_file_location("place553_owned_probe", probe)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    tree = ast.parse(probe.read_text())
    runner = next(node for node in tree.body if isinstance(node, ast.FunctionDef)
                  and node.name == "run_registered_skill")
    scope = next((node for node in runner.body if isinstance(node, ast.With)
                  and any(ast.unparse(item.context_expr) == "executor.p.env.complete_skill()"
                          for item in node.items)), None)
    if scope is None or "runner(executor, policy, rpc, case, condition)" not in ast.unparse(scope):
        raise ValueError("complete_skill must enclose both setup and the first attempt")
    serve = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "serve")
    facade = next(node for node in serve.body if isinstance(node, ast.ClassDef) and node.name == "SkillFacade")
    chunk = next(node for node in facade.body if isinstance(node, ast.FunctionDef) and node.name == "chunk_step")
    if "complete_probe_chunk(self, actions" not in ast.unparse(chunk):
        raise ValueError("owned skill server is not using the complete control helper")

    class FakeFacade:
        def __init__(self, truncate_at=None):
            self.calls = 0
            self.truncate_at = truncate_at
            self._skill_chunk_accounting = {
                "chunks_requested": 0, "requested_controls": 0, "executed_controls": 0,
                "raw_native_success_controls": 0, "external_truncation": False,
            }

        def step(self, action):
            self.calls += 1
            # Native success starts at the first control and stays latched.
            trunc = self.truncate_at is not None and self.calls >= self.truncate_at
            return {"step": self.calls}, np.array([0.]), np.array([True]), np.array([trunc]), {}

    full = FakeFacade()
    module.complete_probe_chunk(full, np.zeros((5, 7)))
    assert full.calls == 5 and full._skill_chunk_accounting["requested_controls"] == 5
    assert full._skill_chunk_accounting["executed_controls"] == 5
    assert full._skill_chunk_accounting["raw_native_success_controls"] == 5
    budget = FakeFacade(truncate_at=2)
    module.complete_probe_chunk(budget, np.zeros((5, 7)))
    assert budget.calls == 2 and budget._skill_chunk_accounting["external_truncation"]
    try:
        module.complete_probe_chunk(budget, np.zeros((5, 7)))
    except RuntimeError:
        pass
    else:
        raise AssertionError("a subsequent chunk after external truncation must be rejected")
    return {
        "full_chunk_when_native_success_latched": full._skill_chunk_accounting,
        "external_budget_stops_immediately": budget._skill_chunk_accounting,
        "setup_and_both_first_attempt_arms_inside_complete_skill": True,
        "private_joint_or_predicate_used_for_control": False,
        "scope": "CPU fake-control contract only, not physical evidence or qualification",
    }


def prepare(previous_manifest, expected_sha, source, output, source_commit=None):
    previous_manifest = Path(previous_manifest).resolve(strict=True)
    source = Path(source).resolve(strict=True)
    if sha(previous_manifest) != expected_sha:
        raise ValueError("the registered previous 40-case selection manifest changed")
    previous = json.loads(previous_manifest.read_text())
    if (previous.get("cohort") != "selection" or previous.get("qualification_authorized") is not False
            or previous.get("new_training_rows") != 0):
        raise ValueError("only the registered selection cohort may be reused")
    cases = previous["cases"]
    if len(cases) != 40 or any(case["kind"] != "place" for case in cases):
        raise ValueError("exactly the original 40 placement cases are required")
    if set(previous["conditions"]) != {"current160", "vla_subtask160"}:
        raise ValueError("the original current/VLA arms must remain intact")
    if len({case["name"] for case in cases}) != 40:
        raise ValueError("duplicate registered case names")
    for name, condition in previous["conditions"].items():
        expected_executor = "current" if name == "current160" else "vla_subtask"
        if condition["executor"] != expected_executor or condition["max_chunks"] != 160:
            raise ValueError("the registered method or contact budget changed")
    source_files = [{"path": str(source / rel), "relative_path": rel, "sha256": sha(source / rel)}
                    for rel in SOURCE_FILES]
    checks = contract_check(source)
    plan = copy.deepcopy(previous)
    plan.update(
        version="place553-complete-controls-selection/1",
        previous_selection_manifest={"path": str(previous_manifest), "sha256": expected_sha},
        producer={"path": str(Path(__file__).resolve()), "sha256": sha(__file__)},
        source_snapshot={"path": str(source), "commit": source_commit, "files": source_files},
        skill_chunk_contract={
            "version": "owned-original-skill-complete-chunks/1", "controls_per_requested_chunk": 5,
            "native_success_stops_chunk": False, "stop_at_external_budget": True,
            "private_joint_or_predicate_used_for_control": False,
            "scope": "owned original skill diagnostic, not rollout/evaluation behavior",
        },
        unchanged_registered_identity={
            "cases": "all 40 case dictionaries unchanged, including names, states, BDDL/init and public subtask texts",
            "conditions": "both current160/vla_subtask160 dictionaries unchanged; contact stops are public/runtime or budget",
            "standards": "same thresholds, first-attempt scoring, no physical-failure retries; this remains selection",
        },
        placement_reporting_contract={
            "newly_satisfied": "physically_executed and private_before=false and private_after=true",
            "already_satisfied_preserved": "before=true and after=true, reported separately, not a newly successful place",
            "setup_strata": ["true_sustained_grasp", "false_sustained_grasp", "unknown_sustained_grasp"],
            "setup_truth_controls_execution": False,
            "no_first_attempt": "public setup/binding failure or unavailable; never reported as executed success",
            "unmeasured": "null remains unmeasured; known-truth agreement keeps null in the denominator",
            "actual_budget": "server_chunk_execution compared to all recorded setup/first motion controls; native flags and external truncation separate",
        },
    )
    assert plan["cases"] == previous["cases"] and plan["conditions"] == previous["conditions"]
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    manifest = output / "place553_same40_selection.json"
    manifest.write_text(json.dumps(plan, indent=2) + "\n")
    report = {
        "version": "place553-CPU-prepare/1", "manifest": str(manifest), "manifest_sha256": sha(manifest),
        "previous_selection_manifest": plan["previous_selection_manifest"], "source": plan["source_snapshot"],
        "cases": 40, "raw_states": len({case["state_sha256"] for case in cases}),
        "case_and_condition_identity_unchanged": True, "complete_block_contract": checks,
        "new_physical_trials": 0, "new_training_rows": 0, "GPU_jobs_submitted": 0,
        "qualification_authorized": False, "script_sha256": sha(__file__),
    }
    preparation = output / "preparation.json"
    preparation.write_text(json.dumps(report, indent=2) + "\n")
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--previous-manifest", type=Path, required=True)
    parser.add_argument("--previous-manifest-sha", required=True)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--source-commit")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(prepare(args.previous_manifest, args.previous_manifest_sha,
                             args.source, args.output, args.source_commit)))


if __name__ == "__main__":
    main()
