"""Selection smoke on ten explicitly indexed original-task RGB-D events."""
import argparse
from dataclasses import asdict
import hashlib
import json
from pathlib import Path

import imageio.v3 as iio
import numpy as np

from robots.libero.v5_stove_measurement import DEFAULT_PARAMETERS, VERSION, measure_stove_rgbd, measured_stove_endpoint


def source(path):
    return {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text())
    args.output.mkdir(parents=True, exist_ok=False)
    rows = []
    for event in manifest["events"]:
        obj = event["receipt"]["object"]
        entity = event["fixture_evidence"][obj]["parent"]
        record = {"episode": event["episode"], "decision": event["decision"], "trace": event["trace"],
                  "cached_pre_action_perception_entity": entity, "views": {}}
        for view in ("agentview", "wrist"):
            measurements = []
            for stage in ("decision_frame_step", "post_frame_step"):
                step = event[stage]
                image_path = Path(event["output"]) / (view + "_high.png") / f"{step:02d}.png"
                world_path = Path(event["output"]) / (view + "_world_high.npz") / f"{step:02d}.npz"
                image = iio.imread(image_path)[..., :3]
                with np.load(world_path) as archive:
                    world = archive["array"]
                measurement = measure_stove_rgbd(image, world, entity, step, view)
                measurement["input_files"] = [source(image_path), source(world_path)]
                measurements.append(measurement)
            before, after = measurements
            verdict, evidence = measured_stove_endpoint(before, after, "turn_on")
            record["views"][view] = {"before": before, "after": after, "turn_on_verdict": verdict, "evidence": evidence}
        rows.append(record)
    report = {"scope": "selection smoke, not independent qualification or off confirmation",
              "module_version": VERSION, "module": source(Path("robots/libero/v5_stove_measurement.py")),
              "script": source(Path(__file__)), "manifest": source(args.manifest),
              "parameters": asdict(DEFAULT_PARAMETERS), "events": rows,
              "after_on_main": sum(r["views"]["agentview"]["turn_on_verdict"] is True for r in rows),
              "total_events": len(rows),
              "main_before_on": sum(r["views"]["agentview"]["before"]["state"] == "on" for r in rows),
              "limitations": ["All original events were turn_on; turn_off still needs independent on/off evidence.",
                              "The source events selected these development features and cannot confirm their accuracy.",
                              "World coordinates and stove bounds come from calibrated RGB-D perception only.",
                              "Full support samples are audit evidence and must not enter planner text."]}
    path = args.output / "report.json"
    path.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"report": source(path), "after_on_main": report["after_on_main"],
                      "total_events": len(rows), "main_before_on": report["main_before_on"],
                      "main_red_fractions": [r["views"]["agentview"]["after"]["features"]["red_fraction"] for r in rows]}))


if __name__ == "__main__":
    main()
