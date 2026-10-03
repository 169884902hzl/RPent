"""Pin original training initial states without changing collection identities."""

import argparse
import copy
import hashlib
import json
import os
from pathlib import Path

import numpy as np


def pin(manifest, benchmarks):
    if manifest["libero_type"] != "standard":
        raise ValueError("collection registration requires original LIBERO")
    result = copy.deepcopy(manifest)
    identities, states = set(), {}
    for episode in result["episodes"]:
        suite, task, init = (episode[k] for k in ("suite", "task", "seed"))
        if suite not in {"libero_spatial", "libero_object", "libero_goal", "libero_10"}:
            raise ValueError("collection suite is not an original task suite")
        if not 0 <= task < 10 or not 10 <= init < 40:
            raise ValueError("collection identity is outside original training tasks/inits")
        identity = (suite, task, init)
        if identity in identities:
            raise ValueError("duplicate collection identity")
        identities.add(identity)
        if (suite, task) not in states:
            states[suite, task] = benchmarks[suite].get_task_init_states(task)
        digest = hashlib.sha256(np.asarray(states[suite, task][init]).tobytes(order="C")).hexdigest()
        if episode.get("init_state_sha256", digest) != digest:
            raise ValueError("registered original init hash differs from installed asset")
        episode["init_state_sha256"] = digest
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if os.environ.get("LIBERO_TYPE") != "standard":
        parser.error("set LIBERO_TYPE=standard to register original collection")
    manifest = json.loads(args.manifest.read_text())
    from libero.libero.benchmark import get_benchmark

    suites = {e["suite"] for e in manifest["episodes"]}
    if suites - {"libero_spatial", "libero_object", "libero_goal", "libero_10"}:
        raise ValueError("do not load PRO assets for training registration")
    result = pin(manifest, {suite: get_benchmark(suite)() for suite in suites})
    result["init_registration"] = {
        "input_manifest": str(args.manifest),
        "input_sha256": hashlib.sha256(args.manifest.read_bytes()).hexdigest(),
        "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "source": "official original task init arrays; bytes in C order",
        "identities_and_runtime_budget_unchanged": True,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x") as stream:
        json.dump(result, stream, indent=2)
        stream.write("\n")
    print(json.dumps({"episodes": len(result["episodes"]), "output": str(args.output),
                      "sha256": hashlib.sha256(args.output.read_bytes()).hexdigest()}))


if __name__ == "__main__":
    main()
