"""Audit every standard90 BDDL object and fixture category for pan presence."""

import hashlib
import json
import os
import sys
from collections import Counter
from pathlib import Path


ROOT = Path(sys.argv[1])
OUT = Path(sys.argv[2])
os.environ["LIBERO_TYPE"] = "standard"
os.environ["LIBERO_CONFIG_PATH"] = str(ROOT / "runtime_config")
from libero.libero.envs.bddl_utils import robosuite_parse_problem
from rlinf.envs.libero.utils import benchmark


pool = json.loads((OUT / "report.json").read_text())
bddl_root = Path(pool["task_sources"][0]["bddl"]["path"]).parent
suite = benchmark.get_benchmark("libero_90")()
object_types, fixture_types, records = Counter(), Counter(), []
for index in range(90):
    task = suite.get_task(index)
    assert task.problem_folder == "libero_90"
    bddl = bddl_root / task.bddl_file
    problem = robosuite_parse_problem(str(bddl))
    objects, fixtures = problem["objects"], problem["fixtures"]
    object_types.update(objects.keys())
    fixture_types.update(fixtures.keys())
    names = [name for category, instances in {**objects, **fixtures}.items()
             for name in [category, *instances] if "pan" in name.lower() or "frying" in name.lower()]
    records.append({"task": index, "task_name": task.name,
                    "bddl": {"path": str(bddl), "sha256": hashlib.sha256(bddl.read_bytes()).hexdigest()},
                    "objects": objects, "fixtures": fixtures, "pan_matching_names": names,
                    "pan_present_by_objects_or_fixtures": bool(names)})
pan_tasks = [r["task"] for r in records if r["pan_present_by_objects_or_fixtures"]]
assert pan_tasks == [r["task"] for r in pool["task_sources"]]
report = {"scope": "All 90 standard LIBERO90 original BDDL objects and fixtures; goal is never a pan-presence filter",
          "producer_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
          "original90_tasks_scanned": len(records), "pan_presence_task_ids": pan_tasks,
          "object_category_counts": dict(object_types), "fixture_category_counts": dict(fixture_types),
          "other_pan_category_aliases_found": [k for k in object_types if "pan" in k.lower() and k != "chefmate_8_frypan"],
          "pan_goal_task_ids": [18, 21, 40, 41, 42, 45], "off_target_pan_presence_task_ids": [19, 20, 43, 44],
          "asset_scope": "Declared original manipulable objects and fixtures; decorative visual meshes are not additional task-object instances",
          "tasks": records, "PRO_assets_read": False, "new_physics": 0, "new_model_calls": 0,
          "confirmation100_registered": False, "qualification_authorized": False}
(OUT / "all90_object_presence_report.json").write_text(json.dumps(report, indent=2) + "\n")
print(json.dumps({k: report[k] for k in ("original90_tasks_scanned", "pan_presence_task_ids", "other_pan_category_aliases_found", "object_category_counts", "fixture_category_counts")}))
