"""Offline checks for private-score isolation and fixed failed-setup schedule."""

import contextlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

PACKET = Path(__file__).resolve().parent


def load_file(name, filename):
    spec = importlib.util.spec_from_file_location(name, PACKET / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FakeFacade:
    def __init__(self, *args, meta, **kwargs):
        self._stove_chunk_scope = None
        self.returned = {"public_observation": "unchanged"}
        self.controls = 0

    def stove_chunk_start(self, phase, max_chunks):
        self._stove_chunk_scope = {"phase": phase, "chunks_requested": 0, "executed_controls": 0}
        return {"phase": phase, "private_joint_or_predicate_used_for_control": False}

    def chunk_step(self, actions, **kwargs):
        self.controls += len(actions)
        self._stove_chunk_scope["chunks_requested"] += 1
        self._stove_chunk_scope["executed_controls"] += len(actions)
        return self.returned


class Off20ContractTest(unittest.TestCase):
    def test_opposite_truth_does_not_change_controls_or_public_response(self):
        fake_parent = types.ModuleType("robots.libero.v5_stove_probe_env")
        fake_parent.StoveProbeFacade = FakeFacade
        fake_utils = types.ModuleType("scripts.probe_v5_skill501_original")
        fake_utils.diagnostic_json = lambda row: json.dumps(row)
        with patch.dict(sys.modules, {fake_parent.__name__: fake_parent, fake_utils.__name__: fake_utils}):
            module = load_file("off20_fake_score_env", "stove564_probe_env.py")
        traces = []
        with tempfile.TemporaryDirectory() as tmp:
            for truth_value in (False, True):
                path = Path(tmp) / f"labels_{truth_value}.jsonl"
                facade = module.ScoredStoveProbeFacade(meta={"seed": 0}, label_path=path, cell="fake")
                facade.skill_truth = lambda spec: {"joint_names": ["q"], "joint_qpos": [[int(truth_value)]],
                    "satisfied": truth_value, "sim_time": facade.controls * .05}
                self.assertNotIn("joint_qpos", facade.stove_chunk_start("on", 160))
                for _ in range(160):
                    returned = facade.chunk_step([0] * 5)
                    self.assertIs(returned, facade.returned)
                    self.assertEqual(returned, {"public_observation": "unchanged"})
                facade._label_stream.close()
                rows = [json.loads(line) for line in path.read_text().splitlines()]
                self.assertEqual(len(rows), 161)
                self.assertEqual([r["actual_controls"] for r in rows], list(range(0, 801, 5)))
                self.assertTrue(all(r["turn_off_satisfied"] == truth_value for r in rows))
                traces.append((facade.controls, returned))
        self.assertEqual(traces[0], traces[1])

    def test_score_error_keeps_controls_and_public_return_and_error_ledger(self):
        fake_parent = types.ModuleType("robots.libero.v5_stove_probe_env")
        fake_parent.StoveProbeFacade = FakeFacade
        fake_utils = types.ModuleType("scripts.probe_v5_skill501_original")
        fake_utils.diagnostic_json = lambda row: json.dumps(row)
        with patch.dict(sys.modules, {fake_parent.__name__: fake_parent, fake_utils.__name__: fake_utils}):
            module = load_file("off20_fake_error_env", "stove564_probe_env.py")
        with tempfile.TemporaryDirectory() as tmp:
            facade = module.ScoredStoveProbeFacade(meta={"seed": 0}, label_path=Path(tmp) / "labels.jsonl", cell="fake")
            facade._stove_chunk_scope = {"phase": "on", "chunks_requested": 0, "executed_controls": 0}
            facade.skill_truth = lambda spec: (_ for _ in ()).throw(RuntimeError("score transport failed"))
            returned = facade.chunk_step([0] * 5)
            self.assertIs(returned, facade.returned)
            self.assertEqual(facade.controls, 5)
            facade._label_stream.close()
            row = json.loads(facade._label_path.read_text())
            self.assertEqual(row["status"], "private_scoring_error")
            self.assertEqual(row["actual_controls"], 5)

    def test_failed_on_setup_still_runs_same_fixed_off(self):
        runner = load_file("off20_fake_runner", "probe_off20.py")
        inherited = types.ModuleType("scripts.probe_v5_stove521_endpoint")
        commands, captures = [], []
        inherited.capture_measurements = lambda *a, **kw: captures.append(str(a[-1])) or {"public": "fake"}
        def fixed(executor, rpc, **kw):
            commands.append(kw)
            return {"fixed_prefix_completed": kw["phase"] != "on", "status": "fake"}
        inherited.fixed_contact = fixed
        inherited.prepare_off_approach = lambda *a: {"executed": False, "reason": "unmeasured"}
        env = types.SimpleNamespace(complete_skill=contextlib.nullcontext, _native_terminated=False, truncated=False)
        primitive = types.SimpleNamespace(env=env, release=lambda: {"executed": True})
        executor = types.SimpleNamespace(p=primitive, motion_evidence=[], retreat=lambda: None)
        case = {"method": "measured_complete_knob_off", "on_prompt": "turn on the stove",
                "off_prompt": "turn the stove knob all the way to the off position", "public_contact_refinement": True}
        scripts = types.ModuleType("scripts")
        scripts.probe_v5_stove521_endpoint = inherited
        with patch.dict(sys.modules, {"scripts": scripts, inherited.__name__: inherited}):
            row = runner.run_phases(executor, None, None, case, {}, Path("/fake"))
        self.assertEqual([(c["phase"], c["chunks"]) for c in commands], [("on", 160), ("off", 160)])
        self.assertEqual(commands[1]["prompt"], case["off_prompt"])
        self.assertFalse(row["on_setup"]["fixed_prefix_completed"])
        self.assertEqual(len(captures), 5)


if __name__ == "__main__":
    unittest.main(verbosity=2)
