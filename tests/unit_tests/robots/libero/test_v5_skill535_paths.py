"""Preparation paths remain usable from an isolated runtime source cwd."""

import json
from pathlib import Path

import pytest

from scripts.prepare_v5_skill535_articulate_place_confirmation import (
    _plan, explicit_access_files, identity, load_pinned, tokenizer_files,
)
from scripts.prepare_v5_fixture540_handle_selection import build_selection, TYPES


def test_pinned_relative_input_survives_source_directory_change(tmp_path, monkeypatch):
    preparation = tmp_path / "preparation"
    preparation.mkdir()
    config = preparation / "config.json"
    config.write_text('{"libero_type":"standard"}')
    monkeypatch.chdir(tmp_path)
    original, record = load_pinned(Path("preparation/config.json"))
    source = tmp_path / "source"
    source.mkdir()
    monkeypatch.chdir(source)
    loaded, second_record = load_pinned(Path(record["path"]), record["sha256"])
    assert loaded == original
    assert second_record == record
    assert Path(record["path"]).is_absolute()


def test_tokenizer_inputs_are_pinned_without_directory_enumeration(tmp_path, monkeypatch):
    package = tmp_path / "tokenizer"
    package.mkdir()
    for name in ("tokenizer_config.json", "tokenizer.json", "chat_template.jinja"):
        (package / name).write_text("{}")

    def forbidden_scan(*args, **kwargs):
        raise AssertionError("directory enumeration is forbidden")

    monkeypatch.setattr(Path, "iterdir", forbidden_scan)
    records = tokenizer_files(package)
    assert {Path(ref["path"]).name for ref in records} == {
        "tokenizer_config.json", "tokenizer.json", "chat_template.jinja"}
    assert all(Path(ref["path"]).is_absolute() for ref in records)
    (package / "tokenizer.json").unlink()
    with pytest.raises(ValueError, match="tokenizer.json or vocab.json"):
        tokenizer_files(package)


def test_explicit_access_index_checks_ledgers_and_pinned_manifest(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    reserved = tmp_path / "reserved.json"
    run = tmp_path / "run.json"
    ledger = tmp_path / "episodes.jsonl"
    reserved.write_text("{}")
    run.write_text("{}")
    ledger.write_text('{"preserved_failure":true}\n')
    access = {"reserved_manifests": [identity(reserved)],
              "runs": [{"manifest": identity(run), "ledgers": [identity(ledger)]}]}
    # Old access indexes may contain paths relative to preparation cwd.
    access["runs"][0]["ledgers"][0]["path"] = "episodes.jsonl"
    records = explicit_access_files(access)
    assert {ref["role"] for ref in records} == {
        "reserved_manifest", "access_run_manifest", "access_run_ledger"}
    assert all(Path(ref["path"]).is_absolute() for ref in records)
    ledger.write_text("changed\n")
    with pytest.raises(ValueError, match="explicit access reference changed"):
        explicit_access_files(access)
    ledger.unlink()
    with pytest.raises(FileNotFoundError):
        explicit_access_files(access)


def test_pairwise_method_selection_cannot_claim_confirmation_qualification(tmp_path):
    source = tmp_path / "producer.py"
    source.write_text("# producer\n")
    ref = identity(source)
    rows = [{"kind": "articulate", "type": "drawer_open", "condition": arm}
            for arm in ("current160", "vla_subtask160")]
    plan = _plan("articulate", rows, base_config=ref, choice_package=str(tmp_path),
                 choice_package_files=[ref], catalog_file=ref, access_files=[ref],
                 overlap=[], unique_states={"a" * 64}, prior_files=[], source_script=ref)
    assert plan["cohort"] == "selection"
    assert plan["qualification_authorized"] is False
    assert plan["new_training_rows"] == 0
    assert "not a confirmation batch" in plan["confirmation"]
    assert "disjoint states" in plan["confirmation"]
    # Serialisation does not introduce relative references.
    assert json.loads(json.dumps(plan))["base_config"]["path"] == str(source)


def test_measured_handle_arm_is_separate_and_never_routes_using_private_truth():
    parent = {"cohort": "selection", "qualification_authorized": False,
              "new_training_rows": 0, "conditions": {"current160": {
                  "executor": "current", "max_chunks": 160, "overrides": {}}},
              "cases": [{"name": f"{label}_s{seed}_current160", "kind": "articulate",
                         "type": label, "condition": "current160", "state_sha256": str(seed),
                         "subtask_prompt": "open the middle drawer of the cabinet"}
                        for label in TYPES for seed in range(5)]}
    before = json.loads(json.dumps(parent))
    ref = {"path": "/explicit/producer.py", "sha256": "a" * 64}
    selection = build_selection(parent, ref, 5, ref)
    assert parent == before
    assert len(selection["cases"]) == 30
    arm = selection["conditions"]["measured_fixture_handle160"]
    assert arm["executor"] == "current"
    assert arm["contact_approach"] == "measured_fixture_handle"
    assert arm["overrides"]["dual_view_fusion_v1"] is True
    assert {r["condition"] for r in selection["cases"]} == {"measured_fixture_handle160"}
    assert "no simulated handle" in selection["measured_handle_scope"]["missing_handle"]
    assert selection["qualification_authorized"] is False
