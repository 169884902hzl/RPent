"""Validate explicit registered rawstates before using the unchanged skill runner."""

import argparse
import hashlib
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--shard-index", type=int, default=0)
    parser.add_argument("--shards", type=int, default=8)
    parser.add_argument("--states", action="store_true")
    args = parser.parse_args()
    from scripts.v5_probe_preflight import load_pinned_manifest, pinned_file
    import numpy as np
    from rlinf.envs.libero.utils import benchmark

    _, plan, _ = load_pinned_manifest(args.manifest)
    if len(plan["cases"]) != 24 or plan["selection"]["analysis_role"] != "registered_layout_confirmation24":
        raise ValueError("Only the registered 24 new layouts are allowed")
    suite = benchmark.get_benchmark("libero_90")()
    initial = suite.get_task_init_states(19)
    for reference in [*plan["source_snapshot"]["files"], plan["source_snapshot"]["archive"],
                      *plan["producer_dependencies"]]:
        pinned_file(reference, "source_or_adapter")
    selected = plan["cases"][args.shard_index::args.shards]
    audits = []
    for case in selected:
        reference = case["registered_layout_state"]
        pinned_file(reference, "registered_layout_state")
        value = json.loads(Path(reference["path"]).read_text())
        state = np.asarray(value["rawstate"], dtype="<f8", order="C")
        digest = hashlib.sha256(state.tobytes()).hexdigest()
        if (digest != case["state_sha256"] or value["episode"] != case["episode"]
                or state.shape != np.asarray(initial[case["episode"]["seed"]]).shape
                or not np.isfinite(state).all()):
            raise ValueError("Registered layout bytes/shape/episode differ")
        audits.append({"name": case["name"], "state_sha256": digest,
                       "geometry_fingerprint": case["geometry_fingerprint"],
                       "layout_seed": value["layout_seed"]})
    print(json.dumps({**plan["preflight"], "registered_layout_states_checked": len(audits),
                      "layout_audit": audits, "GPU_started": False,
                      "physics_executed": False, "qualification": False}, indent=2))


if __name__ == "__main__":
    main()
