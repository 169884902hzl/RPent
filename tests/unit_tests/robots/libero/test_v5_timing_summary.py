"""Native success must not be grouped with unsuccessful timing samples."""

import hashlib
import json
import sys

from scripts.summarize_v5_timing40_20261001 import main


def test_persistence_native_success_without_finish_has_success_latency(tmp_path, monkeypatch):
    cohort = tmp_path / "cohort.json"
    episodes = [{"suite": "libero_object_swap", "task": i, "seed": 40 + j}
                for i in range(10) for j in range(4)]
    cohort.write_text(json.dumps({"episodes": episodes}))
    results = tmp_path / "result"
    root = results / "episodes"
    episode = episodes[0]
    directory = root / "libero_object_swap_t0_s40"
    directory.mkdir(parents=True)
    (directory / "choices.jsonl").write_text(json.dumps({
        "selected": "place(e1,e2,in)",
        "timing_s": {"model_inference": .12, "http_round_trip": .2, "total": 2.},
    }) + "\n")
    (root / "episodes.jsonl").write_text(json.dumps({
        "episode": episode, "output_dir": str(directory),
        "result": {"official_success": True, "correct_finish": False,
                   "termination_category": "success", "wall_s": 4.},
    }) + "\n")
    monkeypatch.setattr(sys, "argv", ["summary", "--manifest", str(cohort), "--results", str(results)])
    main()
    report = json.loads((results / "timing_summary.json").read_text())
    assert report["complete"] is False
    assert report["official_success"] == 1
    assert report["explicit_successful_finish"] == 0
    assert report["episode_wall"]["success"]["n"] == 1
    assert "failure" not in report["episode_wall"]
    assert report["step_timing"]["success/model_inference"]["median_s"] == .12
    assert report["ledger_sha256"] == hashlib.sha256((root / "episodes.jsonl").read_bytes()).hexdigest()
