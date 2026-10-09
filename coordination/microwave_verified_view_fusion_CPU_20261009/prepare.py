"""Prepare one visited-state diagnostic with an explicit code-only overlay."""

import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tarfile

ROOT = Path("/public/home/sunyihan/rpent_libero_eval")
OLD_PLAN = ROOT / "results/harness_v5/microwave_candidate_hold_20261008_r1/preparation/stop_hold48.json"
OLD_SHA = "36e554a9baa9b72942cdac687c77014b36eef3930e49cff690ab057e3d281d15"
PATCH = ROOT / "coordination/microwave_verified_view_fusion_20261009.patch"
COMMIT = "e0a6597549731414c47b4be737d083e9399d1ab2"
SOURCE = ROOT / "source_v5_microwave_verified_view_20261009_r1"
OUTPUT = ROOT / "results/harness_v5/microwave_verified_view_20261009_r1"


def ref(path):
    return {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    if ref(OLD_PLAN)["sha256"] != OLD_SHA:
        raise ValueError("Original development plan changed")
    old = json.loads(OLD_PLAN.read_text())
    parent = Path(old["source_snapshot"]["path"])
    for item in [*old["source_snapshot"]["files"], old["source_snapshot"]["archive"],
                 old["producer"], *old["producer_dependencies"], old["launcher"], old["adapter"]]:
        if ref(Path(item["path"]))["sha256"] != item["sha256"]:
            raise ValueError("Parent source changed: " + item["path"])
    OUTPUT.mkdir(parents=True, exist_ok=False)
    shutil.copytree(parent, SOURCE, ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache"))
    subprocess.run(["patch", "--batch", "--forward", "-p1", "-d", str(SOURCE),
                    "--input", str(PATCH)], check=True)
    files = [{**ref(SOURCE / Path(item["path"]).relative_to(parent)),
              "relative_path": str(Path(item["path"]).relative_to(parent))}
             for item in old["source_snapshot"]["files"]]
    archive = Path(str(SOURCE) + ".tar")
    with tarfile.open(archive, "w") as stream:
        for item in files:
            stream.add(item["path"], arcname=item["relative_path"], recursive=False)
    identity = {"path": str(SOURCE), "commit": COMMIT,
        "identity_kind": "original_candidate_hold_source_plus_verified_view_fusion_patch",
        "parent_plan": ref(OLD_PLAN), "patch": ref(PATCH), "files": files, "archive": ref(archive)}
    identity_path = OUTPUT / "source_identity.json"
    identity_path.write_text(json.dumps(identity, indent=2) + "\n")

    def rewrite(value):
        if isinstance(value, list):
            return [rewrite(item) for item in value]
        if isinstance(value, dict):
            result = {key: rewrite(item) for key, item in value.items()}
            if set(("path", "sha256")) <= result.keys() and str(result["path"]).startswith(str(SOURCE) + "/"):
                result["sha256"] = ref(Path(result["path"]))["sha256"]
            return result
        if isinstance(value, str) and (value == str(parent) or value.startswith(str(parent) + "/")):
            return str(SOURCE) + value[len(str(parent)):]
        return value

    plan = rewrite(old)
    plan.update(source_snapshot=identity, source_identity_file=str(identity_path),
                source_snapshot_sha256=ref(identity_path)["sha256"],
                purpose="visited original microwave verified-view fusion diagnosis; not confirmation",
                thresholds_changed=False, comparison_baseline_job="candidate_hold_r1",
                comparison_baseline=ref(OLD_PLAN), training_allowed=False, train_allowed=False,
                qualification_authorized=False, new_training_rows=0)
    for condition in plan["conditions"].values():
        condition["overrides"]["microwave_verified_view_fusion_v1"] = True
    plan_path = OUTPUT / "stop_verified48.json"
    plan_path.write_text(json.dumps(plan, indent=2) + "\n")
    print(json.dumps({"source": str(SOURCE), "identity": ref(identity_path),
        "plan": ref(plan_path), "launcher": plan["launcher"], "physical_output": str(OUTPUT / "stop48")}))


if __name__ == "__main__":
    main()
