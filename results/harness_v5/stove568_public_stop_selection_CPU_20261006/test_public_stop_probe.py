"""Offline public-stop and split-recovery schedule regressions."""

import contextlib
import importlib.util
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

PACKET = Path(__file__).resolve().parent


def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, PACKET / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class PublicStopTest(unittest.TestCase):
    def test_unmeasured_off_never_stops_even_when_red_is_zero(self):
        observer = load("stove568_test_observer", "public_red_observer.py")
        calibration = {"endpoint_stop_admitted": False, "red_fraction_threshold": None}
        result = observer.stop_decision({"agentview": {"surface_pixels": 20000, "red_fraction": 0}}, calibration)
        self.assertFalse(result["stop"])
        self.assertEqual(result["reason"], "public_off_endpoint_unmeasured")

    def test_opposite_private_labels_do_not_affect_public_stop(self):
        observer = load("stove568_test_observer_isolation", "public_red_observer.py")
        calibration = {"endpoint_stop_admitted": False, "red_fraction_threshold": None}
        decisions = []
        for value in (True, False):
            decisions.append(observer.stop_decision({"agentview": {"surface_pixels": 20000,
                "red_fraction": 0, "turn_off_satisfied": value, "joint_qpos": -1 if value else 2}}, calibration))
        self.assertEqual(decisions[0], decisions[1])

    def test_failed_setup_fixed_off_and_separate_release_retreat_captures(self):
        runner = load("stove568_test_runner", "probe_public_red_recovery.py")
        order = []
        inherited = types.ModuleType("scripts.probe_v5_stove521_endpoint")
        def capture(*args, **kwargs):
            order.append("capture:" + args[-1].name)
            return {"public": "fake"}
        inherited.capture_measurements = capture
        inherited.fixed_contact = lambda *a, **kw: {"fixed_prefix_completed": False}
        utils = types.ModuleType("scripts.probe_v5_skill501_original")
        import json
        utils.diagnostic_json = json.dumps
        utils.executed_actions = lambda motions: 5 * len(motions)
        observer = types.ModuleType("public_red_observer")
        observer.observe = lambda *a: {"stop_decision": {"stop": False}, "public_only": True}
        scripts = types.ModuleType("scripts")
        scripts.probe_v5_stove521_endpoint = inherited
        rpc = types.SimpleNamespace(call=lambda *a, **kw: {"executed_controls": 800})
        primitive = types.SimpleNamespace(env=types.SimpleNamespace(complete_skill=contextlib.nullcontext,
            _native_terminated=False, truncated=False), release=lambda: order.append("release") or {})
        class Executor:
            def __init__(self):
                self.p = primitive
                self.toolkit = types.SimpleNamespace(_state=types.SimpleNamespace(latest_step=0))
                self.scene = types.SimpleNamespace(entities={})
                self.motion_evidence = []
            def vla_act(self, prompt, chunks, stop):
                order.append("off:" + prompt)
                self.motion_evidence.append({"executed_controls": 5})
                return {"chunks": 1}
            def retreat(self):
                order.append("retreat")
        with tempfile.TemporaryDirectory() as tmp:
            with patch.dict(sys.modules, {"scripts": scripts, inherited.__name__: inherited,
                    utils.__name__: utils, observer.__name__: observer}):
                result = runner.run_phases(Executor(), None, rpc, {}, {"public_calibration": {}}, Path(tmp))
        self.assertEqual(sum(item.startswith("off:") for item in order), 160)
        self.assertEqual(order[-5:], ["capture:after_contact", "release", "capture:after_release", "retreat", "capture:after_retreat"])
        self.assertFalse(result["on_setup"]["fixed_prefix_completed"])
        self.assertEqual(result["off_contact"]["chunks"], 160)
        self.assertEqual(result["off_contact"]["executed_control_actions"], 800)


if __name__ == "__main__":
    unittest.main(verbosity=2)
