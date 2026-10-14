"""Pin a third grasp method on the same original-only selection layouts."""

import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile

ROOT = Path("/public/home/sunyihan/rpent_libero_eval")
PARENT = ROOT / "source_v5_skill_budget_20261009_r2"
SOURCE = ROOT / "source_v5_wrist_contact_20261009_r2"
ADAPTER = ROOT / "coordination/perturb_skill_adapter_20261009_r1"
PREVIOUS = ROOT / "results/harness_v5/perturb_skill_selection_20261009_r1"
OUTPUT = ROOT / "results/harness_v5/perturb_grasp_contact5cm_20261009_r2"


def ref(path):
    return {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    parent = json.loads((PARENT / "source_snapshot.json").read_text())
    patch = ROOT / "coordination/grasp_wrist_contact_v3_20261009.patch"
    if not SOURCE.exists():
        if ref(Path(parent["archive"]["path"]))["sha256"] != parent["archive"]["sha256"]:
            raise ValueError("parent source archive changed")
        shutil.copytree(PARENT, SOURCE, symlinks=True,
                        ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache"))
        subprocess.run(["git", "apply", "--check", str(patch)], cwd=SOURCE, check=True)
        subprocess.run(["git", "apply", str(patch)], cwd=SOURCE, check=True)
        files = []
        for item in parent["files"]:
            relative = item.get("relative_path") or str(Path(item["path"]).relative_to(PARENT))
            files.append({**ref(SOURCE / relative), "relative_path": relative})
        archive = Path(str(SOURCE) + ".tar")
        with tarfile.open(archive, "x") as stream:
            for item in files:
                stream.add(item["path"], arcname=item["relative_path"], recursive=False)
        identity = {"path": str(SOURCE), "commit": parent["commit"],
                    "identity_kind": "budget_base_commit_plus_wrist_contact_patch",
                    "base_archive": parent["archive"], "patch": ref(patch),
                    "test_source": ref(ROOT / "coordination/test_v5_grasp_closeup.py"),
                    "files": files, "archive": ref(archive), "unrelated_dirty_changes_excluded": True}
        (SOURCE / "source_snapshot.json").write_text(json.dumps(identity, indent=2) + "\n")
    identity = json.loads((SOURCE / "source_snapshot.json").read_text())
    if identity.get("patch") != ref(patch):
        raise ValueError("existing near-contact snapshot does not match the patch")
    launcher = ADAPTER / "scripts/run_v5_perturb_skill_selection_20261009.sbatch"
    for category in ("bowl", "bottle", "box", "cup", "frypan"):
        cell = "grasp_" + category
        prep = OUTPUT / cell / "preparation"
        if (prep / "startup_submission.json").exists():
            print(json.dumps({"cell": cell, "status": "startup_already_registered"}), flush=True)
            continue
        old_path = PREVIOUS / cell / "preparation/selection.json"
        old = json.loads(old_path.read_text())
        method = "wrist_contact5cm160"
        condition = copy.deepcopy(old["conditions"]["wrist_near_contact160"])
        condition["overrides"].update(grasp_wrist_contact_v3=True, grasp_short_prompt_v2=True)
        cases = [copy.deepcopy(case) for case in old["cases"] if case["condition"] == "wrist_near_contact160"]
        if len(cases) != 100 or len({case["state_sha256"] for case in cases}) != 100:
            raise ValueError("third method must reuse exactly100 unique selection layouts")
        for case in cases:
            case["name"] = case["name"].removesuffix("_wrist_near_contact160") + "_" + method
            case["condition"] = method
        prep.mkdir(parents=True, exist_ok=False)
        plan = {**old, "source_path": str(SOURCE), "source_snapshot": identity,
                "source_commit": identity["commit"], "conditions": {method: condition}, "cases": cases,
                "producer": ref(Path(__file__)), "comparison_parent": ref(old_path),
                "producer_dependencies": [*old["producer_dependencies"], ref(patch)],
                "purpose": "third original-only perturbation selection method: wrist measurement at15cm, contact at5cm within2cm tolerance",
                "confirmation": False, "training_allowed": False}
        manifest = prep / "selection.json"
        manifest.write_text(json.dumps(plan, indent=2) + "\n")
        env = {"PERTURB_SKILL_PLAN": str(manifest), "PERTURB_SKILL_PLAN_SHA": ref(manifest)["sha256"],
               "PERTURB_SKILL_SOURCE": str(SOURCE), "PERTURB_SKILL_ADAPTER": str(ADAPTER),
               "PERTURB_SKILL_OUTPUT": str(OUTPUT / cell), "PERTURB_SKILL_STARTUP": "1"}
        cpu = subprocess.run(["bash", str(launcher)], env={**os.environ, **env,
                             "PERTURB_SKILL_CPU_ONLY": "1"}, capture_output=True, text=True)
        (prep / "CPU_preflight.log").write_text(cpu.stdout + cpu.stderr)
        cpu.check_returncode()
        command = ["sbatch", "--parsable", "--array=0", "--nice=1000",
                   "--export=ALL," + ",".join(k + "=" + v for k, v in env.items()), str(launcher)]
        started = subprocess.run(command, capture_output=True, text=True, check=True)
        record = {"job": started.stdout.strip(), "environment": env, "launcher": ref(launcher),
                  "manifest": ref(manifest), "CPU_preflight": "pass", "physical_startup": "pending",
                  "confirmation": False, "source_snapshot": ref(SOURCE / "source_snapshot.json")}
        (prep / "startup_submission.json").write_text(json.dumps(record, indent=2) + "\n")
        print(json.dumps({"cell": cell, "job": record["job"], "manifest": record["manifest"],
                          "source_archive": identity["archive"], "CPU_preflight": "pass"}), flush=True)


if __name__ == "__main__":
    main()
