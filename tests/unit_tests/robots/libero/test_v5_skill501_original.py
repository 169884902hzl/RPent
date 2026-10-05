"""Original skill diagnostics keep measured control and private labels apart."""

import json
from dataclasses import replace
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


def public_drawer_case():
    return {**case("articulate"), "object_symbol": "private_unresolvable_fixture_symbol",
            "object_category": "cabinet middle drawer", "subtask_prompt": "open the cabinet middle drawer"}


def measured_cabinet_executor():
    executor = FakeExecutor()
    cabinet = Entity("e98", "cabinet", (0., .2, 1.), (-.1, .1, .8), (.1, .3, 1.2))
    top = Entity("e34", "cabinet top surface", (0., .2, 1.2), (-.1, .1, 1.19), (.1, .3, 1.2), part_of="e98")
    executor.scene.entities = {entity.id: entity for entity in (cabinet, top)}
    executor.instruction = "close the bottom drawer of the cabinet"
    return executor


def test_current_arm_reuses_unique_measured_cabinet_and_preserves_public_middle(monkeypatch):
    executor = measured_cabinet_executor()
    seen = []
    execute = executor.execute
    def recording(action):
        seen.append((action.text(), executor.instruction))
        return execute(action)
    monkeypatch.setattr(executor, "execute", recording)
    result = probe.run_first_attempt(executor, FakePolicy(missing=True), FakeRPC(),
                                     public_drawer_case(), {"executor": "current"})
    assert seen == [("articulate(e98,open)", "open the cabinet middle drawer")]
    assert executor.instruction == "close the bottom drawer of the cabinet"
    stage = result["first_attempt"]
    assert stage["binding_evidence"]["basis"] == "unique_measured_cabinet_public_drawer_instruction"
    assert stage["contact_instruction"]["scoped_override"] is True
    assert len(stage["public_before"]["entities"]) == 2
    assert not any("middle drawer" in entity["name"] for entity in stage["public_before"]["entities"])


def test_vla_arm_keeps_missing_real_drawer_binding_without_coarse_prompt_substitution():
    executor = measured_cabinet_executor()
    result = probe.run_first_attempt(executor, FakePolicy(missing=True), FakeRPC(),
                                     public_drawer_case(), {"executor": "vla_subtask"})
    assert result["status"] == "first_attempt_public_binding_missing"
    assert result["first_attempt"] is None and executor.calls == []


def test_current_arm_does_not_guess_between_two_visible_cabinets():
    executor = measured_cabinet_executor()
    executor.scene.entities["e2"] = Entity("e2", "cabinet", (.3, .2, 1.), (.2, .1, .8), (.4, .3, 1.2))
    result = probe.run_first_attempt(executor, FakePolicy(missing=True), FakeRPC(),
                                     public_drawer_case(), {"executor": "current"})
    assert result["status"] == "first_attempt_public_binding_missing" and executor.calls == []


def test_private_fixture_symbol_alone_cannot_supply_public_drawer_ordinal():
    executor = measured_cabinet_executor()
    spec = {**case("articulate"), "object_symbol": "wooden_cabinet_1_middle_region"}
    result = probe.run_first_attempt(executor, FakePolicy(missing=True), FakeRPC(), spec, {"executor": "current"})
    assert result["status"] == "first_attempt_public_binding_missing" and executor.calls == []


def test_setup_drawer_instruction_comes_from_registered_public_category():
    spec = {"mode": "close", "object_category": "cabinet bottom drawer"}
    assert probe.registered_drawer_instruction(spec) == "close the cabinet bottom drawer"
    spec["subtask_prompt"] = "close the cabinet top drawer"
    with pytest.raises(ValueError, match="contradicts"):
        probe.registered_drawer_instruction(spec)


def test_scoped_public_instruction_restored_on_execution_failure(monkeypatch):
    executor = measured_cabinet_executor()
    def fail(action):
        assert executor.instruction == "open the cabinet middle drawer"
        raise RuntimeError("contact failed")
    monkeypatch.setattr(executor, "execute", fail)
    result = probe.run_first_attempt(executor, FakePolicy(missing=True), FakeRPC(),
                                     public_drawer_case(), {"executor": "current"})
    assert result["status"] == "probe_error"
    assert executor.instruction == "close the bottom drawer of the cabinet"


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


def test_fixture_setup_truth_is_audited_against_its_own_mode_not_the_first_target():
    chosen = {**public_drawer_case(), "mode": "close", "setup": [{"mode": "open"}]}
    setup = {"selected": "articulate(e1,open)", "receipt": {"mode": "open"},
             "private_before": {"predicate": ["open", "drawer"], "satisfied": True},
             "private_after": {"predicate": ["open", "drawer"], "satisfied": False}}
    first = {"selected": "articulate(e1,close)", "receipt": {"mode": "close"},
             "private_before": {"predicate": ["close", "drawer"], "satisfied": True},
             "private_after": {"predicate": ["close", "drawer"], "satisfied": True}}
    audit = summary.fixture_mode_audit({"case": chosen, "status": "recorded", "setup": [setup], "first_attempt": first})
    assert audit["setup"][0]["spec_mode"] == audit["setup"][0]["receipt_mode"] == "open"
    assert audit["setup"][0]["private_after_queried_mode"] == "open"
    assert audit["setup"][0]["private_before"] is True and audit["setup"][0]["private_after"] is False
    assert audit["setup"][0]["queried_requested_mode"] is True
    assert audit["first_attempt"]["private_after_queried_mode"] == "close"


def test_fixture_mode_audit_normalizes_stove_and_exposes_wrong_queries():
    chosen = {**case("articulate"), "mode": "turn_off", "setup": [{"mode": "turn_on"}]}
    stage = {"selected": "articulate(e1,turn_on)", "receipt": {"mode": "turn_on"},
             "private_before": {"predicate": ["turnon", "stove"], "satisfied": False},
             "private_after": {"predicate": ["turnon", "stove"], "satisfied": True}}
    row = {"case": chosen, "status": "setup", "setup": [stage]}
    audit = summary.fixture_mode_audit(row)
    assert audit["setup"][0]["expected_private_predicate_mode"] == "turnon"
    assert audit["setup"][0]["queried_requested_mode"] is True
    stage["private_after"]["predicate"][0] = "turnoff"
    assert summary.fixture_mode_audit(row)["setup"][0]["queried_requested_mode"] is False


def test_grasp_verifier_confusion_uses_end_hold_without_punishing_macro_release():
    rows=[]
    for end, visual in ((True, True), (False, True), (True, False), (False, False)):
        rows.append({"status": "recorded", "first_attempt": {
            "receipt": {"grasp_verified": visual}, "private_after": {"satisfied": False}},
            "private_grasp_phase": {"true_sustained_grasp_during_skill": True,
                                    "true_sustained_grasp_at_end": end}})
    rows.append({"status": "recorded", "first_attempt": {
        "receipt": {"place_verified": True}, "private_after": {"satisfied": True}},
        "private_grasp_phase": {"true_sustained_grasp_during_skill": True,
                                "true_sustained_grasp_at_end": False}})
    report=summary.grasp_phase_metrics(rows, 5)
    verifier=report["runtime_grasp_verifier_against_end_hold"]
    assert verifier["confusion"] == {"tp": 1, "fp": 1, "fn": 1, "tn": 1, "public_grasp_not_measured": 1}
    assert verifier["false_positive_count"] == verifier["false_negative_count"] == 1
    assert verifier["agreement"] == .5
    assert report["counts"]["sustained_grasp_then_completed_release"] == 1


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


class ContactExecutor(FakeExecutor):
    def __init__(self, independent=False):
        super().__init__()
        self.grasp_independent_views_v1 = independent
        self.grasp_minimum_opening = .003
        self.p._last_obs_eef_pos = np.array([0., 0., 1.])
        self.approaches, self.chunk_calls, self.verifier_calls = [], [], []
        self.p._vlm_chunk = self.original_chunk
        self.scene.measure_handle = lambda obj: None

    def stage_grasp(self, source, pose, receipt, **kwargs):
        self.approaches.append((source, pose, kwargs))
        return True

    def vla_act(self, *args, **kwargs):
        return {"legacy": True}

    def _execute(self, selected, receipt, card):
        self.calls.append(selected)

    def original_chunk(self, *args, **kwargs):
        self.chunk_calls.append((args, kwargs))
        self.motion_evidence.append({"executed_action_count": 5})
        return {"executed_chunk": True}

    def opening_may_hold(self, opening):
        return True


def contact_case():
    return {**case("grasp_then_subtask"), "mode": "on", "setup": [], "target_symbol": "original_target_1"}


def contact_condition(**overrides):
    return {"executor": "current", "profile": "high_short", "contact_approach": "measured_handle",
            "max_chunks": 160, **overrides}


@pytest.mark.parametrize("fallback", [None, "measured_bounds_centre"])
def test_missing_handle_only_uses_explicit_measured_bounds_fallback(fallback):
    from robots.libero.v5_state import Candidate, entity_record

    executor, evidence, receipt = ContactExecutor(), {}, {}
    obj = replace(executor.scene.entities["e1"], name="frypan")
    executor.scene.entities[obj.id] = obj
    condition = contact_condition(**({"contact_approach_fallback": fallback} if fallback else {}))
    with probe.contact_probe_controls(executor, FakeRPC(), contact_case(), condition,
                                      Candidate("grasp", "e1"), evidence):
        accepted = executor.stage_grasp(obj, [99, 99, 99], receipt)
    assert evidence["approach"]["measurement"] == entity_record(obj)
    if fallback:
        assert accepted is True
        assert executor.approaches[0][1] == [0., 0., 1.15]
        assert evidence["approach"]["original_method"] == "visible_handle_not_measured"
        assert evidence["approach"]["rejection"] == "visible_handle_not_measured"
        assert evidence["approach"]["method"] == "measured_bounds_centre"
    else:
        assert accepted is False
        assert not executor.approaches
        assert receipt["grasp_verified"] is None
        assert receipt["failure_reason"] == "visible_handle_not_measured"


def test_measured_handle_keeps_its_position_when_fallback_is_enabled():
    from robots.libero.v5_state import Candidate

    executor, evidence = ContactExecutor(), {}
    obj = replace(executor.scene.entities["e1"], name="moka pot")
    executor.scene.entities[obj.id] = obj
    executor.scene.measure_handle = lambda source: (.03, .02, .98)
    condition = contact_condition(contact_approach_fallback="measured_bounds_centre")
    with probe.contact_probe_controls(executor, FakeRPC(), contact_case(), condition,
                                      Candidate("vla_subtask", "e1"), evidence):
        executor._execute(Candidate("vla_subtask", "e1"), {}, None)
    assert executor.approaches[0][1] == [.03, .02, 1.18]
    assert evidence["approach"]["method"] == "measured_visible_handle"
    assert "fallback" not in evidence["approach"]
    assert len(executor.calls) == 1
    assert executor.calls[0].tool == "vla_subtask"


@pytest.mark.parametrize("verified", [True, False, None])
def test_independent_verdict_replaces_legacy_result_after_public_helper(monkeypatch, verified):
    from robots.libero.v5_state import Candidate
    from scripts import probe_v5_grasp449_20261005 as grasp_probe

    executor, evidence, sequence = ContactExecutor(independent=True), {}, []
    legacy = {"frames": [{"passes_lower_rise_and_aperture": True}]}

    def public_helper(*args, **kwargs):
        sequence.append("legacy_public_hold")
        return {"grasp_verified": True, "stop": "grasp_verified", "final_grasp_measurement": True}, {"chunks_used": 2}, legacy

    def independent_verifier(source):
        sequence.append("independent_public_verifier")
        executor.last_verification_measurements["independent_grasp"] = {"verified": verified, "frames": [1, 2]}
        return verified

    monkeypatch.setattr(grasp_probe, "rpent_pick_then_stable_measure", public_helper)
    executor.verify_grasp_measurement = independent_verifier
    condition = contact_condition(contact_stop="rpent_pick")
    with probe.contact_probe_controls(executor, FakeRPC(), contact_case(), condition,
                                      Candidate("grasp", "e1"), evidence):
        result = executor.vla_act("unused complete task", 160, "grasp_verified", executor.scene.entities["e1"])
    assert sequence == ["legacy_public_hold", "independent_public_verifier"]
    assert result["grasp_verified"] is verified
    assert result["final_grasp_measurement"] is True
    assert evidence["stable_visual_grasp"] == legacy
    assert evidence["contact_prompts"][0]["text"] == "pick up the bowl"
    assert evidence["independent_visual_grasp"]["verified"] is verified
    executor.last_verification_measurements["independent_grasp"]["frames"].append(3)
    assert evidence["independent_visual_grasp"]["frames"] == [1, 2]


def test_legacy_public_helper_keeps_default_verdict_without_new_verification(monkeypatch):
    from robots.libero.v5_state import Candidate
    from scripts import probe_v5_grasp449_20261005 as grasp_probe

    executor, evidence = ContactExecutor(), {}
    executor.verify_grasp_measurement = lambda obj: pytest.fail("default route cannot acquire new hold")
    monkeypatch.setattr(grasp_probe, "rpent_pick_then_stable_measure", lambda *args, **kwargs:
        ({"grasp_verified": True, "stop": "grasp_verified"}, {"chunks_used": 1}, {"legacy": True}))
    with probe.contact_probe_controls(executor, FakeRPC(), contact_case(), contact_condition(contact_stop="rpent_pick"),
                                      Candidate("grasp", "e1"), evidence):
        result = executor.vla_act("unused", 160, "grasp_verified", executor.scene.entities["e1"])
    assert result["grasp_verified"] is True
    assert "independent_visual_grasp" not in evidence


def test_macro_independent_frames_preserve_unknown_and_do_not_hold_or_stop():
    from robots.libero.v5_state import Candidate

    executor, evidence = ContactExecutor(independent=True), {}
    verdicts = iter([None, False, True])
    executor.independent_grasp_frame = lambda obj, support: {"verified": next(verdicts), "per_view": {}}
    executor.verify_grasp_measurement = lambda obj: pytest.fail("macro cannot acquire verification hold")
    condition = contact_condition(executor="vla_subtask", contact_approach="measured_bounds_centre")
    with probe.contact_probe_controls(executor, FakeRPC(), contact_case(), condition,
                                      Candidate("vla_subtask", "e1"), evidence):
        for _ in range(3):
            assert executor.p._vlm_chunk("complete transfer") == {"executed_chunk": True}
    assert len(executor.chunk_calls) == 3
    assert evidence["executed_vla_actions"] == 15
    assert [frame["verified"] for frame in evidence["independent_grasp_frame_observations"]] == [None, False, True]
    assert len(evidence["public_grasp_observations"]) == 1
    assert evidence["public_grasp_observations"][0]["interpretation"] == "single_frame_witness_not_two_frame_grasp_verdict"
