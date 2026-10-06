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


def test_embedded_calibration_is_consumed_like_cli_file_before_services(tmp_path):
    from harness_v5_eval import load_grasp_measurement_calibration

    manifest, plan = plan_file(tmp_path)
    calibration = {"opening_calibration": {"open_empty_min_m": .078},
                   "grip_site_geometry": {"xml": pinned(tmp_path / "gripper.xml")},
                   "robot_rigid_transform_validation": {"passed": True}}
    reference = pinned(tmp_path / "calibration.json", json.dumps(calibration))
    plan["robot_calibration_file"] = reference
    plan["conditions"] = {"pan": {"overrides": {"grasp_measurement_calibration": calibration}}}
    manifest.write_text(json.dumps(plan))
    _, checked, _ = preflight.load_pinned_manifest(manifest)
    inline, inline_provenance = load_grasp_measurement_calibration(calibration)
    from_file, file_provenance = load_grasp_measurement_calibration(reference["path"])
    assert inline == from_file == calibration
    assert inline_provenance["source"] == "embedded_manifest"
    assert file_provenance["sha256"] == reference["sha256"]
    assert any(ref["role"] == "pan:public_gripper_geometry"
               for ref in checked["preflight"]["files_checked"])
    calibration["opening_calibration"]["open_empty_min_m"] = .08
    manifest.write_text(json.dumps(plan))
    with pytest.raises(ValueError, match="differs from robot_calibration_file"):
        preflight.load_pinned_manifest(manifest)


def test_bad_calibration_payload_fails_cpu_preflight(tmp_path):
    manifest, plan = plan_file(tmp_path)
    plan["conditions"] = {"pan": {"overrides": {"grasp_measurement_calibration": {"bad": True}}}}
    manifest.write_text(json.dumps(plan))
    with pytest.raises(ValueError, match="missing opening_calibration"):
        preflight.load_pinned_manifest(manifest)
