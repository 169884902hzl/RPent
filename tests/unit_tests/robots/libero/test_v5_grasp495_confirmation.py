"""Reserved confirmation uses a fixed recipe and excludes discovery states."""

import copy
import hashlib
import json
import sys
from types import ModuleType, SimpleNamespace

import numpy as np
import pytest

from scripts import prepare_v5_grasp495_remaining_confirmation as prepare


def digest(text):
    return hashlib.sha256(text.encode()).hexdigest()


def fixtures(group="frypan"):
    parent = {"cases": [{"episode": {"suite": "libero_10", "task": 2, "seed": 0}}],
              "base_config": {"path": "/unused-original-config", "sha256": digest("config")},
              "conditions": {"discovery_winner_must_not_be_selected": {"max_chunks": 1}},
              "truth_protocol": {"success_threshold": .95, "minimum_class_success": .90,
                                 "verifier_agreement_threshold": .95}}
    rows = [{"group": group, "category": "frypan" if group == "frypan" else "moka pot",
             "episode": {"suite": "libero_90", "task": index // 30, "seed": 10 + index % 30},
             "official_init_index": 10 + index % 30,
             "state_sha256": digest(str(index)), "state_hash_encoding": prepare.STATE_ENCODING,
             "source": "official_original_LIBERO90", "name": "reserved_" + str(index),
             "init_file": {"path": "/unopened-init", "sha256": digest("init")},
             "bddl": {"path": "/unopened-original-bddl", "sha256": digest("bddl")}}
            for index in range(100)]
    hashes = {("libero_10", 2, 0): digest("old")}
    hashes.update({(r["episode"]["suite"], r["episode"]["task"], r["episode"]["seed"]): r["state_sha256"]
                   for r in rows})
    recipe = {"schema": prepare.RECIPE_SCHEMA, "group": group, "frozen": True,
              "name": "explicit_handle320_stable_wrist",
              "condition": {"profile": "high_short", "mode": "direct", "max_chunks": 320,
                            "overrides": {"grasp_thin_aperture_v1": True},
                            "contact_prompt_binding": "selected_only", "contact_stop": "rpent_pick",
                            "contact_verification": "stable_lower_gripper_wrist"},
              "exploration_reports": [{"path": "/unopened_report", "sha256": digest("report")}]}
    return parent, {"cases": rows}, recipe, lambda *key: hashes[key]


def build(parent, pool, recipe, loader):
    return prepare.build_confirmation(parent, pool, recipe, group=recipe["group"],
                                      state_sha_for=loader, verify_case_assets=lambda row: None)


@pytest.mark.parametrize("group", ["frypan", "moka_pot"])
def test_explicit_recipe_is_preserved_on_exactly100_independent_states(group):
    parent, pool, recipe, loader = fixtures(group)
    original = copy.deepcopy((parent, pool, recipe))
    plan = build(parent, pool, recipe, loader)
    assert plan["conditions"] == {"confirm_" + group: recipe["condition"]}
    assert len(plan["cases"]) == len({r["state_sha256"] for r in plan["cases"]}) == 100
    assert len({r["name"] for r in plan["cases"]}) == 100
    assert plan["confirmation_audit"]["tuple_overlap"] == 0
    assert plan["confirmation_audit"]["raw_state_hash_overlap"] == 0
    assert plan["truth_protocol"] == parent["truth_protocol"]
    assert plan["new_training_rows"] == 0 and plan["original90_grasp_diagnostic_v1"] is True
    assert "legacy summarizer" in plan["qualification"]
    assert (parent, pool, recipe) == original


def test_same_raw_state_under_a_different_tuple_is_not_independent():
    parent, pool, recipe, loader = fixtures()
    row = pool["cases"][0]
    row["state_sha256"] = digest("old")
    changed = lambda s, t, i: digest("old") if (s, t, i) == ("libero_90", 0, 10) else loader(s, t, i)
    with pytest.raises(ValueError, match="raw state overlaps discovery"):
        build(parent, pool, recipe, changed)


def test_duplicate_tuple_and_duplicate_raw_state_are_both_rejected():
    parent, pool, recipe, loader = fixtures()
    pool["cases"][1]["episode"] = pool["cases"][0]["episode"].copy()
    pool["cases"][1]["official_init_index"] = 10
    with pytest.raises(ValueError, match="tuple overlaps discovery or repeats"):
        build(parent, pool, recipe, loader)
    parent, pool, recipe, loader = fixtures()
    first_hash = pool["cases"][0]["state_sha256"]
    pool["cases"][1]["state_sha256"] = first_hash
    changed = lambda s, t, i: first_hash if (s, t, i) == ("libero_90", 0, 11) else loader(s, t, i)
    with pytest.raises(ValueError, match="raw state overlaps discovery or repeats"):
        build(parent, pool, recipe, changed)


def test_current_state_must_match_its_reserved_canonical_hash():
    parent, pool, recipe, loader = fixtures()
    changed = lambda s, t, i: digest("changed") if s == "libero_90" else loader(s, t, i)
    with pytest.raises(ValueError, match="confirmation state changed"):
        build(parent, pool, recipe, changed)


@pytest.mark.parametrize("change", [
    {"episode": {"suite": "libero_spatial_swap", "task": 0, "seed": 10}},
    {"official_init_index": 41}, {"state_hash_encoding": "body-origin proxy"},
    {"source": "generated_state"},
])
def test_other_assets_seeds_and_encodings_cannot_enter_confirmation(change):
    parent, pool, recipe, loader = fixtures()
    pool["cases"][0].update(change)
    with pytest.raises(ValueError, match="official original90 init10-39"):
        build(parent, pool, recipe, loader)


def test_missing_reserved_state_is_not_silently_replaced():
    parent, pool, recipe, loader = fixtures()
    pool["cases"].pop()
    with pytest.raises(ValueError, match="exactly100"):
        build(parent, pool, recipe, loader)


@pytest.mark.parametrize("change", [
    {"frozen": False}, {"group": "mug"}, {"condition": {}},
    {"exploration_reports": []}, {"exploration_reports": [{"path": "report", "sha256": "missing"}]},
])
def test_recipe_needs_explicit_freeze_full_condition_and_report_identity(change):
    _, _, recipe, _ = fixtures()
    recipe.update(change)
    with pytest.raises(ValueError):
        prepare.validate_recipe(recipe, "frypan")


def test_pinned_report_is_opaque_and_never_selects_a_winner(monkeypatch, tmp_path):
    parent, pool, recipe, loader = fixtures()
    parent_path, pool_path, recipe_path = [tmp_path / name for name in ("parent.json", "pool.json", "recipe.json")]
    parent_path.write_text(json.dumps(parent))
    pool["source_manifest"] = prepare.file_record(parent_path)
    pool_path.write_text(json.dumps(pool))
    report = tmp_path / "report.bytes"
    report.write_bytes(b"not JSON: no metric parsing permitted\xff")
    recipe["exploration_reports"] = [prepare.file_record(report)]
    recipe_path.write_text(json.dumps(recipe))
    monkeypatch.setattr(prepare, "SOURCE_SHA", prepare.file_record(parent_path)["sha256"])
    monkeypatch.setattr(prepare, "POOL_SHA", prepare.file_record(pool_path)["sha256"])
    monkeypatch.setattr(prepare, "make_official_state_validator", lambda pool: (loader, lambda row: None))
    output = tmp_path / "test_output"
    monkeypatch.setattr(sys, "argv", ["prepare", "--parent", str(parent_path), "--pool", str(pool_path),
        "--group", "frypan", "--recipe", str(recipe_path),
        "--recipe-sha256", prepare.file_record(recipe_path)["sha256"], "--output", str(output)])
    prepare.main()
    plan = json.loads((output / "full.json").read_text())
    assert plan["conditions"]["confirm_frypan"] == recipe["condition"]
    assert plan["exploration_reports"] == recipe["exploration_reports"]


def test_official_validator_checks_file_identity_before_replaying_state(monkeypatch, tmp_path):
    monkeypatch.setenv("LIBERO_TYPE", "standard")
    monkeypatch.setenv("LIBERO_CONFIG_PATH", str(tmp_path / "prior_config"))
    roots = {k: tmp_path / k for k in ("bddl_files", "init_states", "assets")}
    for path in roots.values():
        (path / "libero_90").mkdir(parents=True)
    bddl = roots["bddl_files"] / "libero_90" / "pan.bddl"
    init = roots["init_states"] / "libero_90" / "pan.pruned_init"
    bddl.write_text("original task")
    init.write_bytes(b"official states")
    config = tmp_path / "config.yaml"
    config.write_text("fixed original asset roots")
    official = SimpleNamespace(problem_folder="libero_90", bddl_file="pan.bddl", init_states_file="pan.pruned_init")
    arrays = np.asarray([[float(i), .5] for i in range(50)])
    suite = SimpleNamespace(get_task=lambda task: official, get_task_init_states=lambda task: arrays)
    lib = ModuleType("libero.libero")
    lib.get_libero_path = lambda key: str(roots[key])
    monkeypatch.setitem(sys.modules, "libero", ModuleType("libero"))
    monkeypatch.setitem(sys.modules, "libero.libero", lib)
    utils = ModuleType("rlinf.envs.libero.utils")
    utils.benchmark = SimpleNamespace(__name__="libero.libero.benchmark", get_benchmark=lambda name: lambda: suite)
    monkeypatch.setitem(sys.modules, "rlinf.envs.libero.utils", utils)
    pool = {"config": prepare.file_record(config), "asset_roots": {k: str(v) for k, v in roots.items()},
            "benchmark_python_namespace": "libero.libero.benchmark"}
    loader, verify = prepare.make_official_state_validator(pool)
    row = {"episode": {"suite": "libero_90", "task": 40, "seed": 10},
           "bddl": prepare.file_record(bddl), "init_file": prepare.file_record(init)}
    verify(row)
    assert loader("libero_90", 40, 10) == hashlib.sha256(arrays[10].astype("<f8").tobytes()).hexdigest()
    init.write_bytes(b"asset changed")
    with pytest.raises(ValueError, match="confirmation asset changed"):
        verify(row)
    with pytest.raises(ValueError, match="non-original task"):
        loader("libero_spatial_swap", 0, 10)


def test_recipe_hash_changes_fail_before_building_confirmation(tmp_path):
    path = tmp_path / "recipe.json"
    path.write_text('{"frozen":true}')
    previous = prepare.file_record(path)["sha256"]
    path.write_text('{"frozen":false}')
    with pytest.raises(ValueError, match="registered file changed"):
        prepare.load_pinned_json(path, previous)
