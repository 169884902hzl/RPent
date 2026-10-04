"""An existing image alone cannot establish decision-time synchronization."""

import pytest

from scripts.package_v6_libero_images import match_frame
from scripts.diagnose_v5_preaction_success import auc, outcome


def fixture():
    event = {"measurements": [{"source_step": 8}], "post_measurements": [{"source_step": 19}],
             "robot_measurement": {"eef_xyz": [0, 0, 1], "gripper_opening": .08},
             "post_robot_measurement": {"eef_xyz": [0, 0, 1.1], "gripper_opening": .02}}
    steps = {8: {"step_idx": 8, "state": {"robot0_eef_pos": [0, 0, 1.00000001], "robot0_gripper_qpos": [.04, -.04]}},
             19: {"step_idx": 19, "state": {"robot0_eef_pos": [0, 0, 1.1], "robot0_gripper_qpos": [.01, -.01]}}}
    return event, steps


def test_auxiliary_post_frame_is_not_action_pre_frame():
    event, steps = fixture()
    assert match_frame(event, steps, post=False)[0]["step_idx"] == 8
    assert match_frame(event, steps, post=True)[0]["step_idx"] == 19


def test_disagreeing_robot_pose_refuses_frame_even_if_it_exists():
    event, steps = fixture()
    steps[8]["state"]["robot0_eef_pos"][0] = .02
    with pytest.raises(ValueError, match="robot/frame mismatch"):
        match_frame(event, steps, post=False)


def test_explicit_capture_precedes_legacy_entity_source_heuristic():
    event, steps = fixture()
    event["decision_frame_step"] = 3
    with pytest.raises(ValueError, match="registered frame"):
        match_frame(event, steps, post=False)


def test_selection_confidence_cannot_override_physical_failure_label():
    event = {"answer": {"probabilities": {"C0": .99}},
             "receipt": {"tool": "grasp", "grasp_verified": False}}
    assert outcome(event) == (0, "grasp_verified")
    assert outcome({"receipt": {"tool": "articulate", "verification": "unverified"}})[0] is None


def test_auc_ties_and_class_absence():
    assert auc([0, 1], [.1, .9]) == 1
    assert auc([0, 1], [.5, .5]) == .5
    assert auc([1], [.9]) is None


def test_future_capture_syncs_robot_sensors_without_rewriting_the_old_cache():
    from types import SimpleNamespace

    import numpy as np

    from robots.libero.tools import LiberoPrimitives
    from robots.libero.v5_runtime import V5Executor

    image = np.zeros((2, 2, 3), dtype=np.uint8)
    old = {"states": np.array([.1, .2, .3, .4, .5, .6, .01, -.01]), "image": image}
    p = SimpleNamespace(env=SimpleNamespace(last_obs=old), _last_obs=old)
    p.set_obs = lambda obs: LiberoPrimitives.set_obs(p, obs)
    p.set_obs(old)
    measured = {"robot0_eef_pos": [.101, .202, .303],
                "robot0_gripper_qpos": [.03, -.03]}
    capture_calls = []
    toolkit = SimpleNamespace(primitives=p,
        get_env_state=lambda **kw: capture_calls.append(kw),
        _state=SimpleNamespace(latest_record=lambda: SimpleNamespace(state=measured)))
    executor = V5Executor(toolkit, SimpleNamespace())
    executor.capture(sync_robot=True)
    assert len(capture_calls) == 1
    np.testing.assert_allclose(p._last_obs_eef_pos, measured["robot0_eef_pos"])
    assert p._last_obs_gripper == pytest.approx(.06)
    np.testing.assert_array_equal(p._last_obs["states"][3:6], old["states"][3:6])
    np.testing.assert_array_equal(old["states"], [.1, .2, .3, .4, .5, .6, .01, -.01])
    assert p._last_obs["image"] is image and p.env.last_obs is p._last_obs
    frame = {"step_idx": 7, "state": measured}
    event = {"decision_frame_step": 7, "measurements": [],
             "robot_measurement": {"eef_xyz": p._last_obs_eef_pos.tolist(),
                                   "gripper_opening": p._last_obs_gripper}}
    assert match_frame(event, {7: frame}, post=False)[0] is frame


@pytest.mark.parametrize("negative_is_acceptable", [False, True])
def test_image_packager_keeps_tested_finish_negatives_in_their_own_bucket(
    tmp_path, monkeypatch, negative_is_acceptable
):
    import copy
    import json
    import sys

    from scripts import package_v6_libero_images as package

    episode = tmp_path / "episode"
    episode.mkdir()
    event, steps = fixture()
    event.update(decision=0, request={"context": "state before"},
                 post_request={"context": "state after"})
    for frame in steps.values():
        frame["artifacts"] = []
    (episode / "states.json").write_text(json.dumps({"steps": list(steps.values())}))
    (episode / "choices.jsonl").write_text(json.dumps(event) + "\n")
    row = {"schema_version": "entities-plan-receipt/3.1", "init_state_index": 10,
           "scene_id": "original/test", "step": 0,
           "request": {"state": "state before", "questions": {"action": {
               "criteria": {"C0": "finish()", "C1": "grasp(e1,direct)"}}}},
           "evaluated_actions": ["C0", "C1"], "acceptable_actions": ["C1"]}
    wrapper = {"source_request_sha256": "recorded_request", "finish_code": "C0",
               "row": copy.deepcopy(row)}
    if negative_is_acceptable:
        wrapper["row"]["acceptable_actions"].append("C0")
    files = []
    for name, item in (("train", row), ("premature_finish_negative", wrapper)):
        path = episode / f"{name}.jsonl"
        path.write_text(json.dumps(item) + "\n")
        files.append({"bucket": name, "path": str(path), "sha256": package.sha(path),
                      "admitted": True})
    index = tmp_path / "index.json"
    index.write_text(json.dumps({"training": {"files": files}}))
    out = tmp_path / "images"
    monkeypatch.setattr(sys, "argv", ["package", "--index", str(index),
                                      "--index-sha256", package.sha(index), "--output", str(out)])
    monkeypatch.setattr(package, "render_pair", lambda *a, **kw: {
        "views": [{"view": "agentview"}, {"view": "wrist"}]})
    package.main()
    kept = [json.loads(x) for x in (out / "train.jsonl").read_text().splitlines()]
    negatives = [json.loads(x) for x in (out / "premature_finish_negative.jsonl").read_text().splitlines()]
    assert len(kept) == 1 and kept[0]["acceptable_actions"] == ["C1"]
    assert len(negatives) == int(not negative_is_acceptable)
    if negatives:
        assert negatives[0]["finish_code"] == wrapper["finish_code"]
        assert negatives[0]["source_request_sha256"] == wrapper["source_request_sha256"]
        attached = negatives[0]["row"]
        for field in row:
            assert attached[field] == row[field]
        assert [v["view"] for v in attached["media_pair"]["views"]] == ["agentview", "wrist"]
    report = json.loads((out / "manifest.json").read_text())
    assert report["premature_finish_negative"]["rows"] == len(negatives)
    assert report["train"]["rows"] == 1
    if negative_is_acceptable:
        assert report["counts"]["finish probe is not an explicit tested negative"] == 1
