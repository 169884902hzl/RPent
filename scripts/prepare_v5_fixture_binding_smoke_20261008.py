"""Pin the receipt/support fixes for a visited original-task physical smoke."""

import argparse
import json
from pathlib import Path

from prepare_v5_interim574 import ref


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--parent-index", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    source = args.source.resolve(strict=True)
    identity = json.loads((source / "source_snapshot.json").read_text())
    snapshot = {"path": str(source), "commit": identity["commit"],
                "files": identity["files"], "archive": identity["archive"]}
    parent = json.loads(args.parent_index.read_text())
    parent_plans = [json.loads(Path(item["path"]).read_text()) for item in parent["files"]
                    if Path(item["path"]).name.startswith("expert_part")]
    registered = {(e["suite"], e["task"], e["seed"]): e
                  for plan in parent_plans for e in plan["episodes"]}
    # These are already visited development states. The first is the exact
    # background-mask/overlength reproduction; none is independent confirmation.
    requested = [
        ("libero_10", 3, 2), ("libero_10", 3, 0),
        ("libero_10", 4, 0), ("libero_10", 4, 1),
        ("libero_10", 5, 0), ("libero_10", 5, 1),
        ("libero_10", 6, 0), ("libero_10", 6, 1),
        ("libero_goal", 2, 0), ("libero_goal", 2, 1),
        ("libero_goal", 7, 0), ("libero_goal", 7, 1),
        ("libero_object", 4, 0), ("libero_object", 4, 1),
        ("libero_spatial", 7, 0), ("libero_spatial", 7, 1),
    ]
    episodes = [registered[key] for key in requested]
    budget = {**parent_plans[0]["budget"], "fixture_support_footprint_v2": True,
              "fixture_part_visibility_v2": True, "vla_task_diagnostic_v1": False,
              "motion_trace_v1": True}
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    files = []
    for part in range(8):
        plan = {"purpose": "visited original16 support/visibility/token physical development smoke",
                "budget": budget, "behavior_frozen": False, "evaluation_only": True,
                "training_allowed": False, "confirmation": False, "libero_type": "standard",
                "source_path": str(source), "source_commit": identity["commit"],
                "cohort": "expert", "episodes": episodes[part::8]}
        path = output / f"expert_part{part}.json"
        path.write_text(json.dumps(plan, indent=2) + "\n")
        files.append(ref(path))
    index = {"purpose": plan["purpose"], "files": files, "references": [ref(args.parent_index)],
             "source_snapshot": snapshot, "source_path": str(source), "source_commit": identity["commit"],
             "batch_runner": ref(source / "v5_batch_eval.py"),
             "launcher": ref(source / "scripts/run_v5_interim574.sbatch"),
             "runtime_supplement": [ref(source / "typed_choice_eval.py")],
             "planned": {"expert": len(episodes)}, "training_allowed": False, "confirmation": False,
             "renderer_changes": ["receipt_compact/6", "fixture_support_footprint_v2", "fixture_part_visibility_v2"],
             "generator": ref(__file__)}
    (output / "manifest.json").write_text(json.dumps(index, indent=2) + "\n")
    print(json.dumps(ref(output / "manifest.json")))


if __name__ == "__main__":
    main()
