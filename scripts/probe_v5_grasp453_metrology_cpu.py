"""Check private grasp geometry and the unheld negative control on CPU."""

import argparse
import hashlib
import json
from pathlib import Path
import time


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    plan = json.loads(args.manifest.read_text())
    assert plan["truth_protocol"]["runtime_truth_allowed"] is False
    from robots.libero.v5_env_server import make_v5_env
    from robots.libero.v5_runtime import category

    cases = {}
    for case in plan["cases"]:
        cases.setdefault(case["group"], case)
    rows = []
    args.output.mkdir(parents=True, exist_ok=False)
    for group, case in cases.items():
        ep = case["episode"]
        if ep["suite"] not in ("libero_spatial", "libero_object", "libero_goal", "libero_10"):
            raise ValueError("metrology controls are original-task only")
        started = time.perf_counter()
        env = make_v5_env(ep["task"], ep["seed"], ep["suite"], 10000,
                          branch_state=True, deterministic_reset_v1=True)
        try:
            env.reset()
            worker = env.env.workers[0]
            contacts = worker.env_call("v5_grasp_contacts", target="self")
            names = [name for name in contacts["objects"] if category(name) == case["category"]]
            if len(names) != 1:
                raise ValueError(f"negative control has no unique object: {group}: {names}")
            name = names[0]
            reference = worker.env_call("v5_grasp_reference", args=[name], target="self")
            hold = worker.env_call("v5_measure_grasp_hold",
                                   args=[name, reference, plan["truth_protocol"]["hold_duration_s"]],
                                   target="self")
            row = {"group": group, "episode": ep, "target": name,
                   "reference": reference, "hold": hold, "wall_s": time.perf_counter() - started}
            rows.append(row)
            (args.output / (group + ".json")).write_text(json.dumps(row, indent=2) + "\n")
            if hold["truth"]["success"] or hold["truth"]["duration_s"] < .5 - 1e-8:
                raise RuntimeError("unheld control or physical hold clock failed")
            print(json.dumps({"group": group, "negative_control_passed": True,
                              "samples": hold["truth"]["samples"],
                              "duration_s": hold["truth"]["duration_s"]}), flush=True)
        finally:
            env.close()
    report = {"scope": "CPU reset/unheld metrology controls; no policy grasp or task score",
              "manifest_sha256": sha(args.manifest), "script_sha256": sha(Path(__file__)),
              "classes": len(rows), "all_unheld_negative_controls_passed": len(rows) == len(cases),
              "new_training_rows": 0, "rows": rows}
    path = args.output / "report.json"
    path.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"report": str(path), "sha256": sha(path)}))


if __name__ == "__main__":
    main()
