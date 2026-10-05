"""Replay explicit successful development prefixes under one changed flag."""

import argparse
import hashlib
import json
from pathlib import Path
import sys

from scripts.replay_v5_original_motion import ReplayScorer, prefix_outcome


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--shard-index", type=int, required=True)
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text())
    from harness_v5_eval import run_episode
    import typed_choice_eval
    from rpent.utils.daemon import ProcessDaemon, pick_free_port
    from rpent.utils.rpc import wait_for_ready
    from rpent.utils.rpc.http_rpc import HttpRpcClient

    typed_choice_eval.ChoiceScorer = ReplayScorer
    args.output.mkdir(parents=True, exist_ok=False)
    daemons, endpoints, records = [], {}, []
    try:
        for name, module, extra in (
            ("sam3", "robots.libero.v5_sam3_server", []),
            ("vla", "rpent.robots.components.pi05_vla_server", ["--embodiment", "libero"]),
        ):
            port = pick_free_port()
            daemon = ProcessDaemon(name="regression448_" + name,
                cmd=[sys.executable, "-m", module, *extra, "--transport", "http",
                     "--host", "127.0.0.1", "--port", str(port), "--parent-watch"],
                log_path=str(args.output / ("shared_" + name + ".log")))
            daemon.start()
            daemons.append(daemon)
            endpoints[name] = f"http://127.0.0.1:{port}"
        for name, daemon in zip(("sam3", "vla"), daemons):
            wait_for_ready(HttpRpcClient(endpoints[name]), daemon=daemon, timeout_s=300)
        with (args.output / "episodes.jsonl").open("x") as ledger:
            for case in manifest["cases"][args.shard_index::2]:
                trace, config = Path(case["trace"]), Path(case["config"])
                assert sha(trace) == case["trace_sha256"] and sha(config) == case["config_sha256"]
                cfg = json.loads(config.read_text())
                assert cfg["libero_type"] == "pro" and cfg["seed"] == 40
                original = [json.loads(line) for line in trace.read_text().splitlines()
                            if line.strip()][:case["prefix_decisions"]]
                ReplayScorer.records = original
                cfg.update(case["overrides"])
                cfg.update(provider="qwen27", choice_endpoint="recorded-prefix://diagnostic-only",
                    sam3_endpoint=endpoints["sam3"], vla_endpoint=endpoints["vla"],
                    choice_package=Path(manifest["choice_package"]),
                    output_dir=args.output / case["name"], max_decisions=len(original),
                    motion_trace_v1=True)
                cfg.pop("init_state_sha256", None)
                run_args = argparse.Namespace(**cfg)
                raised = None
                try:
                    result = run_episode(run_args)
                except Exception as error:
                    raised = error
                    result_path = run_args.output_dir / "result.json"
                    result = json.loads(result_path.read_text()) if result_path.exists() else {
                        "status": "startup_error", "error": repr(error)}
                path = run_args.output_dir / "choices.jsonl"
                executed = [json.loads(line) for line in path.read_text().splitlines()
                            if line.strip()] if path.exists() else []
                record = {"case": case, "result": result,
                    "output_dir": str(run_args.output_dir), "raised_error": repr(raised) if raised else None,
                    "recorded_decisions": len(executed),
                    "diagnostic_outcome": prefix_outcome(len(executed), len(original), result, raised),
                    "request_equal_count": sum(bool(x["answer"].get("request_bytes_equal_to_original"))
                                               for x in executed),
                    "receipts": [{"decision": x["decision"], "selected": x["selected"],
                                  "receipt": x["receipt"]} for x in executed],
                    "choices_sha256": sha(path) if path.exists() else None}
                ledger.write(json.dumps(record) + "\n")
                ledger.flush()
                records.append(record)
                print(json.dumps({"case": case["name"], "outcome": record["diagnostic_outcome"],
                                  "decisions": len(executed), "error": record["raised_error"]}), flush=True)
    finally:
        for daemon in reversed(daemons):
            daemon.stop()
        (args.output / "report.json").write_text(json.dumps({
            "scope": "diagnostic prefixes, not model scores or training rows; physical divergence is explicit",
            "manifest_sha256": sha(args.manifest), "script_sha256": sha(__file__),
            "interpreter": sys.executable, "cases": records}, indent=2) + "\n")
    if not records or any(x["diagnostic_outcome"] == "runtime_error" for x in records):
        raise RuntimeError("diagnostic infrastructure failed; inspect preserved case evidence")


if __name__ == "__main__":
    main()
