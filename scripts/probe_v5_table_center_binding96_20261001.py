# Copyright 2026 Zhilun Hu.
# SPDX-License-Identifier: Apache-2.0
"""Compare a measured tabletop anchor with the existing object-centre estimate."""

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from types import SimpleNamespace

from robots.libero.v5_oracle_policy import OriginalOraclePolicy
from robots.libero.v5_runtime import MeasuredScene
from rpent.utils.rpc.http_rpc import HttpRpcClient
from scripts.replay_v5_saved_perception_cohort_20261001 import SavedFrame


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--manifest", type=Path, required=True)
    p.add_argument("--endpoint", required=True)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    plan = json.loads(args.manifest.read_text())
    args.output.mkdir(parents=True, exist_ok=False)
    client = HttpRpcClient(args.endpoint)
    rows = []
    for index, frame in enumerate(plan["frames"]):
        record = {"frame": frame["key"]}
        for mode in ("existing_estimate", "measured_table"):
            queries = []

            def call(method, *, kwargs, timeout_s):
                result = client.call(method, kwargs=kwargs, timeout_s=timeout_s)
                queries.append({"query": kwargs["text_prompt"], "min_score": kwargs["min_score"],
                                "scores": [x["score"] for x in result["instances"]]})
                return result

            names = frame["public_object_categories"] + (["table"] if mode == "measured_table" else [])
            scene = MeasuredScene(SimpleNamespace(_state=SavedFrame(frame)), SimpleNamespace(call=call), index)
            scene.instance_limits = Counter(names)
            scene.refresh(sorted(set(names)))
            entities = list(scene.entities.values())
            bound = OriginalOraclePolicy(None).bind("bowl", entities, frame["instruction"], scene.view_axes)
            record[mode] = {
                "binding": bound.id if bound else None,
                "binding_xyz": bound.xyz if bound else None,
                "queries": queries,
                "visible_categories": dict(Counter(e.name for e in entities if e.visible)),
                "entities": [{"id": e.id, "name": e.name, "xyz": e.xyz,
                              "lower": e.lower, "upper": e.upper, "visible": e.visible}
                             for e in entities],
            }
        rows.append(record)
        (args.output / "frames.json").write_text(json.dumps(rows, indent=2) + "\n")
    report = {"purpose": "saved RGB-D binding diagnosis only; no physical episodes or training labels",
              "manifest_sha256": hashlib.sha256(args.manifest.read_bytes()).hexdigest(),
              "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              "frames": rows}
    (args.output / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"output": str(args.output), "bindings": [
        {"frame": r["frame"], "before": r["existing_estimate"]["binding_xyz"],
         "after": r["measured_table"]["binding_xyz"],
         "visible": r["measured_table"]["visible_categories"]} for r in rows]}))


if __name__ == "__main__":
    main()
