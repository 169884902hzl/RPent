"""Release registered selection arrays only after their physical startup."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess

ROOT = Path("/public/home/sunyihan/rpent_libero_eval")
OUTPUT = ROOT / "results/harness_v5/perturb_skill_selection_20261009_r1"


def ref(path):
    return {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--release", action="store_true")
    parser.add_argument("--root", type=Path, default=OUTPUT)
    args = parser.parse_args()
    args.root = args.root.resolve(strict=True)
    for registration in sorted(args.root.glob("*/preparation/startup_submission.json")):
        prep = registration.parent
        cell = prep.parent.name
        if (prep / "formal_submission.json").exists():
            print(json.dumps({"cell": cell, "status": "formal_already_submitted"}), flush=True)
            continue
        startup = json.loads(registration.read_text())
        env = dict(startup["environment"])
        launcher = Path(startup["launcher"]["path"])
        manifest = Path(startup["manifest"]["path"])
        plan = json.loads(manifest.read_text())
        if (ref(manifest) != startup["manifest"] or ref(launcher) != startup["launcher"]):
            raise ValueError("startup plan or launcher changed")
        job = str(startup["job"]).split(";")[0]
        out = args.root / cell / f"job{job}" / "part0"
        contract_path = out / "startup_contract.json"
        state = subprocess.run(["sacct", "-n", "-X", "-j", job,
                                "--format=JobID,State,ExitCode", "-P"],
                               text=True, capture_output=True, check=True).stdout.strip()
        if not contract_path.exists() or "|COMPLETED|0:0" not in state:
            print(json.dumps({"cell": cell, "job": job, "status": "waiting_physical_startup",
                              "sacct": state}), flush=True)
            continue
        contract = json.loads(contract_path.read_text())
        expected = {"plan_sha256": startup["manifest"]["sha256"],
                    "source_commit": plan["source_commit"],
                    "launcher_sha256": startup["launcher"]["sha256"]}
        if (contract["status"] != "pass" or contract["physical_controls"] <= 0
                or any(contract[k] != v for k, v in expected.items())
                or contract["case_name"] != plan["cases"][0]["name"]
                or ref(Path(contract["episodes"]["path"])) != contract["episodes"]):
            raise ValueError("physical contract no longer matches this selection plan")
        if not args.release:
            print(json.dumps({"cell": cell, "status": "ready", "physical_controls": contract["physical_controls"]}), flush=True)
            continue
        remaining = len(plan["cases"]) - 1
        if remaining == 0:
            print(json.dumps({"cell": cell, "status": "startup_is_complete_plan"}), flush=True)
            continue
        shards = min(8, remaining)
        env.update(PERTURB_SKILL_STARTUP="0", PERTURB_SKILL_SHARDS=str(shards),
                   PERTURB_SKILL_STARTUP_CONTRACT=str(contract_path))
        # Use the same neutral cwd as the physical runner. The mutable root
        # checkout otherwise shadows the registered source on sys.path.
        cpu = subprocess.run(["bash", str(launcher)], cwd="/tmp", env={**os.environ, **env,
                             "PERTURB_SKILL_CPU_ONLY": "1"}, capture_output=True, text=True)
        (prep / "formal_CPU_preflight.log").write_text(cpu.stdout + cpu.stderr)
        cpu.check_returncode()
        intent = prep / "formal_submission_intent.json"
        with intent.open("x") as stream:
            stream.write(json.dumps({"environment": env, "launcher": ref(launcher),
                                     "contract": ref(contract_path), "registered_attempts": len(plan["cases"]),
                                     "startup_included": True}, indent=2) + "\n")
        command = ["sbatch", "--parsable", f"--array=0-{shards-1}%8", "--nice=0",
                   "--export=ALL," + ",".join(k + "=" + v for k, v in env.items()), str(launcher)]
        result = subprocess.run(command, cwd="/tmp", text=True, capture_output=True, check=True)
        record = {"job": result.stdout.strip(), "command": command, "environment": env,
                  "manifest": ref(manifest), "launcher": ref(launcher),
                  "startup_contract": ref(contract_path), "startup_included": True,
                  "remaining_attempts": len(plan["cases"]) - 1, "confirmation": False}
        with (prep / "formal_submission.json").open("x") as stream:
            stream.write(json.dumps(record, indent=2) + "\n")
        print(json.dumps({"cell": cell, "status": "submitted", "job": record["job"],
                          "remaining_attempts": record["remaining_attempts"]}), flush=True)


if __name__ == "__main__":
    main()
