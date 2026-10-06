"""Register a 3x5 original-only drawer approach/prompt selection comparison."""

import argparse
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
from types import SimpleNamespace


SOURCE_FILES = (
    "scripts/probe_v5_skill501_original.py",
    "scripts/v5_probe_preflight.py",
    "scripts/probe_v5_grasp449_20261005.py",
    "scripts/summarize_v5_skill501_original.py",
    "scripts/summarize_v5_skill543_selection_20261006.py",
    "scripts/summarize_v5_grasp449_20261005.py",
    "harness_v5_eval.py",
    "robots/libero/v5_env_client.py",
    "robots/libero/v5_runtime.py",
    "robots/libero/v5_state.py",
    "robots/libero/v5_oracle_policy.py",
    "robots/libero/v5_oracle_server.py",
    "robots/libero/v5_branch_state.py",
    "robots/libero/v5_reset_seed.py",
    "robots/libero/v5_motion_diagnostics.py",
    "robots/libero/v5_fixture_parts.py",
    "robots/libero/v5_perception_geometry.py",
    "robots/libero/v5_grasp_measurement.py",
    "robots/libero/v5_grasp_truth.py",
    "robots/libero/v5_verification.py",
    "robots/libero/v5_action_effect.py",
    "robots/libero/robot_spec.py",
    "robots/libero/toolkit.py",
    "robots/libero/env_server.py",
)
METHODS = ("native_original160", "stage_original160", "stage_reordered160")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def cpu_contract(source, cases, conditions):
    """Use the pinned real helpers with CPU fake controls, never physics."""
    sys.path.insert(0, str(source))
    helper_path = Path(__file__).with_name("prepare_v5_place553_fullchunks_20261006.py")
    helper = load_module("drawer557_fullblocks_contract", helper_path)
    blocks = helper.contract_check(source)
    probe = load_module("drawer557_owned_probe", source / SOURCE_FILES[0])
    probe.validate_manifest({"cases": cases, "conditions": conditions})

    class FakeExecutor:
        def __init__(self, case):
            self.scene = SimpleNamespace(entities={"e1": SimpleNamespace(name="cabinet", id="e1")},
                                         dual_view_fusion_v1=True)
            self.p = SimpleNamespace(_vlm_chunk=lambda *a, **k: None)
            self.instruction = case["subtask_prompt"]
            self.max_chunks = 160
            self.stage_calls = 0
            self.prompts = []

        def stage_grasp(self, *args, **kwargs):
            raise AssertionError("drawer comparison must not stage an object grasp")

        def stage_fixture_handle(self, obj, receipt, **kwargs):
            self.stage_calls += 1
            receipt["fixture_handle_approach"] = {"CPU_fake": True, "options": kwargs}
            return True

        def vla_act(self, prompt, max_chunks, stop, source=None, **kwargs):
            self.prompts.append({"text": prompt, "max_chunks": max_chunks, "stop": stop})
            return {"CPU_fake": True}

        def _execute(self, selected, receipt, card):
            return self.vla_act("generic runtime phrase", self.max_chunks, "chunk_budget")

    checked = []
    for method in METHODS:
        case = next(case for case in cases if case["condition"] == method)
        condition = conditions[method]
        assert probe.registered_drawer_instruction(case) == case["subtask_prompt"]
        executor, evidence, receipt = FakeExecutor(case), {}, {}
        selected = SimpleNamespace(tool="articulate", object="e1")
        with probe.contact_probe_controls(executor, None, case, condition, selected, evidence):
            executor._execute(selected, receipt, None)
        expected_stage = 0 if method == "native_original160" else 1
        assert executor.stage_calls == expected_stage
        assert executor.prompts == [{"text": case["subtask_prompt"], "max_chunks": 160, "stop": "chunk_budget"}]
        checked.append({"method": method, "stage_calls": executor.stage_calls,
                        "actual_contact_prompt": executor.prompts[0],
                        "scope": "real pinned config gates, fake CPU executor only"})
    return {"complete_blocks": blocks, "stage_prompt_gates": checked,
            "helper": {"path": str(helper_path.resolve()), "sha256": sha(helper_path)},
            "private_truth_used_for_control": False, "new_physical_trials": 0}


def prepare(previous_manifest, expected_sha, source, output, source_commit):
    previous_manifest = Path(previous_manifest).resolve(strict=True)
    source = Path(source).resolve(strict=True)
    if sha(previous_manifest) != expected_sha:
        raise ValueError("registered measured-handle selection manifest changed")
    previous = json.loads(previous_manifest.read_text())
    if (previous.get("cohort") != "selection" or previous.get("qualification_authorized") is not False
            or previous.get("new_training_rows") != 0):
        raise ValueError("source cohort must be development selection only")
    selected = sorted((case for case in previous["cases"] if case["type"] == "drawer_open"
                       and case["episode"]["suite"] == "libero_90"
                       and case["episode"]["task"] == 6
                       and 10 <= case["episode"]["seed"] <= 14),
                      key=lambda case: case["episode"]["seed"])
    if len(selected) != 5 or [c["episode"]["seed"] for c in selected] != list(range(10, 15)):
        raise ValueError("exactly original LIBERO90 t6 init10-14 must be present once")
    if any(c.get("setup") or c["mode"] != "open" or c["kind"] != "articulate" for c in selected):
        raise ValueError("comparison requires native initial drawer-open states without setup")
    template = previous["conditions"][selected[0]["condition"]]
    if template["executor"] != "current" or template["max_chunks"] != 160:
        raise ValueError("registered articulate/current160 method changed")
    conditions, cases = {}, []
    for method in METHODS:
        condition = copy.deepcopy(template)
        condition.update(contact_prompt_source="registered_original_subtask",
                         contact_approach="none" if method == "native_original160" else "measured_fixture_handle")
        conditions[method] = condition
        for old in selected:
            case = copy.deepcopy(old)
            case.update(name=f"drawer557_libero90_t6_s{old['episode']['seed']}_{method}", condition=method,
                        diagnostic_pair_id=f"libero90_t6_s{old['episode']['seed']}",
                        reservation_scope="intentional reuse of visited original selection state, not confirmation")
            if method != "stage_reordered160":
                case["subtask_prompt"] = old["original_instruction"]
                case["prompt_origin"] = "literal_registered_original_LIBERO90_instruction"
            cases.append(case)
    source_files = [{"path": str(source / rel), "relative_path": rel, "sha256": sha(source / rel)}
                    for rel in SOURCE_FILES]
    checks = cpu_contract(source, cases, conditions)
    plan = copy.deepcopy(previous)
    plan.update(version="drawer557-approach-prompt-paired-selection/1", purpose="separate public approach and prompt-word-order factors",
                cases=cases, conditions=conditions,
                producer={"path": str(Path(__file__).resolve()), "sha256": sha(__file__)},
                producer_dependencies=[checks["helper"]],
                source_snapshot={"path": str(source), "commit": source_commit, "files": source_files},
                previous_selection_manifest={"path": str(previous_manifest), "sha256": expected_sha},
                pairing="same five registered raw initial-state SHA values in all three methods; fixed method-major order gives one seed per five-shard process",
                state_repetition="15 nominal resets over5 previously visited original states; not independent confirmation",
                selection="targeted largest ready-but-failed development category; no trial replacement or outcome filtering within this15",
                preregistered_requests_by_type_arm={"drawer_open/" + method: 5 for method in METHODS},
                skill_chunk_contract={"controls_per_requested_chunk": 5, "native_success_stops_chunk": False,
                                      "stop_at_external_budget": True, "private_joint_or_predicate_used_for_control": False},
                diagnostic_factors={"native_original160": "native/reset pose + literal original public instruction",
                                    "stage_original160": "current measured handle staging + same literal original instruction",
                                    "stage_reordered160": "same measured staging + previous registered reordered instruction",
                                    "fixed": "current/articulate,160chunks,complete5 controls,SAM/perception/verification/config unchanged",
                                    "native": "no scripted approach before contact; perception and read-only metrology do not move the robot"},
                private_labels="read-only before endpoint for stratification and after fixed public receipt; no coordinate substitution, action selection, timing or stopping",
                access_reservations={"inputs": [{"path": str(previous_manifest), "sha256": expected_sha,
                                                  "role": "previous visited development selection"}],
                                     "prior_manifests": [], "selected_unique_state_sha": 5,
                                     "intentional_already_visited_selection_reuse": True},
                confirmation="none; these already-visited states never qualify a method",
                metrics={"endpoint": "private before/after requested endpoint, transient native success separate",
                         "public_null": "unmeasured retained in known-truth agreement denominator",
                         "actual_budget": "compare server chunks with recorded first-stage controls; motor-only approaches are not VLA contact",
                         "paired_factors": "native-original vs stage-original tests approach; stage-original vs stage-reordered tests word order",
                         "uncertainty": "nominal Wilson descriptions only, shared original states and small development sample disclosed"})
    assert len(cases) == 15 and len({c["state_sha256"] for c in cases}) == 5
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    manifest = output / "drawer557_same5_three_methods_selection.json"
    manifest.write_text(json.dumps(plan, indent=2) + "\n")
    result = {"manifest": str(manifest), "manifest_sha256": sha(manifest), "source": plan["source_snapshot"],
              "cases": 15, "unique_raw_states": 5, "methods": list(METHODS), "full_block_and_method_CPU_contract": checks,
              "previous_selection_manifest": plan["previous_selection_manifest"], "GPU_jobs_submitted": 0,
              "new_physical_trials": 0, "new_training_rows": 0, "qualification_authorized": False,
              "script_sha256": sha(__file__)}
    (output / "preparation.json").write_text(json.dumps(result, indent=2) + "\n")
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--previous-manifest", type=Path, required=True)
    parser.add_argument("--previous-manifest-sha", required=True)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(prepare(args.previous_manifest, args.previous_manifest_sha, args.source, args.output, args.source_commit)))


if __name__ == "__main__":
    main()
