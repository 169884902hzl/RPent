"""Run one original40 control using the unchanged historical harness modules.

Invoke this file with PYTHONPATH/cwd set to the hash-pinned legacy snapshot.
It borrows only the parent-owned SAM/VLA endpoints and writes separate logs.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--payload", type=Path, required=True)
    args = parser.parse_args()
    payload = json.loads(args.payload.read_text())
    source = Path(payload["source"]).resolve(strict=True)
    import harness_v5_eval
    if Path(harness_v5_eval.__file__).resolve() != source/"harness_v5_eval.py":
        raise ValueError("legacy harness imported from a different snapshot")
    budget = payload["budget"]
    if budget.get("vla_task_v1") or budget["max_episode_steps"] != 10000:
        raise ValueError("legacy control must disable whole-task VLA and use the paired budget")
    episode = payload["case"]["episode"]
    original90_adapter = episode["suite"] == "libero_90"
    if original90_adapter:
        if not payload.get("allow_original90_adapter"):
            raise ValueError("historical171 requires an explicit original90 diagnostic admission adapter")
        def admit_original90(args, collection=None):
            if args.provider != "oracle" or args.libero_type != "standard" or args.suite != "libero_90" or collection is not None:
                raise ValueError("original90 control adapter is original, diagnostic and uncollected only")
            return True
        # Only the historical single-grasp admission guard changes; action
        # selection, executor, public sensing and budgets remain hash-pinned.
        harness_v5_eval._original90_grasp_diagnostic = admit_original90
    import numpy as np
    from robots.libero.env_client import LiberoEnvClient
    # Cold asset/EGL setup exceeded the historical120s reset RPC timeout in
    # one development worker. This changes startup waiting, never actions or
    # the10,000-step physical budget, and affects only this child process.
    LiberoEnvClient._TIMEOUT_S = {**LiberoEnvClient._TIMEOUT_S, "env.reset": 300.}
    original_step, original_chunk = LiberoEnvClient.step, LiberoEnvClient.chunk_step
    public_budget = {"used_sim_steps": 0, "source": "counted_public_step_and_returned_chunk_controls"}
    def measured_step(env, action):
        result = original_step(env, action)
        public_budget["used_sim_steps"] += 1
        return result
    def measured_chunk(env, actions, **kwargs):
        result = original_chunk(env, actions, **kwargs)
        public_budget["used_sim_steps"] += int(np.asarray(result[2]).size)
        return result
    LiberoEnvClient.step, LiberoEnvClient.chunk_step = measured_step, measured_chunk
    run_args = argparse.Namespace(**episode, **budget, libero_type="standard", provider="oracle",
        choice_endpoint=None, choice_package=Path(payload["choice_package"]),
        sam3_endpoint=payload["sam3_endpoint"], vla_endpoint=payload["vla_endpoint"],
        output_dir=Path(payload["output"])/"legacy", done_gated=False)
    try:
        result = harness_v5_eval.run_episode(run_args)
    except Exception:
        # The unchanged historical harness saves its measured final state in
        # finally, then rethrows policy failures such as NoLegalCandidate.
        # Preserve that physical failure and continue the cohort; startup and
        # infrastructure errors still produce a nonzero worker exit.
        saved = run_args.output_dir/"result.json"
        if not saved.is_file():
            raise
        result = json.loads(saved.read_text())
        if result.get("infrastructure_failure", True) or "official_success" not in result:
            raise
    metadata = {"legacy_result": result, "public_execution_budget": public_budget,
        "source_files": [{"path": str(source/name), "sha256": hashlib.sha256((source/name).read_bytes()).hexdigest()}
                         for name in ("harness_v5_eval.py", "robots/libero/v5_runtime.py", "robots/libero/v5_state.py", "robots/libero/v5_oracle_policy.py")],
        "case": payload["case"], "budget": budget, "source": str(source),
        "infrastructure_adapter": {"env_reset_timeout_s": 300.},
        "original90_diagnostic_admission_adapter": original90_adapter}
    (Path(payload["output"])/"legacy_result.json").write_text(json.dumps(metadata, indent=2)+"\n")
    if result.get("status") in {"startup", "startup_error"} or result.get("infrastructure_failure"):
        sys.exit(2)


if __name__ == "__main__":
    main()
