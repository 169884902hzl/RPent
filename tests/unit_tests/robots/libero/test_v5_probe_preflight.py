"""Probe preflight reads pinned files independently of the source cwd."""

import hashlib
import json
from pathlib import Path

import pytest

from scripts import v5_probe_preflight as preflight


def pinned(path, text="asset"):
    path.write_text(text)
    return {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def plan_file(tmp_path):
    package = tmp_path / "model"
    package.mkdir()
    tokenizer = pinned(package / "tokenizer_config.json", "{}")
    plan = {"base_config": pinned(tmp_path / "base.json", '{"libero_type":"standard"}'),
            "choice_package": str(package), "choice_package_files": [tokenizer],
            "cases": [{"name": "case0", "bddl": pinned(tmp_path / "task.bddl"),
                       "init_file": pinned(tmp_path / "init.pruned_init")}]}
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps(plan))
    return manifest, plan


def test_absolute_manifest_works_after_cd_source_and_never_discovers_files(tmp_path, monkeypatch):
    manifest, _ = plan_file(tmp_path)
    source = tmp_path / "source"
    source.mkdir()
    monkeypatch.chdir(source)
    monkeypatch.setattr(Path, "glob", lambda *args: pytest.fail("no glob discovery"))
    monkeypatch.setattr(Path, "rglob", lambda *args: pytest.fail("no recursive discovery"))
    canonical, plan, base = preflight.load_pinned_manifest(manifest)
    assert canonical == manifest and base["libero_type"] == "standard"
    assert len(plan["preflight"]["files_checked"]) == 4


def test_relative_registered_asset_is_rejected_before_service_start(tmp_path):
    manifest, plan = plan_file(tmp_path)
    plan["cases"][0]["bddl"]["path"] = "task.bddl"
    manifest.write_text(json.dumps(plan))
    with pytest.raises(ValueError, match="absolute path"):
        preflight.load_pinned_manifest(manifest)


def test_explicit_choice_hash_and_reservation_inputs_are_checked(tmp_path):
    manifest, plan = plan_file(tmp_path)
    reservation = pinned(tmp_path / "reservation.json", "{}")
    plan["access_reservations"] = {"inputs": [reservation], "prior_manifests": []}
    manifest.write_text(json.dumps(plan))
    preflight.load_pinned_manifest(manifest)
    Path(reservation["path"]).write_text("changed")
    with pytest.raises(ValueError, match="registered access_reservations:inputs changed"):
        preflight.load_pinned_manifest(manifest)
