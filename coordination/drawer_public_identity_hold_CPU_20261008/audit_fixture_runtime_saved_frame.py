"""Exercise the actual scene-owned cleanup on one SHA-checked public frame."""

import argparse
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np

from robots.libero.v5_oracle_policy import OriginalOraclePolicy
from robots.libero.v5_runtime import MeasuredScene
from robots.libero.v5_state import Candidate, Entity
from robots.libero.v5_subtasks import subtask_prompt


def checked(ref):
    path = Path(ref["path"])
    if hashlib.sha256(path.read_bytes()).hexdigest() != ref["sha256"]:
        raise ValueError(f"public file changed: {path}")
    return path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--public-index", type=Path, required=True)
    parser.add_argument("--public-index-sha", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    index = {"path": str(args.public_index), "sha256": args.public_index_sha}
    refs = [json.loads(line) for line in checked(index).read_text().splitlines() if line]
    frame_ref = refs[-1]
    frame = json.loads(checked(frame_ref).read_text())
    scene = MeasuredScene.__new__(MeasuredScene)
    scene.toolkit = SimpleNamespace(_state=SimpleNamespace(latest_step=frame["source_step"]))
    scene.entities = {eid: Entity(**{key: value for key, value in item["current"].items()
                                   if key in Entity.__dataclass_fields__}) for eid, item in frame["entities"].items()}
    scene.perception_evidence = {eid: item["perception_evidence"] for eid, item in frame["entities"].items()}
    scene.fixture_alias_history = []
    masks, mask_refs = {}, {}
    for eid in ("e107", "e47"):
        ref = frame["entities"][eid]["perception_evidence"]["sam_mask_files"]["agentview"]
        with np.load(checked(ref)) as archive:
            masks[eid] = archive["array"].astype(bool)
        mask_refs[eid] = ref
    policy = OriginalOraclePolicy(None)
    def bind():
        value = policy.bind("white_cabinet_1_top_side", list(scene.entities.values()),
                            "put the bowl on top of the cabinet", ((1., 0., 0.), (0., -1., 0.)), source_reference=False)
        return value.id if value else None
    before = bind()
    original = dict(scene.entities)
    scene.canonicalize_fixture_fragments(masks, "agentview")
    after = bind()
    if before is not None or after != "e104":
        raise ValueError("actual runtime scene cleanup did not reproduce the registered binding fix")
    result = {
        "schema": "fixture-fragment-runtime-saved-public-reproduction/1",
        "source_index": index, "source_frame": frame_ref, "source_masks": mask_refs,
        "before_target_binding": before, "after_target_binding": after,
        "candidate_prompt": subtask_prompt(Candidate("vla_subtask", "e15", "e104", "on"), scene.entities),
        "runtime_method": "MeasuredScene.canonicalize_fixture_fragments",
        "evidence": scene.fixture_alias_history[-1],
        "retained_entity_values_unchanged": all(scene.entities[eid] is original[eid] for eid in scene.entities),
        "state_fields_added": False, "private_truth_used": False,
        "new_physical_trials": 0, "qualification_authorized": False,
        "physical_runtime_path_validation_pending": True,
    }
    encoded = json.dumps(result, indent=2) + "\n"
    if args.output.exists() and args.output.read_text() != encoded:
        raise ValueError("immutable CPU reproduction already differs")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(encoded)
    print(json.dumps({"report": str(args.output), "sha256": hashlib.sha256(args.output.read_bytes()).hexdigest(),
                      "before_target_binding": before, "after_target_binding": after,
                      "removed_ids": result["evidence"]["removed_ids"]}))


if __name__ == "__main__":
    main()
