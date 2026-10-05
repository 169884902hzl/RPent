"""Explicit original90 metrology must not extend training or model rollout."""

import sys
from types import ModuleType, SimpleNamespace

import pytest

import harness_v5_eval as harness


def diagnostic_args(**changes):
    return SimpleNamespace(**{
        "original90_grasp_diagnostic_v1": True, "provider": "oracle",
        "libero_type": "standard", "suite": "libero_90", "task": 40,
        "max_decisions": 1, "grasp_probe_category": "frypan",
        "done_gated": False, "counterfactual_spec": None, **changes,
    })


@pytest.mark.parametrize("changes", [
    {"provider": "jev"}, {"provider": "qwen4b"}, {"libero_type": "pro"},
    {"suite": "libero_spatial_swap"}, {"suite": "libero_10"},
    {"max_decisions": 2}, {"grasp_probe_category": None}, {"task": 90},
    {"done_gated": True}, {"counterfactual_spec": "/must-not-be-opened"},
])
def test_ineligible_diagnostic_fails_before_any_runtime_dependency(changes):
    with pytest.raises(ValueError, match="original90 grasp diagnostic requires"):
        harness.run_episode(diagnostic_args(**changes))


def test_no_collection_even_with_a_valid_original90_single_grasp():
    with pytest.raises(ValueError, match="no collection"):
        harness.run_episode(diagnostic_args(), collection=object())
    assert harness._original90_grasp_diagnostic(diagnostic_args()) is True


def test_default_flag_does_not_apply_a_new_scope_to_legacy_calls():
    assert harness._original90_grasp_diagnostic(SimpleNamespace()) is False


def test_harness_cli_routes_only_an_explicit_single_grasp(monkeypatch, tmp_path):
    called = []
    monkeypatch.setattr(harness, "run_episode", lambda args: called.append(args))
    monkeypatch.setattr(sys, "argv", [
        "harness_v5_eval.py", "--suite", "libero_90", "--task", "40",
        "--provider", "oracle", "--max-decisions", "1",
        "--grasp-probe-category", "frypan", "--original90-grasp-diagnostic",
        "--choice-package", str(tmp_path / "unread_tokenizer"),
        "--output-dir", str(tmp_path / "uncreated_episode"),
    ])
    harness.main()
    assert len(called) == 1 and called[0].original90_grasp_diagnostic_v1 is True
    assert not (tmp_path / "uncreated_episode").exists()


def test_original90_facade_needs_opt_in_and_still_rejects_pro(monkeypatch):
    from robots.libero.v5_oracle_server import ORIGINAL_SUITES, OriginalOracleFacade

    assert ORIGINAL_SUITES == {"libero_spatial", "libero_object", "libero_goal", "libero_10"}
    monkeypatch.setenv("LIBERO_TYPE", "standard")
    with pytest.raises(ValueError, match="40 original tasks"):
        OriginalOracleFacade(None, meta={"suite": "libero_90"})
    with pytest.raises(ValueError, match="restricted to libero_90"):
        OriginalOracleFacade(None, meta={"suite": "libero_object_swap"}, original90_diagnostic=True)
    monkeypatch.setenv("LIBERO_TYPE", "pro")
    with pytest.raises(ValueError, match="40 original tasks"):
        OriginalOracleFacade(None, meta={"suite": "libero_90"}, original90_diagnostic=True)


def test_opted_in_facade_keeps_predicates_in_private_attributes(monkeypatch, tmp_path):
    from robots.libero.v5_env_server import V5EnvFacade
    from robots.libero.v5_oracle_server import OriginalOracleFacade

    folder = tmp_path / "libero_90"
    folder.mkdir()
    (folder / "pan.bddl").write_text("registered original scene")
    private_goals = [["on", "chefmate_8_frypan_1", "flat_stove_1_cook_region"]]
    libero = ModuleType("libero.libero")
    libero.get_libero_path = lambda key: str(tmp_path)
    parser = ModuleType("libero.libero.envs.bddl_utils")
    parser.robosuite_parse_problem = lambda path: {"goal_state": private_goals}
    monkeypatch.setitem(sys.modules, "libero", ModuleType("libero"))
    monkeypatch.setitem(sys.modules, "libero.libero", libero)
    monkeypatch.setitem(sys.modules, "libero.libero.envs", ModuleType("libero.libero.envs"))
    monkeypatch.setitem(sys.modules, "libero.libero.envs.bddl_utils", parser)
    monkeypatch.setenv("LIBERO_TYPE", "standard")
    initialized = []
    monkeypatch.setattr(V5EnvFacade, "__init__", lambda self, env, **kwargs: initialized.append(kwargs))
    env = SimpleNamespace(task_suite=SimpleNamespace(get_task=lambda task: SimpleNamespace(
        problem_folder="libero_90", bddl_file="pan.bddl")))
    meta = {"suite": "libero_90", "task": 40, "seed": 10}
    facade = OriginalOracleFacade(env, meta=meta, original90_diagnostic=True)
    assert facade._goals == private_goals
    assert initialized[0]["meta"] == meta
    assert "goals" not in initialized[0]["meta"]


def test_oracle_cli_rejects_original90_without_flag_before_loading_assets(monkeypatch):
    from robots.libero import v5_oracle_server as oracle

    monkeypatch.setenv("LIBERO_TYPE", "standard")
    monkeypatch.setattr(oracle, "make_v5_env", lambda *a, **kw: pytest.fail("must not create an env"))
    monkeypatch.setattr(sys, "argv", ["oracle", "--suite", "libero_90", "--task", "40",
                                     "--seed", "10", "--port", "12345"])
    with pytest.raises(SystemExit) as error:
        oracle.main()
    assert error.value.code == 2


def test_oracle_cli_forwards_diagnostic_identity_without_changing_default_scope(monkeypatch):
    from robots.libero import v5_oracle_server as oracle

    env = object()
    calls = []
    monkeypatch.setenv("LIBERO_TYPE", "standard")
    monkeypatch.setattr(oracle, "make_v5_env", lambda *a, **kw: calls.append((a, kw)) or env)

    class Facade:
        def __init__(self, received, **kwargs):
            assert received is env
            self.kwargs = kwargs
            calls.append(kwargs)

        def serve(self, **kwargs):
            calls.append(kwargs)

    monkeypatch.setattr(oracle, "OriginalOracleFacade", Facade)
    monkeypatch.setattr(sys, "argv", ["oracle", "--suite", "libero_90", "--task", "40",
        "--seed", "10", "--port", "12345", "--original90-grasp-diagnostic"])
    oracle.main()
    assert calls[0][0][:3] == (40, 10, "libero_90")
    assert calls[1]["original90_diagnostic"] is True
    assert calls[1]["meta"]["original90_grasp_diagnostic_v1"] is True
    assert calls[2]["port"] == 12345
