"""Prepare explicit 10 original and 10 PRO development smoke episodes on CPU."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    baseline = args.baseline.resolve(strict=True)
    plan = json.loads(baseline.read_text())
    budget = dict(plan["budget"])
    # The registered persistence budget is unchanged. These are the current
    # default runtime features, explicitly pinned rather than inferred later.
    budget.update(dual_view_fusion_v1=True, measured_action_receipts_v1=True,
                  measurement_progress_blocking_v1=True, vla_subtask_v1=True,
                  stove_rgbd_verification_v1=True, candidate_failure_counts_v1=True)
    dev_suites = ("libero_spatial_task", "libero_spatial_swap", "libero_object_task",
                  "libero_object_swap", "libero_goal_task", "libero_goal_swap",
                  "libero_10_task", "libero_10_swap")
    original_suites = ("libero_spatial", "libero_object", "libero_goal", "libero_10")
    cohorts = {
        "development": [{"suite": s, "task": 0, "seed": 41} for s in dev_suites]
                       + [{"suite": "libero_spatial_swap", "task": 1, "seed": 41},
                          {"suite": "libero_object_swap", "task": 1, "seed": 41}],
        "original": [{"suite": s, "task": t, "seed": 0}
                     for t in range(2) for s in original_suites]
                    + [{"suite": "libero_spatial", "task": 2, "seed": 0},
                       {"suite": "libero_goal", "task": 2, "seed": 0}],
    }
    args.output.mkdir(parents=True, exist_ok=False)
    files = []
    for cohort, episodes in cohorts.items():
        for shard in range(8):
            path = args.output / f"{cohort}_part{shard}.json"
            item = {
                "purpose": "20-episode current-runtime development smoke; not qualification",
                "libero_type": "standard" if cohort == "original" else "pro",
                "episodes": episodes[shard::8], "budget": budget,
                "evaluation_only": True, "training_allowed": False,
                "baseline": {"path": str(baseline),
                             "sha256": hashlib.sha256(baseline.read_bytes()).hexdigest()},
                "model_revision": "b226f57a8f7ba32b5e58453182cfe47e0434812a8edbea6b003d9bad36ce4bcb",
                "behavior_frozen": False,
            }
            path.write_text(json.dumps(item, indent=2) + "\n")
            files.append({"path": str(path.resolve()),
                          "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                          "cohort": cohort, "part": shard, "episodes": len(item["episodes"])})
    (args.output / "manifest.json").write_text(json.dumps({
        "purpose": "explicit smoke inputs; never read artifacts by glob",
        "total": 20, "original": 10, "development": 10, "files": files,
        "checks": ["fusion and source cameras", "no_effect and blocked actions",
                   "maximum identical-action repetition <=5", "vla_subtask availability and execution",
                   "measured receipt changes"],
    }, indent=2) + "\n")


if __name__ == "__main__":
    main()
