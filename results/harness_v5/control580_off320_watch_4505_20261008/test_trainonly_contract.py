"""Missing public evidence stays unknown; private joins follow public encoding."""

from copy import deepcopy
import numpy as np

from scripts import prepare_v5_temporal_control_trainonly_20261008 as prepare
from scripts.train_v5_temporal_control_trainonly_20261008 import fit


def test_private_labels_are_opened_after_public_features_and_do_not_fill_missing_views(monkeypatch):
    robot = {"eef_xyz_m": [0., 0., 1.], "gripper_opening_m": .04}
    chunks = [{"chunk_index": index, "actual_controls": 5, "cumulative_contact_controls": index * 5,
               "source_step": index + 2, "robot_after": robot,
               "public_frame": {"source_step": index + 2, "views": {}, "public_robot_observation": robot}}
              for index in range(1, 321)]
    private = [{"phase": phase, "chunk_index": index, "actual_controls": index * 5,
                "status": "scored", "controller_access": False, "affects_actions_or_stop": False,
                "turn_off_satisfied": True, "joint_qpos": [999.]}
               for phase, count in (("on", 160), ("off", 320)) for index in range(count + 1)]
    episode = {"captures": {"before_off": {"public_measurements": {"key": "measurement"}}}}
    measurement = {"current_stove_shell": {"src": "perception", "lower": [0, 0, 0], "upper": [1, 1, 1]},
                   "source_step": 2, "views": {}, "public_observation": {
                       "robot": {"eef_xyz": robot["eef_xyz_m"], "gripper_opening": .04}}}
    encoded = []

    def encode(*args, **kwargs):
        encoded.append(True)
        return np.zeros(2578, np.float32), [False, False], "fixture_unmeasured_in_both_views"

    def read(ref, **kwargs):
        key = ref["key"]
        if key == "private":
            assert len(encoded) == 320
        return deepcopy({"episode": episode, "measurement": measurement, "public": chunks, "private": private}[key])

    monkeypatch.setattr(prepare, "encode_sequence", encode)
    monkeypatch.setattr(prepare, "read_pinned", read)
    case = {"raw_state_sha256": "original-train-state", "job_id": 4505,
            "episode": {"key": "episode"}, "public_chunks": {"key": "public"},
            "private_chunks": {"key": "private"}}
    arrays, rows, labels, pairs = prepare.build_case(case, "world_xy_grid_v1")
    assert len(arrays) == len(rows) == len(labels) == len(pairs) == 320
    assert all(row["unknown_reason"] == "fixture_unmeasured_in_both_views" for row in rows)
    assert all(label["label"] is None for label in labels)
    assert pairs[0]["private_label_record"]["line_number"] == 163
    assert pairs[-1]["private_label_record"]["line_number"] == 482
    assert all("joint_qpos" not in row for row in rows)


def test_one_measured_class_does_not_create_a_classifier():
    targets = np.asarray([0, 0, -1, -1])
    assert fit(np.ones((4, 8), np.float32), targets, targets >= 0, epochs=300, seed=577) is None
