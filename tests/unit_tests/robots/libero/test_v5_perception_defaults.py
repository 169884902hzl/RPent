"""Missing legacy budget keys must not disable required query and wrist recall."""

import json
import sys

import pytest

import harness_v5_eval
from scripts import prepare_v5_skill536_runtime_smoke


@pytest.mark.parametrize("disabled", [False, True])
def test_real_cli_defaults_and_explicit_development_controls(monkeypatch, tmp_path, disabled):
    recorded = []
    argv = ["harness_v5_eval", "--choice-package", str(tmp_path), "--output-dir", str(tmp_path / "out")]
    if disabled:
        argv += ["--no-instruction-queries-v1", "--no-wrist-recall-v1"]
    monkeypatch.setattr(sys, "argv", argv)
    monkeypatch.setattr(harness_v5_eval, "run_episode", recorded.append)
    harness_v5_eval.main()
    assert len(recorded) == 1
    assert recorded[0].instruction_queries_v1 is not disabled
    assert recorded[0].wrist_recall_v1 is not disabled


def test_smoke_explicitly_pins_recall_even_with_an_old_budget(monkeypatch, tmp_path):
    baseline = tmp_path / "legacy.json"
    baseline.write_text(json.dumps({"budget": {"max_decisions": 80}}))
    output = tmp_path / "smoke"
    monkeypatch.setattr(sys, "argv", ["prepare", "--baseline", str(baseline), "--output", str(output)])
    prepare_v5_skill536_runtime_smoke.main()
    manifest = json.loads((output / "manifest.json").read_text())
    episodes = 0
    for ref in manifest["files"]:
        from pathlib import Path

        plan = json.loads(Path(ref["path"]).read_text())
        assert plan["budget"]["instruction_queries_v1"] is True
        assert plan["budget"]["wrist_recall_v1"] is True
        assert plan["budget"]["dual_view_fusion_v1"] is True
        episodes += len(plan["episodes"])
    assert episodes == 20
