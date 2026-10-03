"""An original expert replay retains its card provenance and seed isolation."""

import hashlib
import json
import sys

from scripts.build_v5_category_cards118_20261002 import main


def test_successful_original_training_replay_is_not_silently_skipped(tmp_path, monkeypatch):
    def sha(path):
        return hashlib.sha256(path.read_bytes()).hexdigest()

    episode = tmp_path / "episode"
    episode.mkdir()
    trace = episode / "choices.jsonl"
    trace.write_text(json.dumps({
        "selected": "grasp(e1,direct)", "receipt": {"grasp_verified": True, "verification": "verified"},
        "measurements": [{"id": "e1", "name": "bowl"}],
    }) + "\n")
    config = episode / "config.json"
    config.write_text("{}")
    bddl = tmp_path / "original.bddl"
    bddl.write_text("(:objects bowl_1 - bowl) (:fixtures table_1 - table) (:regions (target))")
    episodes = tmp_path / "episodes.json"
    episodes.write_text(json.dumps([{
        "output": str(episode), "identity": ["libero_spatial", 0, 12, "replay:measured_recovery"],
        "result": {"correct_finish": True, "provider": "oracle", "suite": "libero_spatial", "task": 0, "seed": 12},
    }]))
    registry = tmp_path / "registry.json"
    registry.write_text(json.dumps({
        "tasks": {"libero_spatial/0": {"bddl_path": str(bddl), "bddl_sha256": sha(bddl)}},
        "source_episodes": str(episodes), "source_episodes_sha256": sha(episodes),
        "episodes": [{"runtime_config_path": str(config), "runtime_config_sha256": sha(config)}],
    }))
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({
        "original_target_registry": {"path": str(registry), "sha256": sha(registry)},
        "runtime_logs": [{"path": str(trace), "sha256": sha(trace)}],
    }))
    output = tmp_path / "cards"
    monkeypatch.setattr(sys, "argv", ["cards", "--manifest", str(manifest), "--output", str(output)])
    main()
    report = json.loads((output / "manifest.json").read_text())
    assert len(report["files"]) == 1
    assert report["missing_tasks"] == []
    card = json.loads((output / "libero_spatial_t0.json").read_text())
    assert card["steps"] == [{"skill": "grasp", "object_category": "bowl", "mode": "direct"}, {"skill": "finish"}]
    assert card["source_episode"]["seed"] == 12
    assert report["RPent_cards_in_training"] is False
