"""Declare geometry-only reserve layouts before any perturbed policy trial."""

import argparse
import copy
import json
from pathlib import Path
import random

from prepare_expert_remote_resume_20261008 import dump, ref
from prepare_v5_perturb_skill_pools_20261009 import CELLS, sha


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--parent", type=Path, required=True)
    parser.add_argument("--parent-sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if ref(args.parent)["sha256"] != args.parent_sha256:
        raise ValueError("parent preregistration changed")
    parent = json.loads(args.parent.read_text())
    args.output.mkdir(parents=True, exist_ok=False)
    outputs = []
    for split, first in (("selection", 9303000), ("confirmation", 9403000)):
        prior_ref = next(r for r in parent["pools"] if Path(r["path"]).stem == split)
        if ref(Path(prior_ref["path"]))["sha256"] != prior_ref["sha256"]:
            raise ValueError("parent pool changed")
        original = json.loads(Path(prior_ref["path"]).read_text())
        records = []
        for cell, (skill, category) in enumerate(CELLS):
            template = next(r for r in original["records"]
                            if r["rule"]["skill"] == skill and r["rule"]["category"] == category)
            for index in range(100):
                seed = first + cell * 1000 + index
                rng = random.Random(seed)
                record = copy.deepcopy(template)
                rule = record["rule"]
                rule.update(layout_seed=seed,
                            xy_translation_m=[rng.uniform(-.10,.10),rng.uniform(-.10,.10)],
                            world_yaw_delta_deg=rng.uniform(-45.,45.),
                            layout="swap_two_free_objects" if index % 2 else "translate_free_object",
                            goal_rule="rotate_eligible_on_in_target" if skill in ("vla_subtask","place")
                                      and index % 3 == 0 else "retain_original_goal")
                record.update(name=f"{split}_reserve_{skill}_{category.replace(' ','_')}_{seed}",
                              rule_sha256=sha(rule), status="preregistered_not_materialized")
                records.append(record)
        payload = {**original, "records": records, "parent_pool": prior_ref,
                   "reserve_rules_per_cell": 100,
                   "admission": "first100 geometrically valid states per cell, parent declarations then reserves in declared order; never policy outcomes",
                   "geometry_rejection": ["penetration_over3mm","object_fell_outside_table",
                                          "nonfinite","reset_mismatch","duplicate_or_cross_split_state"],
                   "transform_interpretation": "swap XY if declared; apply declared XY translation and world yaw to primary moved object; fixed30 neutral settling",
                   "skill_trials_before_declaration": 0}
        outputs.append(dump(args.output / (split + ".json"), payload))
    result = dump(args.output / "manifest.json", {"parent": ref(args.parent), "pools": outputs,
                  "generator": ref(Path(__file__)), "planned_reserves_per_split": len(CELLS)*100,
                  "permanent_confirmation_training_exclusion": True,
                  "outcomes_read": False, "skill_trials": 0,
                  "not_an_outcome_based_confirmation_retry": True})
    print(json.dumps(result))


if __name__ == "__main__":
    main()
