"""Pin a deterministic 20-state original drawer depth-window development test."""

import argparse
import copy
import hashlib
import json
from collections import Counter
from pathlib import Path


def ref(path):
    path = Path(path).resolve(strict=True)
    return {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--parent", type=Path, required=True)
    parser.add_argument("--parent-sha", required=True)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--source-archive", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not all(p.is_absolute() for p in (args.parent, args.source, args.source_archive, args.output)):
        parser.error("all registered paths must be absolute")
    parent_ref = ref(args.parent)
    if parent_ref["sha256"] != args.parent_sha:
        raise ValueError("registered original selection parent changed")
    parent = json.loads(args.parent.read_text())
    if (parent["cohort"] != "selection" or parent["qualification_authorized"] is not False
            or parent["new_training_rows"] != 0 or len(parent["cases"]) != 200):
        raise ValueError("expected the preserved 200-state original selection")
    selected = []
    for kind in ("drawer_open", "drawer_close"):
        ordered = [c for c in parent["cases"] if c["type"] == kind]
        if len(ordered) != 100:
            raise ValueError("expected 100 registered states per type")
        # This rule depends only on the parent ordering, never an outcome.
        selected.extend(ordered[::10])
    source_identity = copy.deepcopy(parent["source_snapshot"])
    source_identity.update(path=str(args.source), commit=args.source_commit,
                           archive=ref(args.source_archive))
    for item in source_identity["files"]:
        item.update(ref(args.source / item["relative_path"]))
    method = "native_depth_v5_160"
    condition = copy.deepcopy(parent["conditions"]["native_original160"])
    condition["overrides"]["drawer_bounds_depth_v5"] = True
    condition["overrides"]["drawer_current_binding_v4"] = True
    cases = []
    for case in selected:
        new = copy.deepcopy(case)
        new.update(name=case["name"].replace("drawer559_", "drawer565_")
                   .replace("native_original160", method), condition=method,
                   parent_case_name=case["name"])
        cases.append(new)
    plan = copy.deepcopy(parent)
    for key in ("native_recipe_reference", "parent_manifest"):
        plan.pop(key, None)
    plan.update(version="drawer565-public-depth-smoke/1", cases=cases, cases_count=20,
                purpose="Physical metrology test of measured cabinet depth search; no qualification",
                source_snapshot=source_identity, parent_manifest=parent_ref,
                conditions={method: condition}, producer=ref(__file__),
                producer_dependencies=[parent_ref],
                selection="Every tenth registered case within each type, preserving original ordering",
                state_repetition="20 already visited original selection states; never confirmation",
                metrics={**parent["metrics"], "new_public_geometry": "Measured parent-depth search only"},
                diagnostic_factors={"only_change": "drawer_bounds_depth_v5=true",
                                    "unchanged": "prompt, reset,160 complete chunks,setup and scoring"},
                preregistered_requests_by_type_arm={f"{kind}/{method}": 10
                    for kind in ("drawer_open", "drawer_close")},
                qualification_authorized=False, new_training_rows=0,
                new_physical_trials=0, run_status="CPU_prepared_not_submitted")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x") as handle:
        handle.write(json.dumps(plan, indent=2) + "\n")
    print(json.dumps({"manifest": ref(args.output), "source": source_identity,
                      "by_type": dict(Counter(c["type"] for c in cases)), "new_gpu_jobs": 0}))


if __name__ == "__main__":
    main()
