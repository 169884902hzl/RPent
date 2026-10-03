"""Exercise the runtime appliance detector on one explicit original capture."""

import argparse
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np

from robots.libero.v5_runtime import MeasuredScene
from robots.libero.v5_state import entity_record


class SavedState:
    """Present the same immutable camera artifacts to both runtime conditions."""

    latest_step = 0

    def __init__(self, inputs, output):
        self.inputs, self.output = inputs, output

    def load(self, name):
        path = Path(self.inputs[name])
        if name.endswith(".json"):
            return json.loads(path.read_text())
        with np.load(path) as data:
            return data[data.files[0]].copy()

    def load_bytes(self, name):
        return Path(self.inputs[name]).read_bytes()

    def save(self, name, value, step):
        path = self.artifact_path(name, step=step)
        path.parent.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(path, value)
        return path

    def artifact_path(self, name, step):
        return self.output / name / f"{step:02d}.npz"


class DirectSampler:
    def __init__(self, facade):
        self.facade = facade

    def call(self, name, kwargs, timeout_s):
        if name != "sam3.segment_all":
            raise ValueError(name)
        return self.facade.segment_all(**kwargs)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--checkpoint", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--instance-geometry-v4", action="store_true")
    parser.add_argument("--support-crop-v5", action="store_true")
    parser.add_argument("--door-cloud-v6", action="store_true")
    parser.add_argument("--door-dual-view", action="store_true", help="Compare distinct door clouds from both measured views")
    parser.add_argument("--endpoint", help="Reuse an owned warm SAM service for read-only diagnosis")
    args = parser.parse_args()
    case = json.loads(args.manifest.read_text())
    if case["suite"] not in ("libero_spatial", "libero_object", "libero_goal", "libero_10"):
        raise ValueError("appliance diagnosis is original-task-only")
    args.output.mkdir(parents=True, exist_ok=False)
    if args.endpoint:
        from rpent.utils.rpc.http_rpc import HttpRpcClient
        sampler = HttpRpcClient(args.endpoint)
    else:
        from robots.libero.v5_sam3_server import V5Sam3Facade
        sampler = DirectSampler(V5Sam3Facade(args.checkpoint))
    report = {"purpose": "saved original capture runtime diagnosis, not an episode or training rows",
              "manifest_sha256": hashlib.sha256(args.manifest.read_bytes()).hexdigest(),
              "inputs": {name: {"path": path, "sha256": hashlib.sha256(Path(path).read_bytes()).hexdigest()}
                         for name, path in case["inputs"].items()}, "conditions": {}}
    conditions = ("control", "recall", "recall_instances") if args.instance_geometry_v4 or args.support_crop_v5 or args.door_cloud_v6 else ("control", "recall")
    if args.support_crop_v5 or args.door_cloud_v6:
        conditions += ("support_crop",)
    if args.door_cloud_v6:
        conditions += ("door_cloud",)
    if args.door_dual_view:
        if not args.door_cloud_v6:
            raise ValueError("door dual-view diagnosis requires --door-cloud-v6")
        conditions += ("door_dual_view",)
    for condition in conditions:
        output = args.output / condition
        output.mkdir()
        state = SavedState(case["inputs"], output)
        scene = MeasuredScene(SimpleNamespace(_state=state), sampler, 0,
                              furniture_parts_v1=True, instruction_queries_v1=True,
                              fixture_support_filter_v1=True, fixture_front_geometry_v1=True,
                              microwave_recall_geometry_v3=condition != "control",
                              microwave_instance_geometry_v4=condition in ("recall_instances", "support_crop", "door_cloud", "door_dual_view"),
                              appliance_support_crop_v5=condition in ("support_crop", "door_cloud", "door_dual_view"),
                              microwave_door_cloud_v6=condition in ("door_cloud", "door_dual_view"),
                              dual_view_fusion_v1=condition == "door_dual_view")
        scene.instruction = case["instruction"]
        scene.instance_limits.update(case["instance_limits"])
        scene.refresh(case["names"])
        entities = [entity_record(e) for e in scene.entities.values() if e.visible]
        report["conditions"][condition] = {
            "entities": entities, "microwave_count": sum(e["name"] == "microwave" for e in entities),
            "microwave_door_count": sum(e["name"] == "microwave door" for e in entities),
            "work_surface_measurement": scene.work_surface_measurement,
            "rejected": scene.rejected_fixture_measurements, "evidence": scene.perception_evidence,
            "perception_s": scene.perception_s, "calls": scene.calls,
            "fixture_measurement_evidence": scene.fixture_measurement_evidence,
        }
    selected = "door_dual_view" if args.door_dual_view else "door_cloud" if args.door_cloud_v6 else "support_crop" if args.support_crop_v5 else "recall_instances" if args.instance_geometry_v4 else "recall"
    report["passed"] = report["conditions"][selected]["microwave_count"] == 1
    if args.door_cloud_v6:
        report["passed"] &= report["conditions"][selected]["microwave_door_count"] == 1
    report["instance_limits"] = case["instance_limits"]
    report["selected_condition"] = selected
    (args.output / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"passed": report["passed"], "conditions": {
        key: {k: v for k, v in value.items() if k not in ("entities", "evidence", "rejected", "fixture_measurement_evidence")}
        for key, value in report["conditions"].items()}}))
    if not report["passed"]:
        raise RuntimeError("runtime appliance binding remains missing or ambiguous")


if __name__ == "__main__":
    main()
