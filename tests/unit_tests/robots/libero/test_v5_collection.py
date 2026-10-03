"""Collection labels need tested outcomes and the instruction's progress."""

import pytest

from robots.libero.v5_collection import accepted_branch
from robots.libero.v5_state import Candidate


def test_measured_progress_matches_registered_five_bands():
    from robots.libero.v5_progress import PROGRESS_CHOICES, measured_progress

    assert len(PROGRESS_CHOICES) == 5
    assert [measured_progress(n, 8)[0] for n in (0, 1, 4, 6, 8)] == list(map(str, range(5)))


def test_premature_finish_is_negative_even_when_finish_executed():
    before = {"done": False, "satisfied": [False]}
    assert accepted_branch(Candidate("finish"), {"executed": True}, before, before) is False
    done = {"done": True, "satisfied": [True]}
    assert accepted_branch(Candidate("finish"), {"executed": True}, done, done) is True
    assert accepted_branch(Candidate("ask_help"), {"executed": True}, done, done) is False


def test_verified_wrong_destination_is_not_an_acceptable_task_action():
    before = {"done": False, "satisfied": [False]}
    place = Candidate("place", "e1", "e2", "in")
    assert accepted_branch(place, {"place_verified": True}, before, before) is False
    after = {"done": True, "satisfied": [True]}
    assert accepted_branch(place, {"place_verified": True}, before, after) is True


def test_an_executed_grasp_does_not_imply_verified_grasp():
    status = {"done": False, "satisfied": [False]}
    action = Candidate("grasp", "e1", mode="direct")
    assert accepted_branch(action, {"executed": True}, status, status, required_objects={"e1"}) is False
    assert accepted_branch(action, {"grasp_verified": True}, status, status, required_objects={"e1"}) is True
    assert accepted_branch(action, {"grasp_verified": True}, status, status, required_objects={"e2"}) is None


def test_completed_physical_goal_and_grasp_verification_are_separate():
    before = {"done": False, "satisfied": [False]}
    after = {"done": True, "satisfied": [True]}
    assert accepted_branch(Candidate("grasp", "e1", mode="direct"),
                           {"executed": True, "grasp_verified": False}, before, after,
                           required_objects={"e1"}) is True


def test_physical_container_progress_survives_failed_visual_above_rim_check():
    before = {"done": False, "satisfied": [False, False]}
    after = {"done": False, "satisfied": [True, False]}
    action = Candidate("place", "e1", "e2", "in")
    receipt = {"executed": True, "verification": "failed", "place_verified": False}
    assert accepted_branch(action, receipt, before, after) is True
    regress_before = {"done": False, "satisfied": [True, False]}
    regress_after = {"done": False, "satisfied": [False, True]}
    assert accepted_branch(action, receipt, regress_before, regress_after) is False


def test_storage_prerequisite_open_is_acceptable_and_early_close_is_not():
    closed = {"done": False, "goals": [["close", "drawer"], ["in", "bowl", "drawer"]],
              "satisfied": [True, False], "storage_open": {"drawer": False}}
    opened = {**closed, "satisfied": [False, False], "storage_open": {"drawer": True}}
    receipt = {"executed": True, "verification": "unverified"}
    assert accepted_branch(Candidate("articulate", "e2", mode="open"), receipt, closed, opened) is True
    assert accepted_branch(Candidate("articulate", "e2", mode="close"), receipt, opened, closed) is False


def test_native_step_and_later_predicates_are_distinct_private_evidence(monkeypatch):
    from types import SimpleNamespace

    import numpy as np

    from robots.libero.v5_env_server import V5EnvFacade
    from robots.libero.v5_oracle_server import OriginalOracleFacade

    current = {"on": True}
    worker = SimpleNamespace(env_call=lambda *args, **kwargs: current['on'])
    facade = OriginalOracleFacade.__new__(OriginalOracleFacade)
    facade._env = SimpleNamespace(_elapsed_steps=np.array([7]),
                                  env=SimpleNamespace(workers=[worker]))
    facade._goals = [['on', 'bowl', 'plate']]
    facade._bddl_sha = 'original'
    facade._native_diagnostic = True
    facade._native_success_events = []
    monkeypatch.setattr(V5EnvFacade, 'step', lambda self, action: ({}, 0, True, False, {}))
    facade.step([0] * 7)
    current['on'] = False
    after_lift = facade.goal_status()
    assert after_lift['done'] is False and after_lift['satisfied'] == [False]
    assert after_lift['native_success_events'] == [{
        'elapsed_steps': [7], 'raw_termination': True,
        'satisfied_at_native_step': [True], 'all_predicates_at_native_step': True,
    }]


def test_repeated_branch_restore_keeps_rollout_native_history_and_counters():
    from types import SimpleNamespace

    import numpy as np

    from robots.libero.v5_oracle_server import OriginalOracleFacade

    state = np.array([1., 2., 3.])

    def restore_physics(value):
        state[:] = value
        return {}

    worker = SimpleNamespace(
        get_sim_state=lambda: state.copy(),
        set_init_state=restore_physics,
        env_call=lambda name, **kwargs: {"ctrl": [0.5]} if name == "v5_actuator_state" else {},
    )
    facade = OriginalOracleFacade.__new__(OriginalOracleFacade)
    facade._meta = {"suite": "libero_spatial", "task": 0, "seed": 30}
    facade._bddl_sha = "original"
    facade._env = SimpleNamespace(
        env=SimpleNamespace(workers=[worker]),
        _elapsed_steps=np.array([7]),
        success_once=np.array([True]),
        _wrap_obs=lambda raw: {},
    )
    facade._strip_obs = lambda obs: obs
    actual_event = {"elapsed_steps": [7], "all_predicates_at_native_step": True}
    facade._native_success_events = [actual_event.copy()]
    snapshot = facade.snapshot()
    for branch_step in (12, 16):
        state[:] = -1
        facade._env._elapsed_steps[:] = branch_step
        facade._env.success_once[:] = False
        facade._native_success_events.append({"elapsed_steps": [branch_step]})
        facade.restore(snapshot)
        assert facade._native_success_events == [actual_event]
        np.testing.assert_array_equal(facade._env._elapsed_steps, [7])
        np.testing.assert_array_equal(facade._env.success_once, [True])
        np.testing.assert_array_equal(state, [1., 2., 3.])


def _collect_branch_chain(*, done, bound=False):
    import copy
    import random
    from types import SimpleNamespace

    from robots.libero.v5_collection import OriginalCollection
    from robots.libero.v5_state import serialize

    status = {"done": done, "goals": [["on", "bowl", "plate"]], "satisfied": [done]}
    calls, executed, written = [], [], []

    def call(method, args=None, **kwargs):
        calls.append(method)
        if method == "oracle.status":
            return copy.deepcopy(status)
        if method == "oracle.snapshot":
            return copy.deepcopy(status)
        if method == "oracle.restore":
            status.update(args[0])
            # Model the observed contact rebuild at a native terminal state.
            if done:
                status.update(done=False, satisfied=[False])
            return {}
        raise AssertionError(method)

    scene = SimpleNamespace(**{key: {} for key in (
        "entities", "vocabulary", "_scores", "_ids", "fixture_measurement_evidence",
        "rejected_fixture_measurements", "fixture_front_axes", "_rejected_fixture_entities",
        "perception_evidence", "measurement_clouds")},
        work_surface_measurement={"height_m": .9}, _drawer_endpoint_anchors={"e2": "measured_anchor"}, last_measurement_s=0,
        support_z=0, view_axes=None, dual_view_fusion_v1=False, shape_fit_v1=False)
    p = SimpleNamespace(_last_obs={}, _last_obs_gripper=.08,
                        env=SimpleNamespace(terminated=done, truncated=False, last_obs={}))
    p.set_obs = lambda obs: setattr(p, "_last_obs", obs)
    executor = SimpleNamespace(p=p, scene=scene, held=None, held_offset=None, receipts=[],
                               target_cache={}, last_verification_measurements={}, motion_evidence=[])

    def execute(candidate, **kwargs):
        assert scene.work_surface_measurement == {"height_m": .9}
        assert scene._drawer_endpoint_anchors == {"e2": "measured_anchor"}
        executed.append(candidate.tool)
        receipt = {"tool": candidate.tool, "executed": True}
        if candidate.tool == "place":
            receipt.update(object=candidate.object, target=candidate.target, mode=candidate.mode)
        if candidate.tool not in ("finish", "ask_help"):
            assert not p.env.terminated, "physical branch after native termination"
            status.update(done=True, satisfied=[True])
            receipt["grasp_verified"] = True
            scene.work_surface_measurement["height_m"] = 1.4
            scene._drawer_endpoint_anchors["e2"] = "alternative_pose"
        executor.receipts.append(receipt)
        return receipt

    executor.execute = execute
    collector = OriginalCollection.__new__(OriginalCollection)
    collector.rng = random.Random(0)
    collector.counts = {"branches": 0, "next_skill": 0, "zero_signal": 0,
                        "premature_finish_negative": 0}
    collector.config = {"wording_bank_sha256": "bank"}
    collector.source = {}
    collector.split = "train"
    collector.variant = None
    collector.shared = SimpleNamespace(next_skill=lambda row: row, digest=lambda row: "request")
    collector.write = lambda bucket, row: written.append((bucket, copy.deepcopy(row)))
    collector.admit = lambda *args: True
    collector.add_aux = lambda *args: None
    args = SimpleNamespace(suite="libero_spatial", task=0, seed=30,
                           instruction_override="Move the bowl to the plate.", init_state_sha256="init")
    choices = [Candidate("finish"), Candidate("ask_help"),
               Candidate("grasp", "e1", mode="direct"), Candidate("place", "e1", "e2", "on")]
    request = {"context": serialize(args.instruction_override, [], .08, None, [], choices=choices),
               "instruction": "Choose an action.", "options": [c.text() for c in choices]}
    row = collector.before_action(
        args, 1, request, choices[0 if done else 2], choices, scene, executor,
        SimpleNamespace(solved=lambda: done, _solved=done), SimpleNamespace(call=call),
        SimpleNamespace(_bindings={"bowl": "e1", "plate": "e2"} if bound else {}), None, None)
    return row, status, calls, executed, executor


def test_terminal_noop_branches_preserve_contact_predicates_and_skip_physical_alternatives():
    row, status, calls, executed, executor = _collect_branch_chain(done=True)
    assert executed == ["finish", "ask_help"]
    assert "oracle.restore" not in calls
    assert status["satisfied"] == [True] and status["done"] is True
    assert row["acceptable_actions"] == ["C0"]
    assert row["evaluated_actions"] == ["C0", "C1"]
    assert row["unknown_actions"] == ["C2", "C3"]
    assert executor.receipts == []
    assert executor.scene.work_surface_measurement == {"height_m": .9}
    assert executor.scene._drawer_endpoint_anchors == {"e2": "measured_anchor"}


def test_incomplete_physical_branches_still_restore_and_finish_stays_negative():
    row, status, calls, executed, executor = _collect_branch_chain(done=False)
    assert executed == ["grasp", "finish", "place"]
    assert calls.count("oracle.restore") == 2
    assert status["done"] is False and status["satisfied"] == [False]
    assert "C0" in row["evaluated_actions"] and "C0" not in row["acceptable_actions"]
    assert executor.receipts == []


@pytest.mark.parametrize("bound", [False, True])
def test_placement_predicate_is_recorded_only_for_the_tested_bound_goal(bound):
    row, _, _, _, _ = _collect_branch_chain(done=False, bound=bound)
    branch = next(b for b in row["label_evidence"]["branches"] if b["receipt"]["tool"] == "place")
    evidence = branch["predicate_verification_evidence"]
    assert evidence["matching_predicate_indices"] == ([0] if bound else [])
    assert evidence["physical_placement_predicate"] is (True if bound else None)
    assert "physical_placement_predicate" not in str(row["request"])
