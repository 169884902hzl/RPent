"""Materialize preregistered confirmation geometry, without executing skills."""

import argparse
from collections import Counter
import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess

ROOT = Path("/public/home/sunyihan/rpent_libero_eval")
ADAPTER = ROOT / "coordination/perturb_skill_adapter_20261009_r1"
SOURCE = ROOT / "source_v5_skill_budget_20261009_r2"
SELECTION = ROOT / "results/harness_v5/perturb_skill_selection_20261009_r1"
OUTPUT = ROOT / "results/harness_v5/perturb_skill_confirmation_geometry_20261009_r1"


def ref(path):
    return {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("cells", nargs="+")
    args = parser.parse_args()
    environment = {**os.environ, "LIBERO_TYPE": "standard",
                   "LIBERO_CONFIG_PATH": str(ROOT / "runtime_config"),
                   "PYTHONPATH": f"{ADAPTER}:{SOURCE}:{SOURCE / 'scripts'}",
                   "OPENBLAS_NUM_THREADS": "1", "OMP_NUM_THREADS": "1"}
    OUTPUT.mkdir(parents=True, exist_ok=True)
    exclusions = []
    for path in sorted(SELECTION.glob("*/preparation/selection.json")):
        plan = json.loads(path.read_text())
        materialized = plan["references"][0]
        if ref(Path(materialized["path"])) != materialized:
            raise ValueError("selection geometry changed")
        if materialized not in exclusions:
            exclusions.append(materialized)
    if len(exclusions) != 19:
        raise ValueError("all19 selection geometry pools must be excluded first")
    declared = []
    for name in ("perturb_skill_pools_20261009_r1", "perturb_skill_pool_reserves_20261009_r2",
                 "perturb_skill_pool_reserves_20261009_r3", "perturb_macro_box_reserves_20261009_r4"):
        manifest = ROOT / "results/harness_v5" / name / "manifest.json"
        document = json.loads(manifest.read_text())
        item = next(r for r in document["pools"] if Path(r["path"]).stem == "confirmation")
        if ref(Path(item["path"]))["sha256"] != item["sha256"]:
            raise ValueError("confirmation preregistration changed")
        declared.append(item)
    for cell in args.cells:
        final = OUTPUT / f"{cell}_combined.json"
        if final.exists():
            print(json.dumps({"cell": cell, "status": "already_materialized", **ref(final)}), flush=True)
            continue
        selection_plan = json.loads((SELECTION / cell / "preparation/selection.json").read_text())
        source_row = json.loads(Path(selection_plan["references"][0]["path"]).read_text())["rows"][0]
        skill, category = source_row["rule"]["skill"], source_row["rule"]["category"]
        records, identities, references, duplicate_count = [], set(), [], 0
        for index, pool in enumerate(declared):
            if index == 3 and cell != "vla_subtask_box":
                continue
            stage = OUTPUT / cell / f"declaration{index}"
            manifest = stage / "manifest.json"
            if not manifest.exists():
                command = [str(ROOT / ".venv/bin/python"),
                           str(ADAPTER / "scripts/materialize_v5_perturb_skill_pools_20261009.py"),
                           "--pool", pool["path"], "--pool-sha256", pool["sha256"],
                           "--skill", skill, "--category", category, "--output", str(stage)]
                for item in exclusions:
                    command.extend(["--exclude-materialized", item["path"]])
                stage.parent.mkdir(parents=True, exist_ok=True)
                with stage.with_suffix(".stdout.log").open("x") as stdout, stage.with_suffix(".stderr.log").open("x") as stderr:
                    subprocess.run(command, env=environment, stdout=stdout, stderr=stderr, check=True)
            document = json.loads(manifest.read_text())
            references.append(ref(manifest))
            for original in document["rows"]:
                row = copy.deepcopy(original)
                if not row["permanent_training_exclusion"]:
                    raise ValueError("non-confirmation state in confirmation declaration")
                if row["status"] == "prepared":
                    state = row["state_sha256"]
                    if state in identities:
                        duplicate_count += 1
                        row.update(status="invalid_layout", invalid_reasons=[
                            *row.get("invalid_reasons", []), "duplicate_raw_state_across_confirmation_reserves"])
                    else:
                        identities.add(state)
                records.append(row)
            print(json.dumps({"cell": cell, "declaration": index, "unique_valid": len(identities),
                              "skill_executions": 0}), flush=True)
            if len(identities) >= 100:
                break
        payload = {"cell": cell, "rows": records, "counts": dict(Counter(r["status"] for r in records)),
                   "parents": references, "selection_exclusions": exclusions,
                   "cross_reserve_duplicates": duplicate_count,
                   "admission": "first100 unique geometrically valid in declaration order; policy not executed",
                   "prepared_for_confirmation": len(identities) >= 100,
                   "permanent_training_exclusion": True, "policy_outcomes_read": False,
                   "PRO_files_read": False, "skill_executions": 0,
                   "confirmation_result": None, "training_allowed": False,
                   "generator": ref(Path(__file__))}
        with final.open("x") as stream:
            stream.write(json.dumps(payload, indent=2) + "\n")
        print(json.dumps({"cell": cell, "counts": payload["counts"], **ref(final)}), flush=True)


if __name__ == "__main__":
    main()
