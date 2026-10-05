# Copyright 2026 Zhilun Hu.
# SPDX-License-Identifier: Apache-2.0
"""Noise and branch-restoration regressions, offline with real CPU Torch RNG."""

import copy
import json
import threading
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
import torch

from robots.libero import v5_seeded_vla_server as server
from robots.libero.v5_state import Candidate, Entity, serialize
from scripts import probe_v5_multiseed509_original as probe


@pytest.fixture
def seeded(monkeypatch):
    facade = object.__new__(server.SeededPi05VLAFacade)
    facade._noise_lock = threading.Lock()
    monkeypatch.setattr(torch.cuda, "is_available", lambda: False)
    monkeypatch.setattr(server.Pi05VLAFacade, "predict", lambda *_: torch.randn(1, 5, 7).numpy())
    return facade


def test_real_noise_seed_repeat_difference_and_rng_preservation(seeded):
    before = torch.get_rng_state().clone()
    one = seeded.predict({}, {"mode": "eval", "seed": 51})
    repeat = seeded.predict({}, {"mode": "eval", "seed": 51})
    other = seeded.predict({}, {"mode": "eval", "seed": 52})
    np.testing.assert_array_equal(one, repeat)
    assert not np.array_equal(one, other)
    assert torch.equal(before, torch.get_rng_state())


def test_rng_restored_after_predict_exception(seeded, monkeypatch):
    before = torch.get_rng_state().clone()
    def fail(*_):
        torch.randn(20)
        raise RuntimeError("policy failed")
    monkeypatch.setattr(server.Pi05VLAFacade, "predict", fail)
    with pytest.raises(RuntimeError, match="policy failed"):
        seeded.predict({}, {"seed": 12})
    assert torch.equal(before, torch.get_rng_state())


@pytest.mark.parametrize("value", [None, True, False, 1.5, "4", -1, 2**63])
def test_seed_requires_explicit_valid_integer(seeded, value):
    with pytest.raises(ValueError, match="explicit integer"):
        seeded.predict({}, {"mode": "eval", "seed": value})


@pytest.mark.parametrize("options", [{"seed": 10, "mode": "train"}, {"seed": 10, "other": 1}])
def test_seeded_service_rejects_changed_policy_mode(seeded, options):
    with pytest.raises(ValueError, match="only mode=eval"):
        seeded.predict({}, options)


def make_plan(tmp_path):
    root = Path(probe.__file__).resolve().parents[1]
    names = ("robots/libero/v5_state.py", "robots/libero/v5_runtime.py",
             "robots/libero/v5_collection.py", "robots/libero/v5_seeded_vla_server.py",
             "scripts/probe_v5_multiseed509_original.py")
    source = {name: {"path": str(root/name), "sha256": probe.file_sha(root/name)} for name in names}
    freeze_path = tmp_path / "freeze.json"
    freeze_path.write_text(json.dumps({"status": "frozen", "commit": "test-only",
                                     "source_sha256": {key: entry["sha256"] for key, entry in source.items()}}))
    return {"schema": probe.MANIFEST_SCHEMA,
            "freeze": {"path": str(freeze_path), "sha256": probe.file_sha(freeze_path)},
            "source_files": source, "max_noise_calls": 40,
            "policy_noise_base_seeds": [100, 1100, 2100, 3100],
            "episodes": [{"suite": "libero_spatial", "task": 0, "seed": 10}],
            "seeded_service_identity": {"seed_contract": probe.SEED_CONTRACT, "embodiment": "libero",
                "server_sha256": source["robots/libero/v5_seeded_vla_server.py"]["sha256"]}}


def test_manifest_admits_explicit_original_train_split(tmp_path):
    assert probe.validate_plan(make_plan(tmp_path))["commit"] == "test-only"


@pytest.mark.parametrize("field,value", [("suite", "libero_spatial_swap"), ("suite", "libero_90"),
                                         ("seed", 0), ("seed", 40), ("seed", 41), ("task", 10)])
def test_manifest_excludes_pro_development_final_and_original90(tmp_path, field, value):
    plan = make_plan(tmp_path)
    plan["episodes"][0][field] = value
    with pytest.raises(ValueError, match="original40"):
        probe.validate_plan(plan)


def test_manifest_rejects_unfrozen_or_changed_source(tmp_path):
    plan = make_plan(tmp_path)
    path = Path(plan["freeze"]["path"])
    original = json.loads(path.read_text())
    path.write_text(json.dumps({**original, "status": "development"}))
    plan["freeze"]["sha256"] = probe.file_sha(path)
    with pytest.raises(ValueError, match="frozen runtime"):
        probe.validate_plan(plan)
    path.write_text(json.dumps(original))
    plan["freeze"]["sha256"] = probe.file_sha(path)
    plan["source_files"]["robots/libero/v5_runtime.py"]["sha256"] = "0"*64
    with pytest.raises(ValueError, match="registered freeze"):
        probe.validate_plan(plan)


def test_manifest_rejects_overlapping_noise_sequences(tmp_path):
    plan = make_plan(tmp_path)
    plan["policy_noise_base_seeds"] = [100, 120, 200, 300]
    with pytest.raises(ValueError, match="not overlap"):
        probe.validate_plan(plan)


class FakeModel:
    def __init__(self, identity):
        self.identity, self.calls = identity, []
        self._client = SimpleNamespace(call=lambda *_a, **_k: copy.deepcopy(identity))
    def predict(self, obs, options):
        self.calls.append(copy.deepcopy(options))
        return np.full((5, 7), options["seed"], dtype=np.float32)


def test_client_passes_seed_per_chunk_and_hashes_actual_actions():
    identity = {"seed_contract": probe.SEED_CONTRACT}
    model = FakeModel(identity)
    client = probe.SeededBranchClient(model, 44, 2, identity)
    one = client.predict({}, {"mode": "eval"})
    two = client.predict({}, {"mode": "eval"})
    assert model.calls == [{"mode": "eval", "seed": 44}, {"mode": "eval", "seed": 45}]
    assert client.calls[0]["action_sha256"] != client.calls[1]["action_sha256"]
    assert len(one) == len(two) == 5
    with pytest.raises(RuntimeError, match="budget exhausted"):
        client.predict({}, {"mode": "eval"})


def test_client_refuses_unowned_server():
    with pytest.raises(ValueError, match="dedicated"):
        probe.SeededBranchClient(FakeModel({"seed_contract": "unseeded"}), 100, 5,
                                 {"seed_contract": probe.SEED_CONTRACT})


def test_failed_prediction_retains_seed_and_next_request_advances(monkeypatch):
    identity = {"seed_contract": probe.SEED_CONTRACT}
    model = FakeModel(identity)
    client = probe.SeededBranchClient(model, 100, 3, identity)
    good = model.predict
    monkeypatch.setattr(model, "predict", lambda *_a, **_k: np.full((5, 7), np.nan))
    with pytest.raises(ValueError, match="invalid LIBERO"):
        client.predict({}, {"mode": "eval"})
    assert client.calls[0]["policy_noise_seed"] == 100
    assert client.calls[0]["status"] == "instrument_error"
    monkeypatch.setattr(model, "predict", good)
    client.predict({}, {"mode": "eval"})
    assert client.calls[1]["policy_noise_seed"] == 101


def runtime(plan, *, error=False, execute=True, truth=True):
    scene = SimpleNamespace(**{name: {} for name in probe.SCENE_FIELDS})
    entity = Entity("e1", "bowl", (0, 0, .9), (-.03, -.03, .88), (.03, .03, .92))
    scene.entities = {"e1": entity}
    scene.vocabulary = {"bowl"}
    scene.view_axes = ((1, 0, 0), (0, -1, 0))
    choices = [Candidate("grasp", "e1", mode="direct"), Candidate("finish")]
    args = SimpleNamespace(suite="libero_spatial", task=0, seed=10,
                           instruction_override="pick up the bowl", candidate_failure_counts_v1=False)
    env = SimpleNamespace(terminated=False, truncated=False, last_obs={})
    model = FakeModel(plan["seeded_service_identity"])
    p = SimpleNamespace(env=env, model=model, _last_obs={}, _last_obs_gripper=.08)
    def set_obs(obs):
        p._last_obs = obs
        p._last_obs_gripper = obs.get("opening", .08)
    p.set_obs = set_obs
    executor = SimpleNamespace(**{name: {} for name in probe.EXECUTOR_FIELDS})
    executor.p, executor.held, executor.receipts, executor.motion_evidence = p, None, [], []
    executor.public_recovery = None
    toolkit = SimpleNamespace(_solved=False)
    toolkit.solved = lambda: toolkit._solved
    observations = []
    def physical_action(action, card=None):
        observations.append(copy.deepcopy(executor.receipts))
        executor.motion_evidence = []
        if execute:
            p.model.predict({}, {"mode": "eval"})
            executor.motion_evidence = [{"executed_action_count": 5}]
        executor.receipts = [{"tool": "grasp", "grasp_verified": not truth}]
        executor.held = "e1"
        scene.entities["e1"] = Entity("e1", "bowl", (.2, 0, 1.), (.17, -.03, .98), (.23, .03, 1.02))
        return {"tool": "grasp", "executed": execute, "grasp_verified": not truth,
                **({"error": "model transport failed"} if error else {})}
    executor.execute = physical_action
    class RPC:
        def __init__(self):
            self.restores = 0
        def call(self, method, **kwargs):
            if method == "oracle.status":
                return {"done": False, "goals": [["on", "bowl_1", "plate_1"]], "satisfied": [False]}
            if method == "oracle.snapshot":
                return {"sim_state": np.asarray([0., 1.])}
            if method == "oracle.restore":
                self.restores += 1
                return {"raw_observation": "not a restored flag"}
            if method == "oracle.grasp_reference":
                return {"original_support": 0.9}
            if method == "oracle.measure_grasp_hold":
                return {"truth": {"success": truth}, "diagnostic_actions": 25}
            raise AssertionError(method)
    rpc = RPC()
    context = serialize(args.instruction_override, [entity], .08, None, [],
                        view_axes=scene.view_axes, choices=choices, card=None,
                        failure_counts=False, recovery_status=None)
    request = {"instruction": args.instruction_override, "context": context,
               "options": [choice.text() for choice in choices]}
    return {"args": args, "request": request, "choices": choices, "selected_indices": [0],
            "scene": scene, "executor": executor, "toolkit": toolkit, "rpc": rpc,
            "required_objects": {"e1"}, "original_object_names": {"e1": "bowl_1"}}, observations


def test_four_seeds_restore_same_public_bytes_and_private_truth_only_labels(tmp_path):
    plan = make_plan(tmp_path)
    kwargs, observations = runtime(plan)
    before_request = copy.deepcopy(kwargs["request"])
    original_model = kwargs["executor"].p.model
    result = probe.collect_four_seed_branches(plan=plan, **kwargs)
    assert kwargs["executor"].p.model is original_model
    assert kwargs["executor"].held is None and kwargs["executor"].receipts == []
    assert observations == [[], [], [], []]
    assert result["request"] == kwargs["request"] == before_request
    assert result["candidate_statistics"]["C0"]["successes"] == 4
    assert result["unknown_actions"] == ["C1"]
    assert [row["policy_noise_calls"][0]["policy_noise_seed"] for row in result["branches"]] == plan["policy_noise_base_seeds"]
    assert all(row["receipt"]["grasp_verified"] is False and row["accepted"] is True for row in result["branches"])
    assert all(row["diagnostic_steps"] == 25 and row["executed_steps"] == 5 for row in result["branches"])
    assert kwargs["rpc"].restores == 8
    assert result["new_training_rows"] == 0


@pytest.mark.parametrize("error,execute,reason", [(True, True, "execution_or_instrument_error"),
                                               (False, False, "no_physical_execution_evidence")])
def test_errors_and_unexecuted_branches_are_unknown(tmp_path, error, execute, reason):
    plan = make_plan(tmp_path)
    kwargs, _ = runtime(plan, error=error, execute=execute)
    result = probe.collect_four_seed_branches(plan=plan, **kwargs)
    assert all(row["accepted"] is None and row["unknown_reason"] == reason for row in result["branches"])
    stats = result["candidate_statistics"]["C0"]
    assert stats["unknown_trials"] == 4 and stats["known_trials"] == 0
    assert stats["acceptable_branch_rate"] is None and stats["wilson_95"] is None


def test_true_executed_failure_is_a_negative(tmp_path):
    plan = make_plan(tmp_path)
    kwargs, _ = runtime(plan, truth=False)
    result = probe.collect_four_seed_branches(plan=plan, **kwargs)
    assert all(row["accepted"] is False for row in result["branches"])
    assert result["candidate_statistics"]["C0"]["acceptable_branch_rate"] == 0


def test_instrument_exception_restores_model_and_public_state(tmp_path):
    plan = make_plan(tmp_path)
    kwargs, _ = runtime(plan)
    executor = kwargs["executor"]
    model = executor.p.model
    original_execute = executor.execute
    def fail_after_movement(action, card=None):
        original_execute(action, card=card)
        raise RuntimeError("diagnostic transport lost")
    executor.execute = fail_after_movement
    result = probe.collect_four_seed_branches(plan=plan, **kwargs)
    assert executor.p.model is model and executor.receipts == [] and executor.held is None
    assert all(row["accepted"] is None and row["unknown_reason"] == "instrument_error"
               and row["executed_steps"] == 5 for row in result["branches"])


def test_native_terminal_state_never_executes_physical_branch(tmp_path):
    plan = make_plan(tmp_path)
    kwargs, observations = runtime(plan)
    kwargs["toolkit"]._solved = True
    result = probe.collect_four_seed_branches(plan=plan, **kwargs)
    assert observations == []
    assert all(row["accepted"] is None and row["unknown_reason"] == "native_terminal_state_not_executed"
               for row in result["branches"])


def test_public_restore_mismatch_blocks_any_execution(tmp_path):
    plan = make_plan(tmp_path)
    kwargs, observations = runtime(plan)
    kwargs["request"]["context"] += " unexpected"
    with pytest.raises(RuntimeError, match="request bytes differ"):
        probe.collect_four_seed_branches(plan=plan, **kwargs)
    assert observations == []


def test_wrong_live_episode_blocks_any_execution(tmp_path):
    plan = make_plan(tmp_path)
    kwargs, observations = runtime(plan)
    kwargs["args"].seed = 41
    with pytest.raises(ValueError, match="not registered"):
        probe.collect_four_seed_branches(plan=plan, **kwargs)
    assert observations == []


def test_numpy_private_record_serialization_is_strict():
    assert json.loads(probe.json_text({"a": np.array([1, 2]), "b": np.bool_(True)})) == {"a": [1, 2], "b": True}
    with pytest.raises(ValueError):
        probe.json_text({"a": np.array([np.nan])})


def test_wilson_preserves_sample_uncertainty():
    assert probe.wilson(0, 0) is None
    lo, hi = probe.wilson(4, 4)
    assert lo < .6 and hi == pytest.approx(1.)
