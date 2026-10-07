"""Prepare explicitly indexed interim cohorts; do not read result directories."""
import argparse
import hashlib
import json
from pathlib import Path


def ref(path):
    path = Path(path).resolve(strict=True)
    return {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--original-manifest", type=Path, required=True)
    args = parser.parse_args()
    root = args.root.resolve(strict=True)
    prep = args.output.resolve()
    prep.mkdir(parents=True, exist_ok=True)
    if (prep / "manifest.json").exists():
        raise FileExistsError("registered preparation already exists")
    smoke = root / "results/harness_v5/runtime544_smoke20_20261006/preparation/original_part0.json"
    place = root / "results/harness_v5/place_observe_retreat_v9_CPU_20261006/preparation/registered/observe_retreat_v9_same40_category_selection.json"
    pan = root / "results/harness_v5/pan562_runtime_smoke10_CPU_20261006/preparation/pan562_runtime_direct_same10_selection.json"
    old = root / "results/harness_v5/placement442_model_regressions_20261004/preparation/A3-N/old40.json"
    new = root / "results/harness_v5/placement442_model_regressions_20261004/preparation/A3-N/new41.json"
    gate = args.original_manifest.resolve(strict=True)
    source_plan = root / "results/harness_v5/microwave571_public_parent_CPU_20261006/preparation/registered/microwave_public_parent_original10.json"
    source_identity = json.loads(source_plan.read_text())["source_snapshot"]
    budget = json.loads(smoke.read_text())["budget"]
    budget.update(json.loads(place.read_text())["conditions"]["vla_subtask160"]["overrides"])
    budget.update(json.loads(pan.read_text())["conditions"]["pan_runtime_direct_development"]["overrides"])
    budget.update(max_chunks=160, max_decisions=100, max_episode_steps=10000,
                  prompt_limit=3072, drawer_current_binding_v4=True,
                  drawer_bounds_depth_v5=True, drawer_frontmost_panel_v7=True,
                  drawer_contact_clearance_v8=True, drawer_public_stop_v6=False,
                  success_prediction_diagnostic=True)
    # Do not enable the demonstrably ambiguous single-frame drawer stop.
    # No temporal verifier is qualified yet. These runs are interim only.
    base = {"purpose": "interim574 current integrated configuration; not freeze evidence",
            "budget": budget, "behavior_frozen": False, "evaluation_only": True,
            "training_allowed": False, "source_path": str(root / "source_v5_drawer571_20261006"),
            "source_commit": "5da67d19fe8dde8564e06c39266bb1fedc330d2a",
            "model_revision": "b226f57a8f7ba32b5e58453182cfe47e0434812a8edbea6b003d9bad36ce4bcb",
            "references": [ref(p) for p in (smoke, place, pan, old, new, gate)],
            "not_enabled": ["unqualified_temporal_verifier", "single_frame_drawer_stop_v6", "memory"]}
    cohorts = {"A3-N": ("pro", json.loads(old.read_text())["episodes"] + json.loads(new.read_text())["episodes"]),
               "expert": ("standard", json.loads(gate.read_text())["episodes"])}
    files = []
    for cohort, (kind, episodes) in cohorts.items():
        assert len(episodes) == (80 if cohort == "A3-N" else 200)
        assert len({(e["suite"], e["task"], e["seed"]) for e in episodes}) == len(episodes)
        for part in range(8):
            plan = {**base, "libero_type": kind, "episodes": episodes[part::8], "cohort": cohort}
            if cohort == "expert":
                plan["budget"] = {**budget, "success_prediction_diagnostic": False,
                                  "native_termination_diagnostic": True}
            path = prep / f"{cohort}_part{part}.json"
            path.write_text(json.dumps(plan, indent=2) + "\n")
            files.append(ref(path))
    index = {"purpose": base["purpose"], "files": files, "source_path": base["source_path"],
             "source_commit": base["source_commit"], "planned": {"A3-N": 80, "expert": 200},
             "references": base["references"], "baseline_totals": {"A3-N": [46, 80], "expert": [177, 200]},
             "source_snapshot": source_identity,
             "batch_runner": ref(prep / "v5_batch_eval.py"),
             "allocation": "eight 1-GPU shards per cohort; skill jobs have priority; no node binding"}
    (prep / "manifest.json").write_text(json.dumps(index, indent=2) + "\n")


if __name__ == "__main__":
    main()
