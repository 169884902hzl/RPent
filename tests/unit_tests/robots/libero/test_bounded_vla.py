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


def test_no_progress_exits_after_three_blocks():
    result = invoke(lambda: {"progress_vector_m": [0, 0, 0], "completed": False, "outside_region": False})
    assert result["blocks_used"] == 3
    assert result["steps_used"] == 30
    assert result["stop_reason"] == "no_progress_blocks"


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
