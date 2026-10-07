"""Prepare nine fixed-block withdrawal diagnostics on three visited train states.

The immutable r4 producer supplies the capture implementation. This packet
changes only the registered off-block budget and records withdrawal controls.
Private joint labels never choose a block, command, public ROI or stopping point.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import shlex


def identity(path):
    path = Path(path).resolve(strict=True)
    if not path.is_file():
        raise ValueError("Expected an explicit regular file: " + str(path))
    return {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def pinned(ref):
    if not Path(ref["path"]).is_absolute() or identity(ref["path"]) != ref:
        raise ValueError("Registered file changed or is not absolute: " + ref["path"])
    return Path(ref["path"])


def replace_once(source, old, new):
    if source.count(old) != 1:
        raise ValueError("Pinned implementation changed at overlay: " + old[:100])
    return source.replace(old, new, 1)


LOADER = r'''def load_inputs(args):
    plan = read_pinned({"path": str(args.manifest), "sha256": args.manifest_sha256})
    if (plan["version"] != "stove-fixed-withdrawal/1-dev"
            or plan["public_stop_enabled"] is not False
            or plan["private_labels_control_execution"] is not False
            or plan["fixed_on_chunks"] != 160
            or plan["fixed_off_chunks_by_case"] != [20, 40, 160]
            or plan["three_frame_hold_controls"] != 6
            or plan["three_frame_phases"] != ["after_release", "after_retreat"]
            or plan["preserve_pre_off_contact"] is not True
            or len(plan["cases"]) != 9
            or not 0 <= args.shard_index < 9):
        raise ValueError("Registered fixed-block withdrawal protocol changed")
    parent_capture = read_pinned(plan["parent_capture_manifest"])
    if parent_capture["version"] != "temporal-control-capture/4-dev":
        raise ValueError("Expected the immutable r4 parent")
    for ref in plan["source_files"]:
        if identity(ref["path"])["sha256"] != ref["sha256"]:
            raise ValueError("Registered source changed: " + ref["path"])
    for index, case in enumerate(plan["cases"]):
        original = parent_capture["cases"][index % 3]
        if (case["name"] != original["name"]
                or case["state_sha256"] != original["state_sha256"]
                or case["original_case"] != original["original_case"]
                or case["parent_shard_index"] != original["parent_shard_index"]
                or case["split"] != "train"
                or case["original_case"]["episode"] != {
                    "suite": "libero_goal", "task": 7, "seed": index % 3}
                or case["fixed_off_chunks"] != (20, 40, 160)[index // 3]):
            raise ValueError("Only the three explicit visited train states are allowed")
    probe = importlib.import_module("probe_control580_fixed_withdrawal")
    assigned = plan["cases"][args.shard_index]
    _, _, inherited_report = probe.load_inputs(SimpleNamespace(
        manifest=Path(plan["parent_manifest"]["path"]),
        expected_manifest_sha256=plan["parent_manifest"]["sha256"],
        shard_index=assigned["parent_shard_index"], check_states=True))
    return plan, probe, assigned, {"passed": True, "case": assigned["name"],
        "diagnostic_case_id": assigned["diagnostic_case_id"],
        "fixed_off_chunks": assigned["fixed_off_chunks"],
        "manifest": identity(args.manifest), "inherited_preflight": inherited_report,
        "raw_state_sha256": assigned["state_sha256"], "split": "train",
        "source_files_checked": len(plan["source_files"]),
        "validation_episodes_read": False, "simulator_started": False,
        "gpu_services_started": False, "physical_run_verified": False,
        "stop_admitted": False}


'''


RECOVERY = r'''def recovery(executor, *, retreat):
    executor.motion_evidence = []
    before = robot_observation(executor)
    original_step = executor.p._step_env
    controls = 0
    def counted_step(action):
        nonlocal controls
        result = original_step(action)
        controls += 1
        return result
    executor.p._step_env = counted_step
    try:
        if retreat:
            executor.retreat()
            command = {"name": "retreat", "arguments": {}}
            receipt = {"executed": True}
        else:
            receipt = executor.p.release()
            command = {"name": "release", "arguments": {}}
    finally:
        executor.p._step_env = original_step
    return {"command": command, "receipt": receipt,
        "robot_before": before, "robot_after": robot_observation(executor),
        "motion_evidence": copy.deepcopy(executor.motion_evidence),
        "executed_controls": controls,
        "control_count_source": "successful public _step_env calls",
        "unobstructed_control_view": None}


'''


SERVER = '''"""Fixed original-train diagnostic budget, no truth-controlled schedule."""

import os
import stove564_probe_env as inherited
from robots.libero.v5_stove_probe_env import StoveProbeFacade


class FixedWithdrawalStoveProbeFacade(inherited.ScoredStoveProbeFacade):
    def stove_chunk_start(self, phase, max_chunks):
        off_chunks = int(os.environ["CONTROL_CAPTURE_FIXED_OFF_CHUNKS"])
        if off_chunks not in (20, 40, 160):
            raise ValueError("Unregistered fixed withdrawal block")
        expected = 160 if phase == "on" else off_chunks if phase == "off" else None
        if max_chunks != expected:
            raise ValueError("Registered fixed diagnostic budget changed")
        StoveProbeFacade.stove_chunk_start(self, phase, 160)
        self._stove_chunk_scope.update(max_chunks=max_chunks, max_controls=max_chunks * 5)
        self._write_private_score(dict(self._stove_chunk_scope), "before_phase")
        return dict(self._stove_chunk_scope)


def main():
    inherited.ScoredStoveProbeFacade = FixedWithdrawalStoveProbeFacade
    inherited.main()


if __name__ == "__main__":
    main()
'''


def prepare(args):
    capture_ref = {"path": str(args.capture_manifest), "sha256": args.capture_manifest_sha256}
    parent_capture = json.loads(pinned(capture_ref).read_text())
    if (parent_capture["version"] != "temporal-control-capture/4-dev"
            or parent_capture["train_raw_state_count"] != 3
            or parent_capture["preserve_pre_off_contact"] is not True):
        raise ValueError("Expected the immutable three-train-state r4 packet")
    refs = parent_capture["source_files"]
    producer_ref = next(ref for ref in refs if Path(ref["path"]).name == "prepare_control_packet_source.py")
    for ref in refs:
        pinned(ref)
    producer = pinned(producer_ref)
    spec = importlib.util.spec_from_file_location("immutable_control_capture", producer)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    collector = module.COLLECTOR
    start, end = collector.index("def load_inputs(args):"), collector.index("def capture_one(")
    collector = collector[:start] + LOADER + collector[end:]
    start, end = collector.index("def recovery(executor,"), collector.index("def run_phases(")
    collector = collector[:start] + RECOVERY + collector[end:]
    collector = replace_once(collector,
        'fixed_off_chunks = plan.get("fixed_off_chunks", 160)',
        'fixed_off_chunks = assigned["fixed_off_chunks"]\n'
        '    import os\n'
        '    os.environ["CONTROL_CAPTURE_FIXED_OFF_CHUNKS"] = str(fixed_off_chunks)')
    collector = replace_once(collector,
        'result.update(status="fixed_public_control_sequence_recorded",',
        'result["withdrawal_intervention"] = {\n'
        '        "fixed_off_chunk_endpoint": fixed_off_chunks,\n'
        '        "before": result["captures"]["after_contact"],\n'
        '        "after_release": result["captures"]["after_release"],\n'
        '        "after_retreat": result["captures"]["after_retreat"],\n'
        '        "release_controls": result["release_only"]["executed_controls"],\n'
        '        "retreat_controls": result["retreat_only"]["executed_controls"],\n'
        '        "after_release_sequence_hold_controls": 12,\n'
        '        "after_retreat_sequence_hold_controls": 12,\n'
        '        "hold_gripper_command": -1,\n'
        '        "same_run_paired_observation": True,\n'
        '        "private_labels_only_postcollection": True,\n'
        '        "private_endpoint_triggers_withdrawal": False,\n'
        '        "measurement_insertion_is_physical_intervention": True,\n'
        '        "old_r4_action_prefix_replay_verified": False}\n'
        '    result.update(status="fixed_public_control_sequence_recorded",')
    compile(collector, "capture_fixed_withdrawal.py", "exec")

    parent_packet = Path(parent_capture["parent_manifest"]["path"]).parent
    parent_driver = parent_packet / "probe_public_red_recovery.py"
    if identity(parent_driver) not in refs:
        raise ValueError("Parent driver is not explicitly pinned")
    driver = parent_driver.read_text()
    for old, new in (
        ('Path(__file__).resolve().parent', f'Path({str(parent_packet)!r}).resolve()'),
        ('"diagnostic_server_module": "stove564_probe_env"',
         '"diagnostic_server_module": "control580_fixed_withdrawal_probe_env"'),
        ('len(labels) != 322', 'len(labels) != 162 + int(os.environ["CONTROL_CAPTURE_FIXED_OFF_CHUNKS"])'),
        ('list(range(161))', 'list(range(161 if phase == "on" else 1 + int(os.environ["CONTROL_CAPTURE_FIXED_OFF_CHUNKS"])))'),
        ('row["off_contact"]["chunks"] != 160', 'row["off_contact"]["chunks"] != int(os.environ["CONTROL_CAPTURE_FIXED_OFF_CHUNKS"])'),
        ('row["off_contact"].get("executed_control_actions") != 800',
         'row["off_contact"].get("executed_control_actions") != 5 * int(os.environ["CONTROL_CAPTURE_FIXED_OFF_CHUNKS"])'),
    ):
        driver = replace_once(driver, old, new)
    compile(driver, "probe_control580_fixed_withdrawal.py", "exec")
    compile(SERVER, "control580_fixed_withdrawal_probe_env.py", "exec")
    cases = []
    for chunks in (20, 40, 160):
        for index, original in enumerate(parent_capture["cases"]):
            if (original["split"] != "train"
                    or original["original_case"]["episode"] != {"suite": "libero_goal", "task": 7, "seed": index}):
                raise ValueError("Only the three visited train states are allowed")
            cases.append({**original, "fixed_off_chunks": chunks,
                "diagnostic_case_id": original["name"] + "_off" + str(chunks)})
    args.output.mkdir(parents=True, exist_ok=False)
    generated = []
    for name, source in (
        ("capture_fixed_withdrawal.py", collector),
        ("probe_control580_fixed_withdrawal.py", driver),
        ("control580_fixed_withdrawal_probe_env.py", SERVER),
    ):
        path = args.output / name
        path.write_text(source)
        generated.append(identity(path))
    producer_copy = args.output / "prepare_fixed_withdrawal_source.py"
    producer_copy.write_bytes(Path(__file__).read_bytes())
    generated.append(identity(producer_copy))
    root = Path(parent_capture["execution_source_root"]).parent
    interpreter = root / ".venv/bin/python"
    if not interpreter.is_file():
        raise ValueError("Missing registered execution interpreter")
    plan = {"version": "stove-fixed-withdrawal/1-dev", "cohort": "selection_train_diagnostic",
        "parent_capture_manifest": capture_ref, "parent_manifest": parent_capture["parent_manifest"],
        "source_root": parent_capture["execution_source_root"], "source_files": [*refs, *generated],
        "cases": cases, "fixed_on_chunks": 160, "fixed_off_chunks_by_case": [20, 40, 160],
        "actions_per_chunk": 5, "preserve_pre_off_contact": True,
        "three_frame_hold_controls": 6, "three_frame_phases": ["after_release", "after_retreat"],
        "scope": "three previously visited original train states; no validation or confirmation",
        "public_stop_enabled": False, "stop_admitted": False,
        "private_labels_control_execution": False, "private_labels_control_roi": False,
        "private_joint_label_use": "postcollection before/after withdrawal fixture-change diagnosis only",
        "same_run_paired_stages": ["after_contact", "after_release", "after_retreat"],
        "measurement_insertion_is_physical_intervention": True,
        "paired_trajectory_note": "matched initial states, instruction and declared block schedule; old r4 VLA action prefix not replayed",
        "old_run_single_change_causal_claim": False,
        "train_raw_state_count": 3, "validation_episodes_read": False,
        "new_independent_confirmation_coverage": 0, "new_decider_training_rows": 0,
        "output_root": str(args.physical_output), "GPU_submitted": False,
        "physical_run_verified": False, "node_binding": None,
        "read_mode": "manifest-explicit files only; no artifact enumeration"}
    manifest_path = args.output / "capture_manifest.json"
    manifest_path.write_text(json.dumps(plan, indent=2) + "\n")
    python_paths = [plan["source_root"], str(parent_packet),
        str(Path(json.loads(pinned(plan["parent_manifest"]).read_text())["parent_manifest"]["path"]).parent),
        str(args.output)]
    launcher = args.output / "run_fixed_withdrawal.sbatch"
    launcher.write_text(f'''#!/usr/bin/env bash
#SBATCH --partition=gpu
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=90G
#SBATCH --time=08:00:00
#SBATCH --array=0-8%1
#SBATCH --job-name=libero-fixed-withdrawal
#SBATCH --output={root}/results/slurm-%A_%a.log
set -euo pipefail
export PYTHONPATH={shlex.quote(':'.join(python_paths))}
export MUJOCO_GL=egl PYOPENGL_PLATFORM=egl LIBERO_TYPE=standard
export LIBERO_CONFIG_PATH={shlex.quote(str(root / 'runtime_config'))}
export PI05_CHECKPOINT_PATH={shlex.quote(str(root / 'assets/pi05'))}
export SAM3_CHECKPOINT_PATH={shlex.quote(str(root / 'assets/sam3/sam3.pt'))}
export OMP_NUM_THREADS=4 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
FIXED_WITHDRAWAL_RUN={shlex.quote(str(args.physical_output))}/probe_job${{SLURM_ARRAY_JOB_ID}}
mkdir -p "$FIXED_WITHDRAWAL_RUN"
cd /tmp
FIXED_WITHDRAWAL_ARGS=(--manifest {shlex.quote(str(manifest_path))} --manifest-sha256 {identity(manifest_path)['sha256']} --shard-index "$SLURM_ARRAY_TASK_ID")
{shlex.quote(str(interpreter))} {shlex.quote(str(args.output / 'capture_fixed_withdrawal.py'))} "${{FIXED_WITHDRAWAL_ARGS[@]}}" --preflight-only --preflight-report "$FIXED_WITHDRAWAL_RUN/preflight_part${{SLURM_ARRAY_TASK_ID}}.json"
if [[ "${{FIXED_WITHDRAWAL_PREFLIGHT_ONLY:-0}}" == 1 ]]; then exit 0; fi
{shlex.quote(str(interpreter))} -u {shlex.quote(str(args.output / 'capture_fixed_withdrawal.py'))} "${{FIXED_WITHDRAWAL_ARGS[@]}}" --output "$FIXED_WITHDRAWAL_RUN/part${{SLURM_ARRAY_TASK_ID}}"
''')
    report = {"version": "stove-fixed-withdrawal-preparation/1", "manifest": identity(manifest_path),
        "collector": generated[0], "launcher": identity(launcher),
        "source_root": plan["source_root"], "interpreter": str(interpreter),
        "case_count": 9, "train_raw_states": 3, "validation_episodes_read": False,
        "GPU_submitted": False, "physical_run_verified": False, "stop_admitted": False,
        "first_physical_launch": ["sbatch", "--array=0-0%1", str(launcher)],
        "release_after_actual_controls_saved": ["sbatch", "--array=1-8%AVAILABLE_GPUS", str(launcher)]}
    (args.output / "preparation_report.json").write_text(json.dumps(report, indent=2) + "\n")
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--capture-manifest", type=Path, required=True)
    parser.add_argument("--capture-manifest-sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--physical-output", type=Path, required=True)
    args = parser.parse_args()
    if not all(path.is_absolute() for path in (args.capture_manifest, args.output, args.physical_output)):
        parser.error("All manifest, preparation and physical output paths must be absolute")
    print(json.dumps(prepare(args), indent=2))


if __name__ == "__main__":
    main()
