"""Selected manual parameters must reach the measured skill execution."""

from pathlib import Path
from types import SimpleNamespace

import numpy as np
import hashlib
import json
import pytest

from robots.libero.v5_runtime import V5Executor
from robots.libero.v5_skill_profiles import attach_legal_memory, load_profiles, parameters_for
from robots.libero.v5_state import Candidate, Entity


def test_general_profile_can_load_without_any_rpent_files(tmp_path):
    package = load_profiles("general", tmp_path)
    assert package["training_allowed"]
    assert parameters_for(package, "bowl")["rim_fraction"] == .7
    assert "rim_grasp_world_y_offset_m" not in parameters_for(package, "bowl")


def test_rpent_rim_and_general_rim_produce_different_measured_staging():
    root = Path(__file__).resolve().parents[4]
    obj = Entity("e1", "bowl", (0, 0, 1), (-.05, -.05, .95), (.05, .05, 1.05))
    scene = SimpleNamespace(entities={"e1": obj}, view_axes=((1, 0, 0), (0, 1, 0)))
    poses = {}
    for kind in ("general", "rpent"):
        executor = V5Executor(SimpleNamespace(primitives=SimpleNamespace()), scene,
                              skill_profiles=load_profiles(kind, root))
        poses[kind] = executor.grasp_approach(obj, Candidate("grasp", "e1", mode="direct"))
    assert np.allclose(poses["general"][0], (.035, 0, 1.11))
    assert np.allclose(poses["rpent"][0], (0, .045, 1.225))
    assert poses["rpent"][1] == "rpent_world_y_rim"


def test_selected_carry_clip_reaches_primitive_and_receipt_keeps_source():
    root = Path(__file__).resolve().parents[4]
    obj = Entity("e1", "wine bottle", (0, 0, 1), (-.03, -.03, .9), (.03, .03, 1.1))
    calls = []
    primitives = SimpleNamespace(_last_obs_eef_pos=np.array([0., 0., 1.]),
                                 env=SimpleNamespace(terminated=False, truncated=False))
    def move(xyz, **kwargs):
        calls.append(kwargs)
        primitives._last_obs_eef_pos = np.array(xyz)
        return {"final_dist_m": 0}
    primitives.move_to = move
    package = load_profiles("rpent", root)
    executor = V5Executor(SimpleNamespace(primitives=primitives),
                          SimpleNamespace(entities={"e1": obj}), skill_profiles=package)
    executor.held = "e1"
    executor.move((.1, 0, 1), 1)
    assert calls == [{"gripper": 1, "step_clip": .012}]
    receipt = executor.execute(Candidate("finish"))
    assert "skill_profile" not in receipt
    assert executor.last_skill_profile_evidence["sha256"] == package["sha256"]
    assert executor.last_skill_profile_evidence["parameters"]["source_lines"]


def test_disabled_profile_keeps_primitive_default_arguments():
    calls = []
    primitives = SimpleNamespace(_last_obs_eef_pos=np.array([0., 0., 1.]),
                                 env=SimpleNamespace(terminated=False, truncated=False))
    primitives.move_to = lambda xyz, **kwargs: calls.append(kwargs) or {"final_dist_m": 0}
    executor = V5Executor(SimpleNamespace(primitives=primitives), SimpleNamespace())
    executor.move((.1, 0, 1), 1)
    assert calls == [{"gripper": 1}]


def test_original_successful_staging_reaches_selected_profile_and_tampering_is_rejected(tmp_path):
    files = {}
    for name, data in {
        "object_skill_cards.json": {"profiles": [{"category": "bowl", "visual_verified": 20,
           "verified_staging_height_median_above_measured_top": .08}]},
        "failure_lessons.json": {"rules": [{"trigger": "grasp verification fails", "response": "remeasure"}]},
    }.items():
        path = tmp_path / name
        path.write_text(json.dumps(data))
        files[name] = {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"origin": "original_oracle", "PRO_inputs_used": False,
                                   "RPent_cards_in_training": False, "files": files}))
    package = attach_legal_memory(None, manifest, tmp_path)
    assert parameters_for(package, "bowl")["approach_height_m"] == .08
    assert parameters_for(package, "unseen bottle")["approach_height_m"] == .06
    assert package["failure_lessons"] and package["legal_memory"]["files"]
    (tmp_path / "object_skill_cards.json").write_text("{}")
    with pytest.raises(ValueError, match="changed"):
        attach_legal_memory(None, manifest, tmp_path)
