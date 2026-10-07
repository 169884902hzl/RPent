# Copyright 2026 Zhilun Hu.
# SPDX-License-Identifier: Apache-2.0
"""Prepare an explicit, train-only public control-evidence capture packet.

Preparation is CPU-only. The generated collector reuses the pinned original
stove diagnostic, adds a pre-contact view recovery, and never enables an
endpoint stop or consumes private labels to choose commands or public ROIs.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shlex


COLLECTOR = r'''"""Fixed original-state capture; private scores never control sampling."""

import argparse
import copy
import hashlib
import json
from pathlib import Path
import sys
import time
from types import SimpleNamespace


def identity(path):
    path = Path(path)
    return {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def read_pinned(reference):
    if identity(reference["path"])["sha256"] != reference["sha256"]:
        raise ValueError("registered input changed: " + reference["path"])
    return json.loads(Path(reference["path"]).read_text())


def robot_observation(executor):
    return {"eef_xyz_m": executor.p._last_obs_eef_pos.tolist(),
            "gripper_opening_m": float(executor.p._last_obs_gripper),
            "source": "robot_proprioception",
            "contact_sensor": None,
            "contact_sensor_reason": "no_public_contact_sensor_in_current_interface"}


def load_inputs(args):
    plan = read_pinned({"path": str(args.manifest), "sha256": args.manifest_sha256})
    if (plan["version"] != "temporal-control-capture/1-dev"
            or plan["public_stop_enabled"] is not False
            or plan["private_labels_control_execution"] is not False
            or plan["fixed_on_chunks"] != 160 or plan["fixed_off_chunks"] != 160
            or plan["three_frame_hold_controls"] != 6
            or not 0 <= args.shard_index < len(plan["cases"])):
        raise ValueError("registered observation-only capture protocol changed")
    selection = read_pinned(plan["selection_manifest"])
    sampling = read_pinned(plan["sampling_manifest"])
    for ref in plan["source_files"]:
        if identity(ref["path"])["sha256"] != ref["sha256"]:
            raise ValueError("registered source changed: " + ref["path"])
    selected = {case["name"]: case for case in selection["cases"]}
    excluded = set(selection["confirmation_raw_state_sha256"])
    for case in plan["cases"]:
        original = selected[case["name"]]
        parent_case = sampling["cases"][case["parent_shard_index"]]
        if (original["split"] != "train" or original["raw_state_sha256"] != case["state_sha256"]
                or parent_case != case["original_case"] or case["state_sha256"] in excluded
                or parent_case["episode"]["suite"] != "libero_goal"
                or parent_case["episode"]["task"] != 7):
            raise ValueError("only explicit existing verifier-train original states are permitted")
    import probe_public_red_recovery as probe
    assigned = plan["cases"][args.shard_index]
    _, _, inherited_report = probe.load_inputs(SimpleNamespace(
        manifest=Path(plan["parent_manifest"]["path"]),
        expected_manifest_sha256=plan["parent_manifest"]["sha256"],
        shard_index=assigned["parent_shard_index"], check_states=True))
    return plan, probe, assigned, {"passed": True, "case": assigned["name"],
        "manifest": identity(args.manifest), "inherited_preflight": inherited_report,
        "raw_state_sha256": assigned["state_sha256"], "split": "train",
        "registered_confirmation_overlap": 0,
        "registry_complete": plan["confirmation_registry_complete"],
        "source_files_checked": len(plan["source_files"]),
        "simulator_started": False, "gpu_services_started": False,
        "physical_run_verified": False, "stop_admitted": False}


def capture_one(executor, sam_rpc, oracle_rpc, case, runtime_plan, directory, *, fresh=True):
    from scripts import probe_v5_stove521_endpoint as inherited
    started = time.monotonic_ns()
    references = inherited.capture_measurements(executor, sam_rpc, oracle_rpc,
        case, runtime_plan, directory, capture=fresh)
    finished = time.monotonic_ns()
    # Only public evidence is read here. The inherited private label reference
    # remains separate and is not an argument of a public measurement.
    public = read_pinned(references["public_measurements"])
    views = {camera: {"source_step": view["source_step"],
        "files": view["files"], "control_features": view.get("control_features"),
        "query_count": len(view["queries"])} for camera, view in public["views"].items()}
    frame = {"source_step": references["source_step"],
        "capture_started_monotonic_ns": started, "capture_finished_monotonic_ns": finished,
        "views": views, "public_measurements": references["public_measurements"],
        "public_robot_observation": robot_observation(executor),
        "coordinate_source": "calibrated_rgbd_and_robot_proprioception",
        "control_roi_source": "unique_current_SAM_mask_and_depth_parent_binding",
        "private_object_or_joint_values": False,
        "arm_withdrawn_claim": None,
        "visibility_rule": "retreat command is not evidence of an unobstructed control ROI"}
    return references, frame


def capture_three(executor, sam_rpc, oracle_rpc, case, runtime_plan, directory):
    import numpy as np
    from scripts.probe_v5_skill501_original import diagnostic_json
    frames, private_references = [], []
    directory.mkdir(parents=True, exist_ok=False)
    for index in range(3):
        if index:
            # After explicit release, keep the same open-gripper command.
            action = np.asarray([0, 0, 0, 0, 0, 0, -1], dtype=np.float32)
            for _ in range(6):
                executor.p._step_env(action)
        references, frame = capture_one(executor, sam_rpc, oracle_rpc, case,
            runtime_plan, directory / ("frame" + str(index)))
        frame["hold_controls_since_previous_frame"] = 6 if index else 0
        frames.append(frame)
        private_references.append(references["labels"])
    if len({frame["source_step"] for frame in frames}) != 3:
        raise RuntimeError("three-frame capture did not produce three fresh source steps")
    public_path, private_path = directory / "public_sequence.json", directory / "private_labels.json"
    public_path.write_text(diagnostic_json({"frames": frames, "fixed_hold_controls": 12,
        "nominal_control_interval_s": .05, "sim_time_measured": False,
        "public_stop_enabled": False, "controller_reads_private_labels": False}, indent=2) + "\n")
    private_path.write_text(json.dumps({"labels": private_references,
        "controller_access": False, "scope": "private_offline_labels_only"}, indent=2) + "\n")
    return {"public_sequence": identity(public_path), "private_sequence_labels": identity(private_path)}


def recovery(executor, *, retreat):
    executor.motion_evidence = []
    before = robot_observation(executor)
    if retreat:
        executor.retreat()
        command = {"name": "retreat", "arguments": {}}
        receipt = {"executed": True}
    else:
        receipt = executor.p.release()
        command = {"name": "release", "arguments": {}}
    return {"command": command, "receipt": receipt,
        "robot_before": before, "robot_after": robot_observation(executor),
        "motion_evidence": copy.deepcopy(executor.motion_evidence),
        "unobstructed_control_view": None}


def run_phases(executor, sam_rpc, oracle_rpc, case, runtime_plan, output):
    from scripts import probe_v5_stove521_endpoint as inherited
    from scripts.probe_v5_skill501_original import diagnostic_json, executed_actions
    result = {"captures": {}, "public_sequences": {}, "off_prompt": "turn off the stove",
        "public_stop_enabled": False, "private_labels_control_execution": False}
    def capture(stage, fresh=True):
        refs, _ = capture_one(executor, sam_rpc, oracle_rpc, case,
            runtime_plan, output / stage, fresh=fresh)
        result["captures"][stage] = refs
    def sequence(stage):
        result["public_sequences"][stage] = capture_three(executor, sam_rpc, oracle_rpc,
            case, runtime_plan, output / (stage + "_sequence"))
    with executor.p.env.complete_skill():
        capture("before_setup", fresh=False)
        result["on_setup"] = inherited.fixed_contact(executor, oracle_rpc,
            phase="on", prompt="turn on the stove", chunks=160)
        capture("after_setup")
        result["pre_off_release"] = recovery(executor, retreat=False)
        result["pre_off_retreat"] = recovery(executor, retreat=True)
        capture("before_off")
        sequence("before_off")
        executor.motion_evidence = []
        off = {"prompt": "turn off the stove", "chunks": 0, "public_stop": False}
        scope_started = False
        try:
            # The server writes private labels into its separate ledger; this
            # response is not used to choose a command, ROI or stopping point.
            oracle_rpc.call("diagnostic.stove_chunk_start",
                kwargs={"phase": "off", "max_chunks": 160}, timeout_s=120)
            scope_started = True
            with (output / "public_red_chunks.jsonl").open("x") as ledger:
                for index in range(160):
                    before = robot_observation(executor)
                    started = time.monotonic_ns()
                    receipt = executor.vla_act("turn off the stove", 1, "chunk_budget")
                    finished = time.monotonic_ns()
                    if receipt.get("chunks") != 1:
                        raise RuntimeError("contact chunk did not execute five controls")
                    off["chunks"] += 1
                    refs, frame = capture_one(executor, sam_rpc, oracle_rpc, case,
                        runtime_plan, output / "off_chunks" / ("chunk" + str(index + 1)))
                    after = robot_observation(executor)
                    delta = [end - start for start, end in zip(before["eef_xyz_m"], after["eef_xyz_m"])]
                    row = {"chunk_index": index + 1, "source_step": frame["source_step"],
                        "command": {"name": "vla_act", "arguments": {
                            "prompt": "turn off the stove", "max_chunks": 1, "stop": "chunk_budget"}},
                        "execution_started_monotonic_ns": started,
                        "execution_finished_monotonic_ns": finished,
                        "actual_controls": 5, "cumulative_contact_controls": (index + 1) * 5,
                        "robot_before": before, "robot_after": after,
                        "eef_delta_xyz_m": delta, "receipt": receipt,
                        "public_frame": frame,
                        "stop_decision": {"stop": False, "reason": "observation_only"}}
                    ledger.write(diagnostic_json(row) + "\n")
                    ledger.flush()
        except Exception as error:
            off.update(status="execution_error", error=repr(error))
        finally:
            if scope_started:
                off["chunk_completion_scope"] = oracle_rpc.call("diagnostic.stove_chunk_end", timeout_s=120)
        off["executed_control_actions"] = executed_actions(executor.motion_evidence)
        off["motion_evidence"] = copy.deepcopy(executor.motion_evidence)
        result["off_contact"] = off
        capture("after_contact")
        result["release_only"] = recovery(executor, retreat=False)
        capture("after_release")
        sequence("after_release")
        result["retreat_only"] = recovery(executor, retreat=True)
        capture("after_retreat")
        sequence("after_retreat")
    result.update(status="fixed_public_control_sequence_recorded",
        native_original_success_latched=bool(executor.p.env._native_terminated),
        external_action_budget_exhausted=bool(executor.p.env.truncated))
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--manifest-sha256", required=True)
    parser.add_argument("--shard-index", type=int, required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--preflight-only", action="store_true")
    parser.add_argument("--preflight-report", type=Path)
    args = parser.parse_args()
    plan, probe, assigned, report = load_inputs(args)
    if args.preflight_report:
        args.preflight_report.parent.mkdir(parents=True, exist_ok=True)
        args.preflight_report.write_text(json.dumps(report, indent=2) + "\n")
    if args.preflight_only:
        print(json.dumps(report)); return
    if args.output is None or not args.output.is_absolute():
        parser.error("physical output must be absolute")
    probe.run_phases = run_phases
    sys.argv = [str(Path(probe.__file__)), "--manifest", plan["parent_manifest"]["path"],
        "--expected-manifest-sha256", plan["parent_manifest"]["sha256"],
        "--shard-index", str(assigned["parent_shard_index"]), "--output", str(args.output)]
    probe.main()


if __name__ == "__main__":
    main()
'''


def identity(path: Path | str) -> dict:
    path = Path(path).resolve(strict=True)
    return {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def read_pinned(path: Path, digest: str) -> dict:
    if identity(path)["sha256"] != digest:
        raise ValueError(f"registered input changed: {path}")
    return json.loads(path.read_text())


def prepare(args: argparse.Namespace) -> dict:
    selection = read_pinned(args.selection_manifest, args.selection_manifest_sha256)
    sampling = read_pinned(args.sampling_manifest, args.sampling_manifest_sha256)
    parent = read_pinned(Path(sampling["parent_manifest"]["path"]), sampling["parent_manifest"]["sha256"])
    if selection["cohort"] != "selection" or sampling["cohort"] != "selection":
        raise ValueError("capture is restricted to existing selection data")
    selected = {case["name"]: case for case in selection["cases"]}
    excluded = set(selection["confirmation_raw_state_sha256"])
    cases = []
    for index, sampled in enumerate(sampling["cases"]):
        original = selected[sampled["name"]]
        if original["split"] != "train":
            continue
        if (original["raw_state_sha256"] != sampled["state_sha256"]
                or sampled["state_sha256"] in excluded
                or sampled["episode"]["suite"] != "libero_goal" or sampled["episode"]["task"] != 7):
            raise ValueError("original training raw-state identity or exclusion check failed")
        cases.append({"name": sampled["name"], "state_sha256": sampled["state_sha256"],
            "parent_shard_index": index, "split": "train", "original_case": sampled})
    if not cases:
        raise ValueError("no registered verifier-train original states")
    parent_plan = read_pinned(Path(parent["parent_manifest"]["path"]), parent["parent_manifest"]["sha256"])
    source_files = [identity(__file__), *parent["owned_files"], *parent_plan["owned_files"]]
    source_files.extend({"path": str(Path(parent_plan["source_root"]) / name), "sha256": digest}
                        for name, digest in parent_plan["source_sha256"].items())
    for ref in source_files:
        if identity(ref["path"])["sha256"] != ref["sha256"]:
            raise ValueError(f"registered source changed: {ref['path']}")
    args.output.mkdir(parents=True, exist_ok=False)
    collector = args.output / "capture_control_sequence.py"
    collector.write_text(COLLECTOR)
    source_files.append(identity(collector))
    root = Path(parent["source_root"]).parent
    manifest = {"version": "temporal-control-capture/1-dev", "cohort": "selection_train_recollection",
        "scope": "existing verifier-train raw states only; no new independent coverage or confirmation",
        "selection_manifest": identity(args.selection_manifest),
        "sampling_manifest": identity(args.sampling_manifest), "parent_manifest": sampling["parent_manifest"],
        "execution_source_root": parent["source_root"], "source_files": source_files,
        "cases": cases, "train_raw_state_count": len({c["state_sha256"] for c in cases}),
        "excluded_validation_names": [c["name"] for c in selection["cases"] if c["split"] == "validation"],
        "registered_confirmation_raw_state_count": len(excluded), "registered_confirmation_overlap": 0,
        "confirmation_registry_complete": selection["remaining_public_state_registry_complete"],
        "source_commit_note": "inherited immutable stove555 snapshot; exact imported files pinned by SHA",
        "fixed_on_chunks": 160, "fixed_off_chunks": 160, "actions_per_chunk": 5,
        "three_frame_hold_controls": 6, "three_frame_phases": ["before_off", "after_release", "after_retreat"],
        "added_hold_controls_per_case": 36,
        "pre_off_view_recovery": ["explicit release", "existing public retreat", "fresh dual-view capture"],
        "each_off_chunk": ["executed command/arguments", "start/end monotonic timestamp",
            "EEF start/end and delta", "gripper opening before/after", "fresh RGB-D/world/calibration SHA",
            "current SAM mask/score/depth support", "unique public parent association", "control geometry or unmeasured"],
        "public_contact_sensor": "unavailable; no synthetic contact or private contact fields",
        "visibility": "unobstructed view requested, never inferred from the retreat command alone",
        "private_labels_control_execution": False, "private_labels_control_roi": False,
        "public_stop_enabled": False, "stop_admitted": False, "threshold_fitting": False,
        "new_decider_training_rows": 0, "model_training": False, "runtime_modified": False,
        "node_binding": None, "planned_array": f"0-{len(cases) - 1}%{len(cases)}",
        "output_root": str(args.physical_output.resolve()), "GPU_submitted": False,
        "physical_run_verified": False, "read_mode": "manifest-explicit files only; no artifact enumeration"}
    manifest_path = args.output / "capture_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    paths = [parent["source_root"], str(Path(parent["parent_manifest"]["path"]).parent),
             str(Path(sampling["parent_manifest"]["path"]).parent), str(args.output.resolve())]
    launcher = args.output / "run_capture.sbatch"
    launcher.write_text(f'''#!/usr/bin/env bash
#SBATCH --partition=gpu
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=90G
#SBATCH --time=08:00:00
#SBATCH --array=0-{len(cases) - 1}%{len(cases)}
#SBATCH --nice=1000
#SBATCH --job-name=libero-control-capture
#SBATCH --output={root}/results/slurm-%A_%a.log
set -euo pipefail
export PYTHONPATH={shlex.quote(':'.join(paths))}
export MUJOCO_GL=egl PYOPENGL_PLATFORM=egl LIBERO_TYPE=standard
export LIBERO_CONFIG_PATH={shlex.quote(str(root / 'runtime_config'))}
export PI05_CHECKPOINT_PATH={shlex.quote(str(root / 'assets/pi05'))}
export SAM3_CHECKPOINT_PATH={shlex.quote(str(root / 'assets/sam3/sam3.pt'))}
export OMP_NUM_THREADS=4 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
CONTROL_CAPTURE_RUN={shlex.quote(str(args.physical_output.resolve()))}/probe_job${{SLURM_ARRAY_JOB_ID}}
mkdir -p "$CONTROL_CAPTURE_RUN"
cd /tmp
CONTROL_CAPTURE_ARGS=(--manifest {shlex.quote(str(manifest_path.resolve()))} --manifest-sha256 {identity(manifest_path)['sha256']} --shard-index "$SLURM_ARRAY_TASK_ID")
{shlex.quote(str(root / '.venv/bin/python'))} {shlex.quote(str(collector.resolve()))} "${{CONTROL_CAPTURE_ARGS[@]}}" --preflight-only --preflight-report "$CONTROL_CAPTURE_RUN/preflight_part${{SLURM_ARRAY_TASK_ID}}.json"
if [[ "${{CONTROL_CAPTURE_PREFLIGHT_ONLY:-0}}" == 1 ]]; then exit 0; fi
{shlex.quote(str(root / '.venv/bin/python'))} -u {shlex.quote(str(collector.resolve()))} "${{CONTROL_CAPTURE_ARGS[@]}}" --output "$CONTROL_CAPTURE_RUN/part${{SLURM_ARRAY_TASK_ID}}"
''')
    report = {"version": "temporal-control-capture-preparation/1", "prepared": True,
        "manifest": identity(manifest_path), "collector": identity(collector), "launcher": identity(launcher),
        "raw_states": len(cases), "validation_states_used": 0, "confirmation_overlap": 0,
        "confirmation_registry_complete": manifest["confirmation_registry_complete"],
        "simulator_started": False, "GPU_submitted": False, "model_trained": False,
        "physical_run_verified": False, "stop_admitted": False,
        "launch_command_template": ["sbatch", "--array=" + manifest["planned_array"], str(launcher.resolve())],
        "submission_owner": "parent agent; register receipt and available GPU count before submission"}
    (args.output / "preparation_report.json").write_text(json.dumps(report, indent=2) + "\n")
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--selection-manifest", type=Path, required=True)
    parser.add_argument("--selection-manifest-sha256", required=True)
    parser.add_argument("--sampling-manifest", type=Path, required=True)
    parser.add_argument("--sampling-manifest-sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--physical-output", type=Path, required=True)
    args = parser.parse_args()
    if not args.output.is_absolute() or not args.physical_output.is_absolute():
        parser.error("preparation and physical output paths must be absolute")
    print(json.dumps(prepare(args)))


if __name__ == "__main__":
    main()
