"""Original skill diagnostics keep measured control and private labels apart."""

import json
from types import SimpleNamespace
from contextlib import contextmanager

import numpy as np
import pytest

from robots.libero.v5_state import Entity
from scripts import probe_v5_skill501_original as probe
from scripts import summarize_v5_skill501_original as summary


def case(kind="place"):
    return {"name": "original_probe0", "episode": {"suite": "libero_goal", "task": 0, "seed": 10},
            "kind": kind, "type": "place_on" if kind == "place" else "drawer_open",
            "mode": "on" if kind == "place" else "open", "object_symbol": "original_object_1",
            **({"target_symbol": "original_target_1"} if kind == "place" else {}),
            "setup": [{"tool": "grasp", "object_symbol": "original_object_1", "mode": "direct"}]
                if kind == "place" else [], "condition": "current160", "state_sha256": "a" * 64}


def plan(cases):
    return {"conditions": {"current160": {"executor": "current", "max_chunks": 160}}, "cases": cases}


class FakeExecutor:
    def __init__(self, grasp_verified=True, private_truth=True):
        self.held = None
        entities = [Entity("e1", "bowl", (0, 0, .9), (-.04, -.04, .85), (.04, .04, .95)),
                    Entity("e2", "plate", (.2, 0, .8), (.1, -.1, .8), (.3, .1, .81))]
        self.scene = SimpleNamespace(entities={e.id: e for e in entities}, vocabulary={"bowl", "plate"},
                                     view_axes=((1, 0, 0), (0, -1, 0)))
        self.p = SimpleNamespace(_last_obs_eef_pos=[0, 0, 1.], _last_obs_gripper=.02, env=FakeSkillEnv())
        self.instruction = "put the bowl on the plate"
        self.grasp_verified = grasp_verified
        self.motion_evidence = []
        self.last_verification_measurements = {}
        self.calls = []
    def execute(self, action):
        self.calls.append(action.tool)
        self.motion_evidence = [{"name": "move_to", "steps_used": 2},
                                {"name": "pi0.5", "steps_used": 3, "executed_action_count": 3}]
        self.last_verification_measurements = {"measurement_source": "RGB-D"}
        receipt = {"tool": action.tool, "object": action.object, "executed": True,
                   "verification": "unmeasured"}
        if action.tool == "grasp":
            receipt["grasp_verified"] = self.grasp_verified
            self.held = action.object if self.grasp_verified else None
        elif action.mode in ("on", "in"):
            receipt["place_verified"] = None
            self.held = None
        else:
            receipt["articulate_verified"] = None
        return receipt
    def capture(self):
        pass
    def _refresh(self, vocabulary):
        pass


class FakePolicy:
    def __init__(self, missing=False):
        self.missing = missing
    def bind(self, label, entities, *args, **kwargs):
        if self.missing:
            return None
        return entities[1] if label == "original_target_1" else entities[0]


class FakeRPC:
    def __init__(self, truth=True, setup_truth=True):
        self.truth, self.setup_truth = truth, setup_truth
        self.calls = []
    def call(self, method, **kwargs):
        self.calls.append((method, kwargs))
        if method == "oracle.skill501_truth":
            return {"source": "simulation_diagnostic_only", "satisfied": self.truth,
                    "joint_qpos": [[.05]], "joint_names": ["original_fixture_joint"]}
        if method == "oracle.measure_grasp_hold":
            return {"truth": {"success": self.setup_truth}, "diagnostic_actions": 25}
        if method == "oracle.skill501_grasp_trace_finish":
            return {"true_sustained_grasp_during_skill": True, "true_sustained_grasp_at_end": False}
        return {"snapshot": "private"}


class FakeSkillEnv:
    def __init__(self):
        self._native_terminated = False
        self.truncated = False
        self.active = False
    @property
    def terminated(self):
        return self._native_terminated and not self.active
    @contextmanager
    def complete_skill(self):
        previous = self.active
        self.active = True
        try:
            yield
        finally:
            self.active = previous


def test_private_fixture_truth_reads_site_joints_without_unsupported_state_api():
    site = SimpleNamespace(object_state_type="site", parent_name="cabinet", object_name="drawer_site")
    site.get_joint_state = lambda: pytest.fail("SiteObjectState has no joint implementation")
    predicates = []
    env = SimpleNamespace(object_states_dict={"drawer_site": site},
        object_sites_dict={"drawer_site": SimpleNamespace(joints=["drawer_joint"])},
        fixtures_dict={}, objects_dict={},
        sim=SimpleNamespace(data=SimpleNamespace(time=1., get_joint_qpos=lambda name: .123)),
        _eval_predicate=lambda goal: predicates.append(goal) or True)
    truth = probe.private_skill_truth(SimpleNamespace(env=env),
            {"kind": "articulate", "mode": "open", "object_symbol": "drawer_site"})
    assert truth["joint_names"] == ["drawer_joint"]
    assert truth["joint_qpos"] == [[.123]]
    assert predicates == [["open", "drawer_site"]]


def test_jointless_site_uses_parent_joint_and_parent_official_predicate():
    site = SimpleNamespace(object_state_type="site", parent_name="microwave", object_name="door_site")
    parent = SimpleNamespace(object_state_type="object", object_name="microwave")
    env = SimpleNamespace(object_states_dict={"door_site": site, "microwave": parent},
        object_sites_dict={"door_site": SimpleNamespace(joints=[])},
        fixtures_dict={"microwave": SimpleNamespace(joints=["hinge"])}, objects_dict={},
        sim=SimpleNamespace(data=SimpleNamespace(time=1., get_joint_qpos=lambda name: np.array([1.2]))),
        _eval_predicate=lambda goal: goal == ["close", "microwave"])
    truth = probe.private_skill_truth(SimpleNamespace(env=env),
            {"kind": "articulate", "mode": "close", "object_symbol": "door_site"})
    assert truth["satisfied"] is True
    assert truth["joint_qpos"] == [[1.2]]


def test_unmeasured_public_receipt_is_not_filled_from_private_joint_truth():
    executor, rpc = FakeExecutor(), FakeRPC(truth=True)
    stage = probe.execute_stage(executor, FakePolicy(), rpc, case("articulate"), "articulate", "first_attempt")
    assert stage["receipt"]["articulate_verified"] is None
    assert stage["private_after"]["satisfied"] is True
    assert "joint_qpos" not in stage["receipt"]
    assert all(entity["src"] == "perception" for entity in stage["public_before"]["entities"])
    assert stage["executed_actions"] == 5


def test_real_grasp_setup_is_separate_from_first_place_without_attach():
    executor, rpc = FakeExecutor(), FakeRPC()
    result = probe.run_first_attempt(executor, FakePolicy(), rpc, case(), {"executor": "current"})
    assert executor.calls == ["grasp", "place"]
    assert len(result["setup"]) == 1
    assert result["setup"][0]["phase"] == "setup"
    assert result["first_attempt"]["phase"] == "first_attempt"
    assert result["first_attempt"]["held_before"] == "e1"
    assert result["setup"][0]["private_true_sustained_grasp"] is True
    assert not any("restore" in name or "attach" in name for name, _ in rpc.calls)


def test_failed_public_grasp_setup_keeps_evidence_and_does_not_place():
    executor = FakeExecutor(grasp_verified=False)
    result = probe.run_first_attempt(executor, FakePolicy(), FakeRPC(), case(), {"executor": "current"})
    assert result["status"] == "setup_grasp_not_publicly_verified"
    assert result["first_attempt"] is None
    assert result["setup"][0]["physically_executed"] is True
    assert executor.calls == ["grasp"]


def test_private_setup_failure_is_recorded_without_overriding_public_control():
    executor = FakeExecutor(grasp_verified=True)
    result = probe.run_first_attempt(executor, FakePolicy(), FakeRPC(setup_truth=False), case(), {"executor": "current"})
    assert executor.calls == ["grasp", "place"]
    assert result["setup"][0]["private_true_sustained_grasp"] is False
    assert result["setup"][0]["receipt"]["grasp_verified"] is True
    assert summary.setup_truth({"case": case(), **result}) is False


def test_missing_measured_binding_is_not_a_skill_attempt_or_simulator_fallback():
    executor = FakeExecutor()
    result = probe.run_first_attempt(executor, FakePolicy(missing=True), FakeRPC(), case(), {"executor": "current"})
    assert result["status"] == "setup_public_binding_missing"
    assert not executor.calls


def test_full_subtask_arm_executes_formal_runtime_tool():
    executor = FakeExecutor()
    result = probe.run_first_attempt(executor, FakePolicy(), FakeRPC(), case("articulate"), {"executor": "vla_subtask"})
    assert executor.calls == ["vla_subtask"]
    assert result["first_attempt"]["selected"] == "vla_subtask(e1,open)"


@pytest.mark.parametrize("field,value", [("suite", "libero_goal_swap"), ("kind", "unknown_skill"),
                                        ("mode", "direct"), ("name", "../escape"), ("state_sha256", "missing")])
def test_non_original_or_unregistered_case_contract_is_rejected(field, value):
    chosen = case()
    if field == "suite":
        chosen["episode"][field] = value
    else:
        chosen[field] = value
    with pytest.raises(ValueError):
        probe.validate_manifest(plan([chosen]))


def test_selected_tool_without_motion_is_not_physical_execution():
    assert probe.executed_actions([{ "executed": True}, {"steps_used": 0}]) == 0
    assert probe.executed_actions([{ "steps_used": 5, "executed_action_count": 0}]) == 0


def stage(truth=True, measured=True, executed=True):
    return {"motion_evidence": [{"steps_used": int(executed)}], "physically_executed": executed,
            "private_before": {"satisfied": False}, "private_after": {"satisfied": truth},
            "receipt": {"tool": "place", "place_verified": measured, "articulate_verified": measured}}


def row(chosen=None, truth=True, measured=True, executed=True, setup=True):
    return {"case": chosen or case(), "status": "first_attempt_recorded", "wall_s": 10.,
            "setup": [{"receipt": {"tool": "grasp"}, "private_true_sustained_grasp": setup}],
            "first_attempt": stage(truth, measured, executed)}


def test_summary_reports_both_false_directions_precision_recall_and_unmeasured():
    rows = [row(truth=truth, measured=measured) for truth, measured in
            ((True, True), (True, False), (False, True), (False, False), (True, None))]
    result = summary.metrics(rows, 5)
    assert result["confusion"] == {"tp": 1, "fn": 1, "fp": 1, "tn": 1, "unmeasured_private_positive": 1}
    assert result["precision"] == result["recall"] == .5
    assert result["false_positive_count"] == result["false_negative_count"] == 1
    assert result["public_unmeasured"] == 1
    assert result["public_measurement_coverage"] == .8
    assert result["true_successes"] == 3


def test_unknown_or_nonexecuted_trials_do_not_become_official_failure_or_success():
    result = summary.metrics([row(truth=None), row(executed=False)], 2)
    assert result["known_truth"] == 0
    assert result["true_successes"] == 0
    assert result["success_over_executed_known"] is None
    assert result["failure_counts"] == {"private_truth_unavailable": 1, "no_physical_execution": 1}


def test_first_place_metrics_disclose_false_setup_and_all_planned_denominator():
    rows = [row(), row(setup=False)]
    result = summary.metrics(rows, 10)
    assert result["first_place_success_over_true_setup"] == 1
    assert result["first_place_true_setup_coverage_over_planned"] == .1
    assert result["success_over_planned"] == .2
    assert result["numeric_first_place_targets_met"] is False
    assert result["missing"] == 8


def test_fixture_null_verification_stays_unmeasured_in_summary():
    result = summary.metrics([row(case("articulate"), measured=None)], 1)
    assert result["precision"] is None
    assert result["public_unmeasured"] == 1


def test_even_complete_100_trial_skill_exploration_never_authorizes_qualification(tmp_path):
    cases = [dict(case(), name=f"trial_{index}") for index in range(100)]
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps(plan(cases)))
    records = []
    for chosen in cases:
        directory = tmp_path / chosen["name"]
        directory.mkdir()
        trace = directory / "choices.jsonl"
        trace.write_text('{"executed":true}\n')
        records.append({**row(chosen), "output_dir": str(directory), "choices_sha256": probe.sha(trace)})
    ledger = tmp_path / "ledger.jsonl"
    ledger.write_text("".join(json.dumps(record) + "\n" for record in records))
    result = summary.summarize([manifest], [ledger])
    assert result["complete"] is True
    assert result["qualification_authorized"] is False
    assert result["by_type_condition"]["place_on/current160"]["numeric_first_place_targets_met"] is True
    assert result["by_type_condition"]["place_on/current160"]["unique_original_initial_states"] == 1
    (tmp_path / cases[0]["name"] / "choices.jsonl").write_text("changed")
    with pytest.raises(ValueError, match="trace SHA"):
        summary.summarize([manifest], [ledger])


def test_duplicate_changed_or_missing_trial_is_not_silently_replaced(tmp_path):
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps(plan([case()])))
    result = summary.summarize([manifest], [tmp_path / "missing.jsonl"])
    assert result["complete"] is False
    assert result["missing_cases"] == ["original_probe0"]
    with pytest.raises(ValueError, match="duplicate manifest"):
        summary.summarize([manifest, manifest], [])


def test_original_success_in_setup_does_not_block_registered_reverse_first_attempt():
    executor = FakeExecutor()
    selected = case("articulate")
    selected.update(mode="turn_off", type="stove_turn_off", setup=[{
        "tool": "articulate", "object_symbol": "original_object_1", "mode": "turn_on"}])
    execute = executor.execute
    def setup_then_reverse(action):
        assert executor.p.env.terminated is False
        receipt = execute(action)
        if action.mode == "turn_on":
            executor.p.env._native_terminated = True
        return receipt
    executor.execute = setup_then_reverse
    result = probe.run_registered_skill(executor, FakePolicy(), FakeRPC(), selected, {"executor": "current"})
    assert executor.calls == ["articulate", "articulate"]
    assert result["first_attempt"]["physically_executed"] is True
    assert result["native_original_success_latched"] is True
    assert executor.p.env.terminated is True


def private_sample(time, lifted=True, touching_support=False):
    return {"sim_time": time, "lower_extent_m": .84 if lifted else .8,
            "finger_contact": lifted, "other_contact_geoms": ["table"] if touching_support else []}


def test_control_step_trace_preserves_grasp_then_release_as_two_different_events():
    reference = {"lower_extent_m": .8, "other_contact_geoms": ["table"]}
    samples = [private_sample(.1 * index) for index in range(7)] + [private_sample(.7, lifted=False)]
    result = probe.private_grasp_trace_summary(reference, samples)
    assert result["true_sustained_grasp_during_skill"] is True
    assert result["true_sustained_grasp_at_end"] is False
    assert result["first_sustained_grasp"]["truth"]["success"] is True
    assert result["control_steps_sampled"] == 8


def test_lift_window_with_contact_interruption_is_not_a_sustained_grasp():
    reference = {"lower_extent_m": .8, "other_contact_geoms": ["table"]}
    samples = [private_sample(.1 * index) for index in range(5)]
    samples += [private_sample(.5, lifted=False)]
    samples += [private_sample(.6 + .1 * index) for index in range(4)]
    result = probe.private_grasp_trace_summary(reference, samples)
    assert result["true_sustained_grasp_during_skill"] is False
    assert result["true_sustained_grasp_at_end"] is False


def test_original_fixture_support_contact_prevents_false_grasp_truth():
    reference = {"lower_extent_m": .8, "other_contact_geoms": ["table"]}
    samples = [private_sample(.1 * index, touching_support=True) for index in range(10)]
    assert probe.private_grasp_trace_summary(reference, samples)["true_sustained_grasp_during_skill"] is False


def test_full_transfer_arm_keeps_intermediate_grasp_and_final_subtask_independent(monkeypatch):
    selected = case("grasp_then_subtask")
    selected.update(mode="on", target_symbol="original_target_1", setup=[], type="pan_handle_full")
    @contextmanager
    def scoped_controls(executor, rpc, case, condition, action, evidence):
        evidence["executed_vla_actions"] = 10
        evidence["public_grasp_observations"] = [{"witness": "measured"}]
        yield
    monkeypatch.setattr(probe, "contact_probe_controls", scoped_controls)
    executor = FakeExecutor()
    result = probe.run_registered_skill(executor, FakePolicy(), FakeRPC(), selected, {"executor": "vla_subtask"})
    assert executor.calls == ["vla_subtask"]
    assert result["private_grasp_phase"]["true_sustained_grasp_during_skill"] is True
    assert result["private_grasp_phase"]["true_sustained_grasp_at_end"] is False
    assert result["first_attempt"]["private_after"]["satisfied"] is True
    report = summary.grasp_phase_metrics([{**result, "case": selected}], 1)
    assert report["grasp_during_skill_success_rate"] == 1
    assert report["subtask_completion_rate"] == 1
    assert report["counts"]["sustained_grasp_then_completed_release"] == 1


def test_complete_registered_full_contract_still_only_accepts_on_or_in():
    selected = case("grasp_then_subtask")
    selected.update(mode="on", target_symbol="original_target_1", setup=[])
    probe.validate_manifest(plan([selected]))
    selected["mode"] = "grasp_verified"
    with pytest.raises(ValueError, match="skill/mode"):
        probe.validate_manifest(plan([selected]))


def test_private_rpc_snapshot_arrays_roundtrip_without_dropping_fields_or_mutation():
    snapshot = {"sim_state": np.asarray([.1, .2, .3], dtype=np.float64),
                "actuator_state": {"data": {"ctrl": np.array([[1., 2.]], dtype=np.float32)},
                                   "robots": [{"current_action": np.array([1.])}]},
                "counters": {"elapsed_steps": np.array([42]), "reward": np.float32(.25)},
                "completed": np.bool_(True)}
    record = {"initial_snapshot": snapshot, "before_first_attempt_snapshot": snapshot,
              "after_first_attempt_snapshot": snapshot, "private_grasp_phase": {"success": np.bool_(False)}}
    with pytest.raises(TypeError, match="ndarray"):
        json.dumps(record)
    restored = json.loads(probe.diagnostic_json(record))
    assert restored["initial_snapshot"]["sim_state"] == [.1, .2, .3]
    assert restored["before_first_attempt_snapshot"]["actuator_state"]["data"]["ctrl"] == [[1., 2.]]
    assert restored["after_first_attempt_snapshot"]["counters"] == {"elapsed_steps": [42], "reward": .25}
    assert restored["initial_snapshot"]["completed"] is True
    assert restored["private_grasp_phase"]["success"] is False
    assert isinstance(snapshot["sim_state"], np.ndarray)


@pytest.mark.parametrize("value", [object(), {"measurement": np.array([np.nan])}, {"measurement": np.float32(np.inf)}])
def test_invalid_diagnostic_values_still_fail_instead_of_losing_evidence(value):
    with pytest.raises((TypeError, ValueError)):
        probe.diagnostic_json(value)
