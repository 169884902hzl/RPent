"""Exercise offline candidate controls through the actual rerender entry point."""

from dataclasses import asdict
import hashlib
import json
import sys
from types import SimpleNamespace

import pytest

from robots.libero.v5_state import Entity, serialize
from scripts.rerender_v5_format118_20261002 import main
import shared_v5r_schema as shared


@pytest.mark.parametrize("scenario", ["grasp_error", "finish_rejected"])
@pytest.mark.parametrize("cooldown", [False, True])
def test_rerender_matches_live_error_and_card_controls(tmp_path, monkeypatch, scenario, cooldown):
    def write(name, value, jsonl=False):
        path = tmp_path / name
        text = "".join(json.dumps(row) + "\n" for row in value) if jsonl else json.dumps(value)
        path.write_text(text)
        return {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "rows": len(value) if jsonl else 1}

    bowl = Entity("e1", "bowl", (0., 0., .1), (-.02, -.02, .08), (.02, .02, .12))
    context = serialize("pick up the bowl", [bowl], .08, None, [])
    criteria = {"C0": "ask_help()"}
    request = {"state": context, "questions": {"action": {
        "type": "choice", "instructions": "choose a skill", "criteria": criteria}}}
    events = []
    if scenario == "grasp_error":
        receipts = [{"tool": "grasp", "object": "e1", "mode": "direct",
                     "verification": "execution_error", "error": "unreachable measured approach"}]
        receipts += [{"tool": "retreat", "executed": True} for _ in range(4)]
        selected = ["grasp(e1,direct)"] + ["retreat()"] * 4
        indices = range(1, 5)
        steps = [{"skill": "grasp", "object_category": "bowl", "mode": "direct"}]
    else:
        receipts = [{"tool": "finish", "executed": False,
                     "verification": "environment_incomplete"} for _ in range(2)]
        receipts += [{"tool": "retreat", "executed": True}]
        selected = ["finish()", "finish()", "retreat()"]
        indices = [2]
        steps = [{"skill": "finish"}]
    for choice, receipt in zip(selected, receipts):
        events.append({"request": {"context": context}, "post_request": {"context": context},
                       "measurements": [asdict(bowl)], "post_measurements": [asdict(bowl)],
                       "robot_measurement": {"eef_xyz": [0., 0., .3]},
                       "candidates": list(criteria.values()), "selected": choice, "receipt": receipt})
    trace = write("choices.jsonl", events, jsonl=True)
    sources, rows = [], []
    for index in indices:
        sources.append({"request": request, "stage": "skill", "step": index,
                        "source_file": trace["path"], "source_line": index + 1})
        rows.append({"schema_version": "entities-plan-receipt/3.1", "domain": "libero",
                     "question_type": "next_skill", "judge": "physics_branch", "split": "train",
                     "scene_id": "original/libero_spatial/t0/init10", "suite": "libero_spatial",
                     "task_id": 0, "init_state_index": 10, "stage": "skill", "step": index,
                     "request": request, "base_request_sha256": shared.digest(request),
                     "acceptable_actions": ["C0"], "evaluated_actions": ["C0"],
                     "unknown_actions": [], "label_evidence": {"test_only": True}})
    episodes = write("episodes.json", [])
    registry = write("registry.json", {"source_episodes": episodes["path"],
                     "source_episodes_sha256": episodes["sha256"]})
    manifest = write("input.json", {"source_files": [write("sources.jsonl", sources, True)],
                     "files": [write("train.jsonl", rows, True)], "validation_files": [],
                     "runtime_logs": [trace], "original_target_registry": registry})
    cards = []
    for task, card_steps in [(0, steps), (1, [{"skill": "retreat"}])]:
        card = write(f"card{task}.json", {"steps": card_steps})
        cards.append({**card, "task": f"libero_spatial/{task}", "original_scene_sha256": "same-scene"})
    card_manifest = write("cards.json", {"origin": "original_oracle",
                          "RPent_cards_in_training": False, "files": cards})
    monkeypatch.setitem(sys.modules, "transformers", SimpleNamespace(
        AutoTokenizer=SimpleNamespace(from_pretrained=lambda *args, **kwargs: object())))
    monkeypatch.setitem(sys.modules, "parallel_schema", SimpleNamespace(
        prepare_prompts=lambda *args: SimpleNamespace(full_ids=[[1] * 8])))
    output = tmp_path / "rendered"
    argv = ["rerender", "--manifest", manifest["path"], "--cards", card_manifest["path"],
            "--choice-package", str(tmp_path), "--output", str(output), "--stagnation-recovery"]
    if cooldown:
        argv.append("--execution-error-cooldown")
    monkeypatch.setattr(sys, "argv", argv)
    main()
    rendered = [json.loads(line) for line in (output / "train.jsonl").read_text().splitlines()]
    correct = [row for row in rendered if row["memory_variant"] == "correct"]
    assert len(correct) == len(indices)
    for row in correct:
        options = set(row["request"]["questions"]["action"]["criteria"].values())
        assert "ask_help()" in options
        if scenario == "grasp_error":
            blocked = cooldown and row["step"] <= 3
            assert ("grasp(e1,direct)" in options) is not blocked
            assert ("card_next()" in options) is not blocked
            assert "grasp(e1,above_10cm)" in options
        else:
            assert "finish()" not in options
            assert "card_next()" not in options
    report = json.loads((output / "manifest.json").read_text())
    assert report["execution_error_cooldown"] is cooldown
    assert report["full_training_admission"] is False
