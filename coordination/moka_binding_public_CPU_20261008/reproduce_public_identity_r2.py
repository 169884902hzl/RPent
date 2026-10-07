"""Reproduce the opt-in scene-owner path with pinned saved public inputs."""

import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np

from diagnose_public_binding import BASE, INPUTS, checked, sha
from robots.libero.v5_runtime import MeasuredScene
from robots.libero.v5_state import Entity, entity_record


def main() -> None:
    cases = []
    for seed, filename, expected, remote in INPUTS:
        path, reference = checked(filename, expected, remote)
        row = next(json.loads(line) for line in path.read_text().splitlines() if line and json.loads(line)["case"]["layout_seed"] == seed)
        choice_path, choice_ref = checked(f"choices{seed}.jsonl", row["choices_sha256"], row["output_dir"] + "/choices.jsonl")
        choice = json.loads(choice_path.read_text())
        scene = MeasuredScene.__new__(MeasuredScene)
        scene.toolkit = SimpleNamespace(_state=SimpleNamespace(latest_step=choice["decision_frame_step"]))
        scene.entities = {item["id"]: Entity(**{key: value for key, value in item.items() if key in Entity.__dataclass_fields__})
                          for item in choice["measurements"]}
        before = dict(scene.entities)
        scene.measurement_clouds_by_view = {}
        for eid, ref in choice["fixture_measurement_evidence"].items():
            cloud_path, _ = checked(f"cloud_{seed}_{eid}.npz", ref["sha256"], ref["path"])
            points = np.load(cloud_path, allow_pickle=False)["array"]
            scene.measurement_clouds_by_view[eid] = {ref["camera"]: {
                "xyz_world": points, "source_step": ref["source_step"], "src": "perception"}}
        scene.stove_identity_history = []
        # All IDs here come from the same saved choices capture. SAM masks
        # were not persisted; None prevents inventing a mask-based proof.
        scene.canonicalize_stove_measurements({eid: None for eid in scene.measurement_clouds_by_view}, "agentview")
        guards = scene.stove_operating_area(choice["robot_measurement"]["eef_xyz"])
        selected = [eid for eid, guard in guards.items() if guard["disposition"] == "eligible"]
        if len(selected) != 1 or any(guard["disposition"] == "unmeasured" for guard in guards.values()):
            raise ValueError("new public binding is still ambiguous or lacks current evidence")
        if not all(scene.entities[eid] is before[eid] for eid in scene.entities):
            raise ValueError("scene cleanup retargeted an ID or altered measured geometry")
        cases.append({"layout_seed": seed, "episodes": reference, "choices": choice_ref,
                      "old_binding_outcome": row["public_stove_binding_evidence"]["outcome"],
                      "original_old_result_unchanged": True,
                      "scene_identity_evidence": scene.stove_identity_history[-1],
                      "point_operating_area_evidence": guards, "new_binding_outcome": "unique",
                      "new_eligible_ids": selected, "selected_existing_public_entity": entity_record(scene.entities[selected[0]]),
                      "existing_entity_objects_and_measurements_preserved": True,
                      "original_sam_masks_persisted": False, "physical_action_executed": False})
    root = Path(__file__).resolve().parents[2]
    source_files = ["robots/libero/v5_runtime.py", "robots/libero/v5_public_fixture_identity.py",
                    "harness_v5_eval.py", "scripts/probe_v5_moka_transfer_public_20261007.py"]
    result = {"schema": "moka-public-identity-runtime-owner-reproduction/2-CPU-dev",
              "cases": cases, "source_files": [{"path": str(root / file), "sha256": sha(root / file)} for file in source_files],
              "new_unique_bindings": len(cases), "runtime_switch_global_default": False,
              "new_state_fields": 0, "new_geometry_created": False,
              "private_geometry_or_goal_used": False, "gpu_submissions": 0, "physical_reruns": 0,
              "qualification_authorized": False,
              "analyzer": {"path": str(Path(__file__).resolve()), "sha256": sha(Path(__file__))}}
    output = BASE / "public_identity_runtime_reproduction_r2.json"
    encoded = json.dumps(result, indent=2) + "\n"
    if output.exists() and output.read_text() != encoded:
        raise ValueError("immutable reproduction already differs")
    output.write_text(encoded)
    print(json.dumps({"path": str(output), "sha256": sha(output), "new_unique_bindings": len(cases),
                      "ids": [case["new_eligible_ids"] for case in cases]}))


if __name__ == "__main__":
    main()
