"""Check the requested original grasp comparison before development regressions."""

import argparse
import json
from pathlib import Path

from scripts.summarize_v5_first_grasp import read_group


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--primary", type=Path, required=True)
    parser.add_argument("--supplement", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = {}
    for mode in range(3):
        arms = {}
        for arm in ("before", "after"):
            groups = [read_group(root / f"mode{mode}" / arm)
                      for root in (args.primary, args.supplement)]
            valid = sum(g["valid_first_grasps"] for g in groups)
            verified = sum(g["counts"]["grasp_verified"] for g in groups)
            arms[arm] = {"valid_first_grasps": valid, "grasp_verified": verified,
                         "rate": verified / valid if valid else None,
                         "groups": groups}
        report[str(mode)] = arms
    enough = all(a["valid_first_grasps"] >= 50 for m in report.values() for a in m.values())
    unchanged_or_improved = all(m["after"]["rate"] is not None and m["before"]["rate"] is not None
                               and m["after"]["rate"] >= m["before"]["rate"] for m in report.values())
    args.output.write_text(json.dumps({"modes": report, "at_least_50_each": enough,
                                      "original_grasp_success_not_lower": unchanged_or_improved,
                                      "scope": "Original first-grasp validation; not a harness freeze or full-task gate"}, indent=2) + "\n")
    if not enough or not unchanged_or_improved:
        raise RuntimeError("original motion comparison needs repair or additional attempted grasps; preserved report has counts")


if __name__ == "__main__":
    main()
