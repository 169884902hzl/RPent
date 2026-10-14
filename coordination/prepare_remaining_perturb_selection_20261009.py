"""Prepare and physically start only geometrically ready selection cells."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess


ROOT = Path("/public/home/sunyihan/rpent_libero_eval")
ADAPTER = ROOT / "coordination/perturb_skill_adapter_20261009_r1"
MATERIALIZED = ROOT / "results/harness_v5/perturb_skill_materialization_20261009_r2"
OUTPUT = ROOT / "results/harness_v5/perturb_skill_selection_20261009_r1"


def ref(path):
    return {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("cells", nargs="+")
    args = parser.parse_args()
    parent = json.loads((OUTPUT / "grasp_bowl/preparation/selection.json").read_text())
    source = Path(parent["source_path"])
    environment = {**os.environ, "LIBERO_TYPE": "standard",
                   "PYTHONPATH": f"{ADAPTER}:{source}:{source / 'scripts'}"}
    launcher = ADAPTER / "scripts/run_v5_perturb_skill_selection_20261009.sbatch"
    for cell in args.cells:
        preparation = OUTPUT / cell / "preparation"
        if (preparation / "startup_submission.json").exists():
            print(json.dumps({"cell": cell, "status": "startup_already_registered"}), flush=True)
            continue
        candidates = [MATERIALIZED / f"selection_{cell}_combined_r4.json",
                      MATERIALIZED / f"selection_{cell}_combined_r3.json",
                      MATERIALIZED / f"selection_{cell}_combined.json"]
        materialized = next((p for p in candidates if p.exists()), None)
        if materialized is None:
            print(json.dumps({"cell": cell, "status": "not_materialized"}), flush=True)
            continue
        payload = json.loads(materialized.read_text())
        valid = sum(row["status"] == "prepared" for row in payload["rows"])
        if valid < 100:
            print(json.dumps({"cell": cell, "status": "geometric_gap", "valid": valid}), flush=True)
            continue
        if not preparation.exists():
            result = subprocess.run([
                str(ROOT / ".venv/bin/python"),
                str(ADAPTER / "scripts/prepare_v5_perturb_skill_selection_20261009.py"),
                "--materialized", str(materialized), "--materialized-sha256", ref(materialized)["sha256"],
                "--base-plan", parent["references"][1]["path"], "--source", str(source),
                "--adapter", str(ADAPTER), "--choice-package", parent["choice_package"],
                "--output", str(preparation)], env=environment, capture_output=True, text=True)
            if result.returncode:
                print(result.stderr[-2000:], flush=True)
                result.check_returncode()
        manifest = preparation / "selection.json"
        env = {"PERTURB_SKILL_PLAN": str(manifest),
               "PERTURB_SKILL_PLAN_SHA": ref(manifest)["sha256"],
               "PERTURB_SKILL_SOURCE": str(source), "PERTURB_SKILL_ADAPTER": str(ADAPTER),
               "PERTURB_SKILL_OUTPUT": str(OUTPUT / cell), "PERTURB_SKILL_STARTUP": "1"}
        cpu = subprocess.run(["bash", str(launcher)],
                             env={**environment, **env, "PERTURB_SKILL_CPU_ONLY": "1"},
                             text=True, capture_output=True)
        (preparation / "CPU_preflight.log").write_text(cpu.stdout + cpu.stderr)
        cpu.check_returncode()
        command = ["sbatch", "--parsable", "--array=0", "--nice=1000",
                   "--export=ALL," + ",".join(k + "=" + v for k, v in env.items()), str(launcher)]
        started = subprocess.run(command, text=True, capture_output=True, check=True)
        record = {"job": started.stdout.strip(), "environment": env,
                  "launcher": ref(launcher), "manifest": ref(manifest),
                  "CPU_preflight": "pass", "physical_startup": "pending", "confirmation": False}
        (preparation / "startup_submission.json").write_text(json.dumps(record, indent=2) + "\n")
        print(json.dumps({"cell": cell, **record}), flush=True)


if __name__ == "__main__":
    main()
