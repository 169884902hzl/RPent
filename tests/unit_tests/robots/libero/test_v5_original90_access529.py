"""Independent pools exclude recorded unknowns and deduplicate exact states."""

import hashlib
import json

import pytest

from scripts.prepare_v5_original90_fixture_grasp529 import audit_ledgers, make_pool


def write_plan(tmp_path, case):
    path = tmp_path / "plan.json"
    path.write_text(json.dumps({"cases": [case]}))
    return {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def test_instrument_unknown_after_physical_contact_is_visited_and_not_rerunnable(tmp_path):
    digest = "a" * 64
    case = {"name": "mug_state15", "episode": {"suite": "libero_90", "task": 65, "seed": 15},
            "state_sha256": digest}
    ledger = tmp_path / "episodes.jsonl"
    ledger.write_text(json.dumps({"case": case, "status": "probe_error", "true_sustained_grasp": None,
        "raised_error": "private metrology error", "contact_samples": [{"step": 40}]}) + "\n")
    hashes, report = audit_ledgers({"job": "3631", "manifest": write_plan(tmp_path, case),
        "ledgers": [str(ledger)], "require_complete": True}, lambda *_: digest)
    assert hashes == {digest}
    assert report["recorded_rows"] == 1
    assert report["unknown_rows_retained_as_visited"][0]["case"] == "mug_state15"


def test_catalog_only_pool_has_no_visits_and_deduplicates_shared_raw_state():
    def metadata(task):
        return {"trials": 2, "instruction": "pick up the mug", "bddl": {}, "init_file": {}}
    states = {33: ["a", "b"], 35: ["b", "c"]}
    cases, report = make_pool([33, 35], metadata, lambda _, t, s: states[t][s], set(), {"a"})
    assert len(cases) == report["unvisited_state_sha"] == 3
    assert report["visited_state_sha"] == 0
    assert report["duplicate_official_states"] == 1
    assert report["unvisited_already_reserved"] == 1


def test_closed_ledger_partial_tail_is_not_silently_ignored(tmp_path):
    case = {"name": "case", "episode": {"suite": "libero_90", "task": 33, "seed": 0}}
    ledger = tmp_path / "episodes.jsonl"
    ledger.write_text(json.dumps({"case": case}))
    with pytest.raises(ValueError, match="incomplete tail"):
        audit_ledgers({"job": "probe", "manifest": write_plan(tmp_path, case),
            "ledgers": [str(ledger)]}, lambda *_: "a" * 64)
