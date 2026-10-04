"""Replay an explicit original-task skill prefix with executed action tracing."""

import argparse
import hashlib
import json
from pathlib import Path
import sys


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class ReplayScorer:
    records = []

    def __init__(self, *args, **kwargs):
        self.index = 0

    def score(self, context, instruction, options):
        if self.index >= len(self.records):
            raise ValueError("recorded prefix exhausted")
        original = self.records[self.index]
        self.index += 1
        selected = original["selected"]
        if selected not in options:
            raise ValueError("recorded selection absent from measured candidates: " + selected)
        return {
            "selected": options.index(selected), "probabilities": None,
            "model": "original-recorded-skill-prefix-not-model-evaluation",
            "request_bytes_equal_to_original": context == original["request"]["context"],
            "source_request_sha256": hashlib.sha256(
                json.dumps(original["request"], sort_keys=True).encode()).hexdigest(),
        }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--collection-config", type=Path)
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text())
    collection_config = None
    if args.collection_config is not None:
        from robots.libero.v5_collection import OriginalCollection

        if sha(args.collection_config) != manifest["collection_config_sha256"]:
            raise ValueError("registered diagnostic collection config changed")
        collection_config = json.loads(args.collection_config.read_text())
    from harness_v5_eval import run_episode
    import typed_choice_eval
    from rpent.utils.daemon import ProcessDaemon, pick_free_port
    from rpent.utils.rpc import wait_for_ready
    from rpent.utils.rpc.http_rpc import HttpRpcClient

    typed_choice_eval.ChoiceScorer = ReplayScorer
    args.output.mkdir(parents=True, exist_ok=False)
    daemons, endpoints, cases = [], {}, []
    try:
        for name, module, extra in (
            ("sam3", "robots.libero.v5_sam3_server", []),
            ("vla", "rpent.robots.components.pi05_vla_server", ["--embodiment", "libero"]),
        ):
            port = pick_free_port()
            daemon = ProcessDaemon(
                name="original_motion_" + name,
                cmd=[sys.executable, "-m", module, *extra, "--transport", "http",
                     "--host", "127.0.0.1", "--port", str(port), "--parent-watch"],
                log_path=str(args.output / ("shared_" + name + ".log")),
            )
            daemon.start()
            daemons.append(daemon)
            endpoints[name] = "http://127.0.0.1:" + str(port)
        for name, daemon in zip(("sam3", "vla"), daemons):
            wait_for_ready(HttpRpcClient(endpoints[name]), daemon=daemon, timeout_s=300)
        with (args.output / "episodes.jsonl").open("x") as ledger:
            for case in manifest["cases"]:
                trace, config = Path(case["trace"]), Path(case["config"])
                if sha(trace) != case["trace_sha256"] or sha(config) != case["config_sha256"]:
                    raise ValueError("registered original recording changed")
                cfg = json.loads(config.read_text())
                if cfg["libero_type"] != "standard" or cfg["suite"] not in {
                    "libero_spatial", "libero_object", "libero_goal", "libero_10"
                }:
                    raise ValueError("physical diagnostic requires original tasks")
                original = [json.loads(line) for line in trace.read_text().splitlines()
                            if line.strip()][:case["prefix_decisions"]]
                if len(original) != case["prefix_decisions"]:
                    raise ValueError("recording shorter than declared prefix")
                ReplayScorer.records = original
                cfg.update(
                    provider="qwen27", choice_endpoint="recorded-prefix://no-model-service",
                    sam3_endpoint=endpoints["sam3"], vla_endpoint=endpoints["vla"],
                    choice_package=Path(manifest["choice_package"]),
                    output_dir=args.output / case["name"],
                    max_decisions=len(original), motion_trace_v1=True,
                )
                # The original runtime parameters remain unchanged; only the
                # diagnostic motion trace and finite replay length are enabled.
                if collection_config is None:
                    cfg.pop("init_state_sha256", None)
                run_args = argparse.Namespace(**cfg)
                collection = (OriginalCollection(collection_config, run_args.output_dir, run_args)
                              if collection_config is not None else None)
                raised = None
                try:
                    result = run_episode(run_args, collection=collection)
                except Exception as error:
                    raised = repr(error)
                    result_path = run_args.output_dir / "result.json"
                    result = json.loads(result_path.read_text()) if result_path.exists() else {
                        "status": "startup_error", "error": raised}
                if collection is not None:
                    collection.finish(result)
                path = run_args.output_dir / "choices.jsonl"
                executed = [json.loads(line) for line in path.read_text().splitlines()
                            if line.strip()] if path.exists() else []
                record = {
                    "case": case, "output_dir": str(run_args.output_dir), "result": result,
                    "raised_error": raised, "recorded_decisions": len(executed),
                    "reached_registered_prefix_end": len(executed) == len(original),
                    "choices": {"path": str(path), "sha256": sha(path) if path.exists() else None},
                    "receipt_errors": [x["receipt"] for x in executed if x["receipt"].get("error")],
                    "request_equal_count": sum(bool(x["answer"].get("request_bytes_equal_to_original"))
                                               for x in executed),
                    "executed_vla_actions": sum(
                        m.get("executed_action_count", 0)
                        for x in executed for m in x.get("motion_evidence", [])),
                    "physical_branch_replay": collection is not None,
                }
                ledger.write(json.dumps(record) + "\n")
                ledger.flush()
                cases.append(record)
                print(json.dumps({k: record[k] for k in (
                    "recorded_decisions", "reached_registered_prefix_end", "receipt_errors",
                    "request_equal_count", "executed_vla_actions")}), flush=True)
    finally:
        for daemon in reversed(daemons):
            daemon.stop()
        report = {
            "scope": "Original-task recorded skill prefix diagnosis; no model score, no training rows, no full-task claim. Pi05 is executed afresh; request/physics divergence must be examined.",
            "manifest_sha256": sha(args.manifest), "script_sha256": sha(__file__),
            "interpreter": sys.executable, "cases": cases,
            "new_training_rows": 0, "state_or_candidate_format_modified": False,
            "collection_config_sha256": sha(args.collection_config) if args.collection_config else None,
            "diagnostic_branch_files_role": "quarantined diagnosis only; never a training input",
        }
        (args.output / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    if not cases or any(not case["reached_registered_prefix_end"] for case in cases):
        raise RuntimeError("original motion diagnostic incomplete; inspect preserved logs")


if __name__ == "__main__":
    main()
