"""Public-only inference and fixed-schedule sampling regression checks."""

import json
from pathlib import Path
import tempfile
import types
import unittest

import numpy as np

from public_temporal_verifier import frame_features, infer, sequence_features
from sample_public_sequence import capture_public_sequence


class TemporalContractTest(unittest.TestCase):
    def test_private_label_keys_do_not_change_public_feature_or_unknown(self):
        bounds = {"lower": [0, 0, 0], "upper": [1, 1, 1]}
        for value in (True, False):
            features, available = frame_features({"views": {}, "private_joint": value}, bounds)
            np.testing.assert_array_equal(features, np.zeros(640))
            self.assertEqual(available, [False, False])
            self.assertEqual(infer(features, available, "not-opened.npz")["status"], "unknown")

    def test_public_sampler_fixed_hold_schedule(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            controls = []
            class State:
                latest_step = 0
                def artifact_path(self, name, step):
                    path = root / f"{step}_{name}"
                    path.write_bytes(b"public-only-test-frame")
                    return path
            state = State()
            primitive = types.SimpleNamespace(_step_env=lambda action: controls.append(action.tolist()),
                _last_obs_eef_pos=np.asarray([1., 2., 3.]), _last_obs_gripper=.08)
            executor = types.SimpleNamespace(p=primitive, toolkit=types.SimpleNamespace(_state=state),
                capture=lambda: setattr(state, "latest_step", state.latest_step + 1))
            ref = capture_public_sequence(executor, None, root / "sequence", phase="after_retreat", gripper_control=-1)
            packet = json.loads(Path(ref["path"]).read_text())
            self.assertEqual(len(controls), 12)
            self.assertTrue(all(x == [0, 0, 0, 0, 0, 0, -1] for x in controls))
            self.assertEqual(len(packet["frames"]), 3)
            self.assertEqual(packet["status"], "unknown")
            self.assertFalse(packet["stop_based_on_private_label"])

    def test_inference_cpu_checkpoint_parity(self):
        packet = Path(__file__).resolve().parent
        dataset, checkpoint = packet / "dataset", packet / "cpu_baseline" / "temporal_mlp32.npz"
        if not checkpoint.exists():
            self.skipTest("CPU baseline checkpoint only present in execution packet")
        with np.load(dataset / "public_features.npz") as z:
            features = z["features"]
        predictions = [json.loads(x) for x in (packet / "cpu_baseline" / "predictions.jsonl").read_text().splitlines()]
        for index in (0, 100, 480, 799):
            result = infer(features[index], [True, True], checkpoint)
            self.assertLess(abs(result["p_satisfied"] - predictions[index]["p_satisfied"]), 1e-6)
            self.assertFalse(result["stop_admitted"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
