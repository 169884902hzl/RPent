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
    if episode["suite"] == "libero_90":
        raise ValueError("historical171 harness supports original40 only; original90 needs an explicit adapter")
    run_args = argparse.Namespace(**episode, **budget, libero_type="standard", provider="oracle",
        choice_endpoint=None, choice_package=Path(payload["choice_package"]),
        sam3_endpoint=payload["sam3_endpoint"], vla_endpoint=payload["vla_endpoint"],
        output_dir=Path(payload["output"])/"legacy", done_gated=False)
    result = harness_v5_eval.run_episode(run_args)
    metadata = {"legacy_result": result,
        "source_files": [{"path": str(source/name), "sha256": hashlib.sha256((source/name).read_bytes()).hexdigest()}
                         for name in ("harness_v5_eval.py", "robots/libero/v5_runtime.py", "robots/libero/v5_state.py", "robots/libero/v5_oracle_policy.py")],
        "case": payload["case"], "budget": budget, "source": str(source)}
    (Path(payload["output"])/"legacy_result.json").write_text(json.dumps(metadata, indent=2)+"\n")
    if result.get("status") in {"startup", "startup_error"}:
        sys.exit(2)


if __name__ == "__main__":
    main()
