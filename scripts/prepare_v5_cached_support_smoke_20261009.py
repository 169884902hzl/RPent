"""Probe the existing measured-support filter on visited original failures."""

import argparse
import json
from pathlib import Path

from prepare_expert_remote_resume_20261008 import packet, read_pinned, ref


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--parent-index", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    parent = args.parent_index.resolve(strict=True)
    index = json.loads(parent.read_text())
    plans = [read_pinned(item) for item in index["files"]
             if Path(item["path"]).name.startswith("expert_part")]
    source = index["source_snapshot"]
    for item in [*source["files"], source["archive"]]:
        if ref(Path(item["path"])) != {"path": item["path"], "sha256": item["sha256"]}:
            raise ValueError("Source identity changed: " + item["path"])
    identities = {(e["suite"], e["task"], e["seed"]): e
                  for plan in plans for e in plan["episodes"]}
    # Each is a previously visited development state, never confirmation.
    requested = [("libero_10", 2, 0), ("libero_10", 8, 2),
                 ("libero_object", 4, 3), ("libero_10", 2, 1)]
    episodes = [identities[key] for key in requested]
    template = {**plans[0], "purpose": "visited original support/part-visibility development smoke",
                "budget": {**plans[0]["budget"], "fixture_support_footprint_v2": True,
                           "fixture_part_visibility_v2": True, "motion_trace_v1": True},
                "confirmation": False, "training_allowed": False, "behavior_frozen": False}
    result = packet(args.output.resolve(), episodes, template, index, source,
                    [ref(parent), ref(Path(__file__))], 4,
                    {"preserved_unique_physical_identities": 0,
                     "policy": "new development diagnosis; preserve4780 and earlier failures",
                     "confirmation": False, "training_allowed": False,
                     "only_behavior_changes": ["fixture_support_footprint_v2", "fixture_part_visibility_v2"]})
    print(json.dumps(result))


if __name__ == "__main__":
    main()
