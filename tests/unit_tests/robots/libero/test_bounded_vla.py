"""Fallback exits promptly using public evidence; history stays development-only."""
import hashlib
import json

import numpy as np
import pytest

from rpent.skill_package.vla import DevelopmentHistory, VLABudget, run_fallback


def invoke(observe, *, native=lambda: False):
    return run_fallback(prompt="pick up the bowl", prepare=lambda: {"success": True},
        predict=lambda _: np.zeros((10, 7)), step=lambda a: ({}, {}), observe=observe,
        native_done=native, handoff=lambda t: {"smooth": True}, budget=VLABudget(10, 3, 5))


def test_contact_success_interrupts_inside_block():
    count = 0
    def observe():
        nonlocal count
        count += 1
        return {"progress_vector_m": [0, 0, .04 if count > 1 else 0],
                "completed": count > 1, "outside_region": False, "evidence": []}
    result = invoke(observe)
    assert result["outcome"] == "success"
    assert result["steps_used"] == 5
    assert result["handoff"]["smooth"]


def test_default_fallback_remeasures_before_the_next_contact_control():
    controls = []
    def observe():
        return {"progress_vector_m": [0, 0, .04 if controls else 0],
            "completed": bool(controls), "outside_region": False, "evidence": []}
    result = run_fallback(prompt="pick up the bowl", prepare=lambda: {"success": True},
        predict=lambda _: np.zeros((10, 7)),
        step=lambda action: (controls.append(action) or {}, {}), observe=observe,
        native_done=lambda: False, handoff=lambda trace: {"executed": True})
    assert len(controls) == 1
    assert result["steps_used"] == 1 and result["outcome"] == "success"


def test_no_progress_exits_after_three_blocks():
    result = invoke(lambda: {"progress_vector_m": [0, 0, 0], "completed": False, "outside_region": False})
    assert result["blocks_used"] == 3
    assert result["steps_used"] == 30
    assert result["stop_reason"] == "no_progress_blocks"


def test_block_cadence_observes_once_per_variable_length_action_block():
    controls, measurements = [], []
    blocks = iter((np.zeros((3, 7)), np.zeros((7, 7))))
    def observe():
        measurements.append(len(controls))
        return {'progress_vector_m': [0, 0, 0], 'completed': len(controls) == 10,
            'outside_region': False}
    result = run_fallback(prompt='pick up the bowl', prepare=lambda: {'success': True},
        predict=lambda _: next(blocks), step=lambda action: (controls.append(action) or {}, {}),
        observe=observe, native_done=lambda: False, handoff=lambda _: {'completed': True},
        budget=VLABudget(controls_per_check=None))
    assert measurements == [0, 3, 10]
    assert result['steps_used'] == 10 and result['outcome'] == 'success'


def test_block_cadence_still_obeys_native_stop_before_the_next_control():
    controls = []
    result = run_fallback(prompt='pick up the bowl', prepare=lambda: {'success': True},
        predict=lambda _: np.zeros((5, 7)), step=lambda action: (controls.append(action) or {}, {}),
        observe=lambda: {'progress_vector_m': [0, 0, 0], 'completed': False, 'outside_region': False},
        native_done=lambda: len(controls) == 2,
        handoff=lambda _: pytest.fail('cannot move after native stop'),
        budget=VLABudget(controls_per_check=None))
    assert result['steps_used'] == 2 and result['stop_reason'] == 'native_success'
    assert len(result['checks']) == 1


def test_no_progress_can_be_disabled_and_control_budget_is_exact():
    result = run_fallback(prompt='pick up the bowl', prepare=lambda: {'success': True},
        predict=lambda _: np.zeros((5, 7)), step=lambda _: ({}, {}),
        observe=lambda: {'progress_vector_m': [0, 0, 0], 'completed': False, 'outside_region': False},
        native_done=lambda: False, handoff=lambda _: {'completed': True},
        budget=VLABudget(blocks=20, no_progress_blocks=None, max_controls=17))
    assert result['steps_used'] == 17 and result['blocks_used'] == 4
    assert result['stop_reason'] == 'control_budget'
    assert result['budget']['no_progress_blocks'] is None
    assert set(result['timing_s']) == {'preparation', 'inference', 'public_observation', 'control', 'handoff', 'other'}


def test_unsettled_handoff_cannot_claim_a_successful_control_return():
    result = run_fallback(prompt='pick up the bowl', prepare=lambda: {'success': True},
        predict=lambda _: np.zeros((5, 7)), step=lambda _: ({}, {}),
        observe=lambda: {'progress_vector_m': [0, 0, 0], 'completed': True, 'outside_region': False},
        native_done=lambda: False, handoff=lambda _: {'executed': True, 'completed': False,
            'reason': 'hold_not_settled'})
    assert result['skill_stop_reason'] == 'measured_success'
    assert result['outcome'] == 'interrupted' and result['stop_reason'] == 'handoff_hold_not_settled'


def test_outside_region_stops_and_history_unknown_is_not_zero_success():
    result = invoke(lambda: {"progress_vector_m": [0, 0, 0], "completed": False, "outside_region": True})
    assert result["stop_reason"] == "left_target_region"
    assert result["steps_used"] == 5
    history = DevelopmentHistory().estimate("pick", "bowl")
    assert history["success_rate"] is None and history["n"] == 0


def test_reject_confirmation_and_pro_history(tmp_path):
    for domain, split in [("libero_pro", "development"), ("libero_original40", "confirmation")]:
        manifest = tmp_path / "manifest.json"
        manifest.write_text(json.dumps({"sources": [{"domain": domain, "split": split}]}))
        with pytest.raises(ValueError):
            DevelopmentHistory(manifest)


def test_valid_history_has_sample_count_and_source_hash(tmp_path):
    source = tmp_path / "rows.jsonl"
    source.write_text(json.dumps({"split": "development", "confirmed_state": False,
        "action": "pick", "category": "bowl", "context": "measured", "steps_used": 42, "success": True})+'\n')
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"sources": [{"domain": "libero_original40", "split": "development",
        "confirmation_states_present": False, "path": str(source), "sha256": hashlib.sha256(source.read_bytes()).hexdigest()}]}))
    estimate = DevelopmentHistory(manifest).estimate("pick", "bowl")
    assert estimate["success_rate"] == 1. and estimate["n"] == 1 and estimate["expected_steps"] == 42


def test_budget_truncation_is_never_reported_as_success():
    result = run_fallback(prompt="pick up the bowl", prepare=lambda: {"success": True},
        predict=lambda _: np.zeros((10, 7)), step=lambda a: ({}, {}),
        observe=lambda: {"progress_vector_m": [0, 0, 0], "completed": False, "outside_region": False},
        native_done=lambda: False, native_stopped=lambda: True,
        handoff=lambda _: pytest.fail("cannot move after truncation"))
    assert result["outcome"] == "interrupted"
    assert result["stop_reason"] == "environment_budget"


def test_failed_handoff_is_distinct_from_a_successful_subtask():
    result = run_fallback(prompt="pick up the bowl", prepare=lambda: {"success": True},
        predict=lambda _: np.zeros((5, 7)), step=lambda a: ({}, {}),
        observe=lambda: {"progress_vector_m": [0, 0, 0], "completed": True, "outside_region": False},
        native_done=lambda: False, handoff=lambda trace: {"executed": False, "steps_used": 0,
            "reason": "braking_screen_rejected"})
    assert result["skill_stop_reason"] == "measured_success"
    assert result["outcome"] == "interrupted"
    assert result["stop_reason"] == "handoff_braking_screen_rejected"
