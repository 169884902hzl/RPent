"""Join declared reserves in order without reading any policy outcome."""

from collections import Counter
import copy
import hashlib
import json
from pathlib import Path

ROOT = Path("/public/home/sunyihan/rpent_libero_eval")
BASE = ROOT / "results/harness_v5/perturb_skill_materialization_20261009_r2"


def ref(path):
    return {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    for cell, revision, inputs in (
        ("vla_subtask_cup", "r3", ["selection_vla_subtask_cup_combined.json",
                                   "selection_reserve2_vla_subtask_cup/manifest.json"]),
        ("vla_subtask_box", "r4", ["selection_vla_subtask_box_combined_r3.json",
                                   "selection_reserve3_vla_subtask_box/manifest.json"]),
        ("place_in", "r3", ["selection_place_in_combined.json",
                            "selection_reserve2_place_in/manifest.json"]),
    ):
        output = BASE / f"selection_{cell}_combined_{revision}.json"
        if output.exists():
            print(json.dumps({"cell": cell, "status": "already_combined", **ref(output)}))
            continue
        paths = [BASE / item for item in inputs]
        parents = [json.loads(path.read_text()) for path in paths]
        rows, seen, names = [], set(), set()
        duplicates = 0
        for parent in parents:
            if parent.get("policy_outcomes_read") or parent.get("PRO_files_read"):
                raise ValueError("geometry admission must precede policy outcomes")
            for original in parent["rows"]:
                row = copy.deepcopy(original)
                if row["name"] in names:
                    raise ValueError("duplicate declaration name")
                names.add(row["name"])
                if row["permanent_training_exclusion"]:
                    raise ValueError("confirmation state in selection pool")
                if row["status"] == "prepared":
                    identity = row["state_sha256"]
                    if identity in seen:
                        duplicates += 1
                        row.update(status="invalid_layout", invalid_reasons=[
                            *row.get("invalid_reasons", []), "duplicate_raw_state_across_reserves"])
                    else:
                        seen.add(identity)
                rows.append(row)
        payload = {"parents": [ref(path) for path in paths], "rows": rows,
                   "counts": dict(Counter(row["status"] for row in rows)),
                   "declared": len(rows), "cross_reserve_duplicates": duplicates,
                   "admission": "parent declarations then reserves; first100 unique geometrically valid; no policy outcomes",
                   "policy_outcomes_read": False, "PRO_files_read": False,
                   "invalid_states_retained": True, "skill_executions": 0,
                   "training_allowed": False, "generator": ref(Path(__file__))}
        with output.open("x") as stream:
            stream.write(json.dumps(payload, indent=2) + "\n")
        print(json.dumps({"cell": cell, "counts": payload["counts"],
                          "cross_reserve_duplicates": duplicates, **ref(output)}))


if __name__ == "__main__":
    main()
