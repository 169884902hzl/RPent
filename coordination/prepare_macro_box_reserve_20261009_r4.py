"""Declare the remaining geometric box reserves before policy evaluation."""

import copy
import hashlib
import json
from pathlib import Path
import random


ROOT = Path("/public/home/sunyihan/rpent_libero_eval")


def ref(path):
    return {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    parent = ROOT / "results/harness_v5/perturb_skill_pool_reserves_20261009_r3/manifest.json"
    if ref(parent)["sha256"] != "86ae1d5b44bd530996481e355308027644ef24a65495ced4cb272ab132960940":
        raise ValueError("parent declaration changed")
    index = json.loads(parent.read_text())
    output = ROOT / "results/harness_v5/perturb_macro_box_reserves_20261009_r4"
    output.mkdir(exist_ok=False)
    pools = []
    for split, first in (("selection", 9703000), ("confirmation", 9803000)):
        previous = next(item for item in index["pools"] if Path(item["path"]).stem == split)
        old = json.loads(Path(previous["path"]).read_text())
        if ref(Path(previous["path"]))["sha256"] != previous["sha256"]:
            raise ValueError("parent pool changed")
        template = next(row for row in old["records"]
                        if row["rule"]["skill"] == "vla_subtask" and row["rule"]["category"] == "box")
        records = []
        for i in range(200):
            seed = first + i
            rng = random.Random(seed)
            row = copy.deepcopy(template)
            rule = row["rule"]
            rule.update(layout_seed=seed, xy_translation_m=[rng.uniform(-.10, .10), rng.uniform(-.10, .10)],
                        world_yaw_delta_deg=rng.uniform(-45., 45.),
                        layout="swap_two_free_objects" if i % 2 else "translate_free_object",
                        goal_rule="rotate_eligible_on_in_target" if i % 3 == 0 else "retain_original_goal")
            row.update(name=f"{split}_reserve3_vla_subtask_box_{seed}",
                       rule_sha256=hashlib.sha256(json.dumps(rule, sort_keys=True, separators=(",", ":"),
                                                            allow_nan=False).encode()).hexdigest(),
                       status="preregistered_not_materialized")
            records.append(row)
        payload = {**old, "records": records, "cells": [{"skill": "vla_subtask", "category": "box", "planned": 200}],
                   "parent_pool": previous, "skill_trials_before_declaration": 0,
                   "admission": "parent declarations then reserves1,2,3; first100 unique geometrically valid; no policy outcomes"}
        path = output / f"{split}.json"
        path.write_text(json.dumps(payload, indent=2) + "\n")
        pools.append(ref(path))
    manifest = output / "manifest.json"
    manifest.write_text(json.dumps({"parent": ref(parent), "pools": pools, "generator": ref(Path(__file__)),
                                   "reason": "selection has only80 prepared after400 declared layouts; no policy result used",
                                   "selection_seed_range": [9703000, 9703199],
                                   "confirmation_seed_range": [9803000, 9803199],
                                   "confirmation_permanently_excluded_from_training": True,
                                   "policy_outcomes_read": False, "PRO_files_read": False}, indent=2) + "\n")
    print(json.dumps({"manifest": ref(manifest), "pools": pools}))


if __name__ == "__main__":
    main()
