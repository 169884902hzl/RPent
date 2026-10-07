"""Original literal off with public chunk observation and separate recovery."""

import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import sys
import time
from types import SimpleNamespace


def identity(path):
    path = Path(path)
    return {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def load_inputs(args):
    from probe_off20 import load_inputs as load_parent
    from scripts.v5_probe_preflight import pinned_file, validate_registered_states

    if identity(args.manifest)["sha256"] != args.expected_manifest_sha256:
        raise ValueError("registered public-observation probe manifest changed")
    plan = json.loads(args.manifest.read_text())
    if (plan["version"] != "original-stove-public-red-recovery/1-dev" or plan["shards"] != 5
            or not 0 <= args.shard_index < 5 or Path(plan["owned_packet_root"]).resolve() != Path('/public/home/sunyihan/rpent_libero_eval/results/harness_v5/stove568_public_stop_selection_CPU_20261006').resolve()
            or plan["public_stop_enabled"] is not False or plan["fixed_on_chunks"] != 160
            or plan["fixed_off_chunks"] != 160 or plan["off_prompt"] != "turn off the stove"):
        raise ValueError("original observation-only literal protocol changed")
    parent, base, parent_preflight = load_parent(SimpleNamespace(manifest=Path(plan["parent_manifest"]["path"]),
        source=Path(plan["source_root"]), expected_manifest_sha256=plan["parent_manifest"]["sha256"],
        shards=8, shard_index=0, check_states=False))
    cases = [c["original_case"] for c in parent["cells"] if c["method"] == "literal_off"]
    if cases != plan["cases"]:
        raise ValueError("only the five explicit parent original states are allowed")
    checked = [pinned_file(plan["public_stop_calibration"], "public_stop_calibration")]
    calibration = json.loads(Path(plan["public_stop_calibration"]["path"]).read_text())
    if calibration["endpoint_stop_admitted"] is not False or calibration["red_fraction_threshold"] is not None:
        raise ValueError("unseparable endpoint must not acquire a stop threshold")
    for reference in plan["owned_files"]:
        checked.append(pinned_file(reference, "owned_source"))
    assigned = [plan["cases"][args.shard_index]]
    report = {"passed": True, "cwd": str(Path.cwd()), "manifest": identity(args.manifest),
        "parent_preflight": parent_preflight, "owned_files_checked": checked,
        "assigned_cases": [c["name"] for c in assigned], "shard_index": args.shard_index,
        "public_stop_enabled": False, "observer_only": True, "private_labels_control_execution": False,
        "simulator_started": False, "GPU_services_started": False}
    if args.check_states:
        report.update(validate_registered_states(assigned))
    # Inherit the already-pinned capture schema and original asset budget.
    runtime_plan = {**parent, **plan, "diagnostic_server_module": "control580_off320_probe_env"}
    runtime_plan["public_calibration"] = calibration
    return runtime_plan, base, report


def run_phases(executor, sam_rpc, oracle_rpc, case, plan, output):
    from scripts import probe_v5_stove521_endpoint as inherited
    from scripts.probe_v5_skill501_original import diagnostic_json, executed_actions
    from public_red_observer import observe

    result = {"captures": {}, "off_prompt": "turn off the stove", "public_stop_enabled": False}
    def capture(name, fresh=True):
        result["captures"][name] = inherited.capture_measurements(executor, sam_rpc, oracle_rpc,
            case, plan, output / name, capture=fresh)
    with executor.p.env.complete_skill():
        capture("before_setup", fresh=False)
        result["on_setup"] = inherited.fixed_contact(executor, oracle_rpc, phase="on",
            prompt="turn on the stove", chunks=160)
        capture("after_setup")
        capture("before_off")
        step = executor.toolkit._state.latest_step
        shells = [e for e in executor.scene.entities.values() if e.name == "stove" and e.visible and e.source_step == step]
        cached_shell = copy.deepcopy(shells[0]) if len(shells) == 1 else None
        executor.motion_evidence = []
        off = {"prompt": "turn off the stove", "chunks": 0, "public_stop": False}
        scope_started = False
        try:
            oracle_rpc.call("diagnostic.stove_chunk_start", kwargs={"phase": "off", "max_chunks": 160}, timeout_s=120)
            scope_started = True
            with (output / "public_red_chunks.jsonl").open("x") as ledger:
                for index in range(160):
                    receipt = executor.vla_act("turn off the stove", 1, "chunk_budget")
                    if receipt.get("chunks") != 1:
                        raise RuntimeError("off chunk did not execute its five controls")
                    off["chunks"] += 1
                    observed = observe(executor, cached_shell, plan["public_calibration"])
                    ledger.write(diagnostic_json({"chunk_index": index + 1, **observed}) + "\n")
                    ledger.flush()
                    # Public-only gate is implemented, but selection shows no
                    # admitted endpoint. Current probe therefore never stops here.
                    if observed["stop_decision"]["stop"]:
                        off["public_stop"] = True
                        break
        except Exception as error:
            off.update(status="execution_error", error=repr(error))
        finally:
            if scope_started:
                off["chunk_completion_scope"] = oracle_rpc.call("diagnostic.stove_chunk_end", timeout_s=120)
        off["executed_control_actions"] = executed_actions(executor.motion_evidence)
        off["motion_evidence"] = copy.deepcopy(executor.motion_evidence)
        result["off_contact"] = off
        capture("after_contact")
        executor.motion_evidence = []
        try:
            result["release_only"] = {"receipt": executor.p.release()}
        except Exception as error:
            result["release_only"] = {"status": "execution_error", "error": repr(error)}
        capture("after_release")
        executor.motion_evidence = []
        try:
            executor.retreat()
            result["retreat_only"] = {"executed": True}
        except Exception as error:
            result["retreat_only"] = {"status": "execution_error", "error": repr(error)}
        result["retreat_only"]["motion_evidence"] = copy.deepcopy(executor.motion_evidence)
        capture("after_retreat")
    result.update(status="all_public_observation_and_recovery_stages_recorded",
        native_original_success_latched=bool(executor.p.env._native_terminated),
        external_action_budget_exhausted=bool(executor.p.env.truncated))
    return result


def postcollection_score(row, output):
    """Private labels are read only after both recovery stages are finished."""
    labels = [json.loads(line) for line in (output / "labels_chunk.jsonl").read_text().splitlines()]
    if len(labels) != 482 or any(r["status"] != "scored" for r in labels):
        raise RuntimeError("unknown private scores; completed cell is infrastructure-invalid")
    for phase in ("on", "off"):
        records = [r for r in labels if r["phase"] == phase]
        if ([r["chunk_index"] for r in records] != list(range(161 if phase == "on" else 321))
                or any(r["actual_controls"] != r["chunk_index"] * 5 for r in records)):
            raise RuntimeError("private scoring/action counts are incomplete")
    stage_labels = {stage: json.loads(Path(refs["labels"]["path"]).read_text())
                    for stage, refs in row["captures"].items()}
    scores = {"scope": "private_postcollection_scoring_only", "stage_labels": stage_labels,
              "on_setup_satisfied": stage_labels["after_setup"]["requested_predicates"]["turn_on"]["satisfied"],
              "labels_chunk": identity(output / "labels_chunk.jsonl"),
              "public_red_chunks": identity(output / "public_red_chunks.jsonl")}
    path = output / "postcollection_private_scores.json"
    path.write_text(json.dumps(scores, indent=2) + "\n")
    return identity(path)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--expected-manifest-sha256", required=True)
    parser.add_argument("--shard-index", type=int, required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--preflight-only", action="store_true")
    parser.add_argument("--preflight-report", type=Path)
    parser.add_argument("--check-states", action="store_true")
    args = parser.parse_args()
    plan, base, report = load_inputs(args)
    if args.preflight_report:
        args.preflight_report.parent.mkdir(parents=True, exist_ok=True)
        args.preflight_report.write_text(json.dumps(report, indent=2) + "\n")
    if args.preflight_only:
        print(json.dumps({"passed": True, "case": report["assigned_cases"], "cwd": report["cwd"], "observer_only": True}))
        return
    if args.output is None or not args.output.is_absolute():
        parser.error("physical output must be absolute")
    from scripts import probe_v5_stove521_endpoint as inherited
    from scripts.probe_v5_skill501_original import diagnostic_json
    from rpent.utils.daemon import ProcessDaemon, pick_free_port
    from rpent.utils.rpc import wait_for_ready
    from rpent.utils.rpc.http_rpc import HttpRpcClient

    args.output.mkdir(parents=True, exist_ok=False)
    inherited.run_phases = run_phases
    daemons, endpoints = [], {}
    try:
        for name, module, extra in (("sam3", "robots.libero.v5_sam3_server", []),
            ("vla", "rpent.robots.components.pi05_vla_server", ["--embodiment", "libero"])):
            port = pick_free_port()
            daemon = ProcessDaemon(name="stove568_" + name, cmd=[sys.executable, "-m", module, *extra,
                "--transport", "http", "--host", "127.0.0.1", "--port", str(port), "--parent-watch"],
                log_path=str(args.output / ("shared_" + name + ".log")))
            daemon.start()
            daemons.append(daemon)
            endpoints[name] = f"http://127.0.0.1:{port}"
        for name, daemon in zip(("sam3", "vla"), daemons):
            wait_for_ready(HttpRpcClient(endpoints[name]), daemon=daemon, timeout_s=300)
        case = plan["cases"][args.shard_index]
        directory = args.output / case["name"]
        directory.mkdir()
        os.environ["STOVE564_LABEL_LEDGER"] = str(directory / "labels_chunk.jsonl")
        os.environ["STOVE564_CELL"] = case["name"]
        row = {"case": case, "output_dir": str(directory), "new_training_rows": 0}
        started = time.perf_counter()
        try:
            row.update(inherited.run_case(case, base, plan, endpoints, directory))
            if (not row["on_setup"]["fixed_prefix_completed"] or row["off_contact"]["chunks"] != 320
                    or row["off_contact"].get("executed_control_actions") != 1600):
                raise RuntimeError("fixed contact controls incomplete")
            if any(row[stage].get("status") == "execution_error" for stage in ("release_only", "retreat_only")):
                raise RuntimeError("preserved recovery execution fault; cell is infrastructure-invalid")
            row["private_scores"] = postcollection_score(row, directory)
        except Exception as error:
            row.update(status="probe_error", error=repr(error), infrastructure_failure=True,
                       failure_category="execution_or_scoring_infrastructure")
        row["wall_s"] = time.perf_counter() - started
        (directory / "episode.json").write_text(diagnostic_json(row, indent=2) + "\n")
        (args.output / "episodes.jsonl").write_text(diagnostic_json(row) + "\n")
        print(diagnostic_json({"case": case["name"], "status": row["status"], "wall_s": row["wall_s"]}), flush=True)
        if row["status"] == "probe_error":
            raise RuntimeError("preserved original public-observation probe infrastructure failure")
    finally:
        os.environ.pop("STOVE564_LABEL_LEDGER", None)
        os.environ.pop("STOVE564_CELL", None)
        for daemon in reversed(daemons):
            daemon.stop()


if __name__ == "__main__":
    main()
