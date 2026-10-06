"""Run manifest-pinned original off20 cells, preserving all fixed attempts."""

import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import sys
import time

VERSION = "original-stove-off-physical-development/2-implemented"
BUDGET = {"max_chunks_per_skill": 160, "actions_per_chunk": 5, "max_episode_steps": 10000}
METHODS = ("literal_off", "paraphrase_off", "complete_knob_off", "measured_complete_knob_off")


def identity(path):
    path = Path(path)
    return {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def load_inputs(args):
    """Check every explicit source/ref and this shard's reset identities first."""
    from scripts.v5_probe_preflight import pinned_file, validate_registered_states
    from scripts import probe_v5_stove521_endpoint as inherited

    manifest, source = args.manifest, args.source
    if not manifest.is_absolute() or not source.is_absolute():
        raise ValueError("manifest and source must be absolute")
    if Path(inherited.__file__).resolve().parents[1] != source.resolve(strict=True):
        raise ValueError("imported original probe is not the registered immutable source")
    digest = identity(manifest)["sha256"]
    if digest != args.expected_manifest_sha256:
        raise ValueError("off20 manifest identity changed")
    plan = json.loads(manifest.read_text())
    if (plan["version"] != VERSION or plan["source_root"] != str(source)
            or plan["budget"] != BUDGET or plan["shards"] != 8
            or args.shards != 8 or not 0 <= args.shard_index < 8
            or len(plan["cells"]) != 20 or len(plan["methods"]) != 4
            or tuple(m["id"] for m in plan["methods"]) != METHODS
            or plan["config_overrides"] != {"dual_view_fusion_v1": True}
            or plan["diagnostic_server_module"] != "stove564_probe_env"
            or os.environ.get("LIBERO_TYPE") != "standard"):
        raise ValueError("off20 registered scope/config changed")
    if any(plan["private_scoring"][key] for key in
           ("controller_access", "affects_actions", "affects_stop", "affects_binding")):
        raise ValueError("private scoring may not control execution")
    checked, cache = [], {}
    for key in ("original_sampling_manifest", "base_config", "original_task_catalog_file", "design_manifest"):
        checked.append(pinned_file(plan[key], key, cache))
    original = json.loads(Path(plan["original_sampling_manifest"]["path"]).read_text())
    methods = {m["id"]: m for m in plan["methods"]}
    for i, cell in enumerate(plan["cells"]):
        method = methods[METHODS[i % 4]]
        case = original["cases"][i // 4]
        if (cell["original_case"] != case or cell["method"] != method["id"]
                or cell["off_prompt"] != method["off_prompt"]
                or cell["on_prompt"] != "turn on the stove"
                or cell["public_contact_refinement"] != method["public_contact_refinement"]
                or not cell["preserve_on_setup_failure_and_continue_fixed_off"]
                or case["episode"] != {"suite": "libero_goal", "task": 7, "seed": i // 4}
                or hashlib.sha256(cell["off_prompt"].encode()).hexdigest() != method["off_prompt_sha256"]):
            raise ValueError("paired original cells or fixed prompts changed")
        for field in ("bddl", "init_file"):
            checked.append(pinned_file(case[field], f"cell:{cell['name']}:{field}", cache))
    for relative, sha in plan["source_sha256"].items():
        path = source / relative
        if not path.resolve(strict=True).is_relative_to(source.resolve()):
            raise ValueError("source ref escaped the registered snapshot")
        checked.append(pinned_file({"path": str(path), "sha256": sha}, "source:" + relative, cache))
    packet = Path(plan["owned_packet_root"]).resolve(strict=True)
    if packet != Path(__file__).resolve().parent:
        raise ValueError("owned runner differs from manifest packet")
    for ref in plan["owned_files"]:
        if not Path(ref["path"]).resolve(strict=True).is_relative_to(packet):
            raise ValueError("owned source ref escaped packet")
        checked.append(pinned_file(ref, "owned_source", cache))
    resources = []
    for ref in plan["runtime_resources"]:
        path = Path(ref["path"])
        if not path.is_absolute() or not path.exists():
            raise ValueError("runtime resource is not available: " + str(path))
        if "sha256" in ref:
            checked.append(pinned_file(ref, "runtime:" + ref["role"], cache))
        resources.append({**ref, "resolved": str(path.resolve(strict=True)),
                          "bytes": path.stat().st_size if path.is_file() else None})
        if "bytes" in ref and resources[-1]["bytes"] != ref["bytes"]:
            raise ValueError("runtime resource size changed")
    base = json.loads(Path(plan["base_config"]["path"]).read_text())
    if base.get("libero_type") != "standard":
        raise ValueError("base is not original LIBERO")
    base.update(plan["config_overrides"])
    assigned = plan["cells"][args.shard_index::args.shards]
    report = {"passed": True, "manifest": identity(manifest), "source": str(source),
              "cwd": str(Path.cwd()), "files_checked": checked, "resources": resources,
              "shard_index": args.shard_index, "shards": 8,
              "assigned_cells": [c["name"] for c in assigned],
              "config_overrides": plan["config_overrides"], "explicit_files_only": True,
              "gpu_services_started": False, "simulator_started": False,
              "qualification_authorized": False, "physical_launcher_implemented": True}
    if args.check_states:
        report.update(validate_registered_states([c["original_case"] for c in assigned]))
    return plan, base, report


def run_phases(executor, sam_rpc, oracle_rpc, case, plan, output):
    """Execute fixed on/off schedule without inspecting any private scores."""
    from scripts import probe_v5_stove521_endpoint as inherited

    captures, result = {}, {"method": case["method"], "fresh_reset": True}
    def capture(stage, fresh=True):
        captures[stage] = inherited.capture_measurements(
            executor, sam_rpc, oracle_rpc, case, plan, output / stage, capture=fresh)
    with executor.p.env.complete_skill():
        capture("before_setup", fresh=False)
        result["on_setup"] = inherited.fixed_contact(executor, oracle_rpc, phase="on",
            prompt=case["on_prompt"], chunks=160)
        capture("after_setup")
        if case["public_contact_refinement"]:
            result["public_refinement"] = inherited.prepare_off_approach(
                executor, "measured_control_approach", None)
        else:
            result["public_refinement"] = {"requested": False, "method": "no_added_approach"}
        capture("before_off")
        # Setup physics failure never filters or shortens the off attempt.
        result["off_contact"] = inherited.fixed_contact(executor, oracle_rpc, phase="off",
            prompt=case["off_prompt"], chunks=160)
        capture("after_contact")
        executor.motion_evidence = []
        try:
            recovery = {"release": executor.p.release()}
            executor.retreat()
            recovery["retreat"] = "existing_public_retreat"
        except Exception as error:
            recovery = {"status": "execution_error", "error": repr(error)}
        result["public_recovery"] = {**recovery, "motion_evidence": copy.deepcopy(executor.motion_evidence)}
        capture("post_recovery")
    result.update(captures=captures, status="all_fixed_off20_stages_recorded",
        native_original_success_latched=bool(executor.p.env._native_terminated),
        external_action_budget_exhausted=bool(executor.p.env.truncated))
    return result


def score_after_cell(row, output):
    """Join labels only after the complete scheduled cell has returned."""
    label_rows = [json.loads(line) for line in (output / "labels_chunk.jsonl").read_text().splitlines()]
    phases = {}
    for phase in ("on", "off"):
        labels = [r for r in label_rows if r["phase"] == phase]
        if (len(labels) != 161 or [r["chunk_index"] for r in labels] != list(range(161))
                or any(r["status"] != "scored" or r["actual_controls"] != r["chunk_index"] * 5 for r in labels)):
            raise ValueError("missing/failed post-execution private score rows")
        phases[phase] = {"scored_rows": len(labels), "actual_controls": labels[-1]["actual_controls"]}
    setup = json.loads(Path(row["captures"]["after_setup"]["labels"]["path"]).read_text())
    contact = json.loads(Path(row["captures"]["after_contact"]["labels"]["path"]).read_text())
    final = json.loads(Path(row["captures"]["post_recovery"]["labels"]["path"]).read_text())
    satisfied = bool(setup["requested_predicates"]["turn_on"]["satisfied"])
    analysis = {"scope": "postcollection_private_labels_only", "on_setup_satisfied": satisfied,
        "on_setup_stratum": "setup_succeeded" if satisfied else "setup_failed",
        "turn_off_after_contact": contact["requested_predicates"]["turn_off"]["satisfied"],
        "turn_off_after_recovery": final["requested_predicates"]["turn_off"]["satisfied"],
        "phases": phases, "labels_chunk": identity(output / "labels_chunk.jsonl")}
    path = output / "cell_analysis_labels.json"
    path.write_text(json.dumps(analysis, indent=2) + "\n")
    return identity(path)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--expected-manifest-sha256", required=True)
    parser.add_argument("--shard-index", type=int, required=True)
    parser.add_argument("--shards", type=int, default=8)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--preflight-only", action="store_true")
    parser.add_argument("--preflight-report", type=Path)
    parser.add_argument("--check-states", action="store_true")
    args = parser.parse_args()
    plan, base, report = load_inputs(args)
    if args.preflight_report:
        if not args.preflight_report.is_absolute():
            parser.error("preflight-report must be absolute")
        args.preflight_report.parent.mkdir(parents=True, exist_ok=True)
        args.preflight_report.write_text(json.dumps(report, indent=2) + "\n")
    if args.preflight_only:
        print(json.dumps({k: report[k] for k in ("passed", "shard_index", "assigned_cells", "cwd")}), flush=True)
        return
    if args.output is None or not args.output.is_absolute():
        parser.error("physical run requires an absolute output")
    from scripts import probe_v5_stove521_endpoint as inherited
    from scripts.probe_v5_skill501_original import diagnostic_json
    from rpent.utils.daemon import ProcessDaemon, pick_free_port
    from rpent.utils.rpc import wait_for_ready
    from rpent.utils.rpc.http_rpc import HttpRpcClient

    # This process alone replaces its imported callback; shared files stay immutable.
    inherited.run_phases = run_phases
    args.output.mkdir(parents=True, exist_ok=False)
    daemons, endpoints, failures = [], {}, []
    try:
        for name, module, extra in (("sam3", "robots.libero.v5_sam3_server", []),
                ("vla", "rpent.robots.components.pi05_vla_server", ["--embodiment", "libero"])):
            port = pick_free_port()
            daemon = ProcessDaemon(name="stove564_" + name,
                cmd=[sys.executable, "-m", module, *extra, "--transport", "http", "--host", "127.0.0.1",
                     "--port", str(port), "--parent-watch"], log_path=str(args.output / ("shared_" + name + ".log")))
            daemon.start()
            daemons.append(daemon)
            endpoints[name] = f"http://127.0.0.1:{port}"
        for name, daemon in zip(("sam3", "vla"), daemons):
            wait_for_ready(HttpRpcClient(endpoints[name]), daemon=daemon, timeout_s=300)
        with (args.output / "episodes.jsonl").open("x") as ledger:
            for cell in plan["cells"][args.shard_index::args.shards]:
                case = {**cell["original_case"], **{k: v for k, v in cell.items() if k != "original_case"}}
                output = args.output / cell["name"]
                output.mkdir()
                os.environ["STOVE564_LABEL_LEDGER"] = str(output / "labels_chunk.jsonl")
                os.environ["STOVE564_CELL"] = cell["name"]
                row = {"case": case, "output_dir": str(output), "new_training_rows": 0}
                started = time.perf_counter()
                try:
                    row.update(inherited.run_case(case, base, plan, endpoints, output))
                    if any(not row[p]["fixed_prefix_completed"] for p in ("on_setup", "off_contact")):
                        raise RuntimeError("fixed 160x5 contact incomplete; retain exact executed counts")
                    row["analysis_labels"] = score_after_cell(row, output)
                except Exception as error:
                    row.update(status="probe_error", error=repr(error),
                        infrastructure_failure=True, failure_category="execution_or_probe_infrastructure")
                    failures.append(cell["name"])
                row["wall_s"] = time.perf_counter() - started
                (output / "episode.json").write_text(diagnostic_json(row, indent=2) + "\n")
                ledger.write(diagnostic_json(row) + "\n")
                ledger.flush()
                print(diagnostic_json({"cell": cell["name"], "status": row["status"], "wall_s": row["wall_s"]}), flush=True)
        if failures:
            raise RuntimeError("preserved off20 development failures: " + ", ".join(failures))
    finally:
        os.environ.pop("STOVE564_LABEL_LEDGER", None)
        os.environ.pop("STOVE564_CELL", None)
        for daemon in reversed(daemons):
            daemon.stop()


if __name__ == "__main__":
    main()
