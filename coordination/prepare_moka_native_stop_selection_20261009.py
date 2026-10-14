"""Pin a diagnostic-only native-stop overlay on the existing selection states."""

import copy
import hashlib
import json
from pathlib import Path
import shutil
import tarfile


ROOT = Path("/public/home/sunyihan/rpent_libero_eval")
PARENT = ROOT / "results/harness_v5/moka_selection100_20261009_r2/preparation"
OUTPUT = ROOT / "results/harness_v5/moka_selection100_20261009_r3/preparation"
SOURCE = ROOT / "source_v5_moka_native_stop_20261009_r3"
OVERLAY = (
    "probe_v5_skill501_original.py",
    "probe_v5_moka_transfer_public_20261007.py",
    "serve_v5_moka_layout24_20261008.py",
    "probe_v5_moka_layout24_20261008.py",
)


def ref(path):
    path = Path(path).resolve(strict=True)
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return {"path": str(path), "sha256": digest.hexdigest()}


def main():
    old_path = PARENT / "selection100.json"
    old = json.loads(old_path.read_text())
    if ref(old_path)["sha256"] != "6e518d6f17f18ad9297814443b8780692e56af87ee4d96cb063e64423b16dd29":
        raise ValueError("parent selection plan changed")
    parent_source = Path(old["source_snapshot"]["path"])
    archive = old["source_snapshot"]["archive"]
    if ref(archive["path"])["sha256"] != archive["sha256"]:
        raise ValueError("parent source archive changed")
    OUTPUT.mkdir(parents=True, exist_ok=False)
    shutil.copytree(parent_source, SOURCE, symlinks=True,
                    ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache"))
    overlay = []
    for name in OVERLAY:
        original = ROOT / "coordination" / name
        destination = SOURCE / "scripts" / name
        shutil.copyfile(original, destination)
        overlay.append({"original": ref(original), "installed": ref(destination)})
    files = []
    for item in old["source_snapshot"]["files"]:
        relative = Path(item["path"]).relative_to(parent_source)
        files.append({**ref(SOURCE / relative), "relative_path": str(relative)})
    new_archive = Path(str(SOURCE) + ".tar")
    with tarfile.open(new_archive, "w") as stream:
        for item in files:
            stream.add(item["path"], arcname=item["relative_path"], recursive=False)
    identity = {"path": str(SOURCE), "commit": old["source_snapshot"]["commit"],
                "identity_kind": "base_commit_plus_diagnostic_native_stop_overlay",
                "base_archive": archive, "overlay": overlay, "files": files,
                "archive": ref(new_archive), "dirty_worktree_excluded": True}
    identity_path = OUTPUT / "source_identity.json"
    identity_path.write_text(json.dumps(identity, indent=2) + "\n")
    for name in ("probe_v5_moka_layout24_20261008.py",
                 "serve_v5_moka_layout24_20261008.py", "typed_choice_eval.py", "preflight.py"):
        origin = SOURCE / "scripts" / name if name in OVERLAY else PARENT / name
        shutil.copyfile(origin, OUTPUT / name)
    launcher = (PARENT / "run_selection100.sbatch").read_text().replace(
        str(PARENT.parent / "physical"), str(OUTPUT.parent / "physical"))
    begin = launcher.index("missing_controls=[row.get")
    end = launcher.index('(root/"contract.json").write_text', begin)
    # A public identity binding failure is a skill outcome, even without motion.
    # The real single-case startup still requires a physical request.
    launcher = launcher[:begin] + launcher[end:]
    launcher_path = OUTPUT / "run_selection100.sbatch"
    launcher_path.write_text(launcher)

    def rewrite(value):
        if isinstance(value, list):
            return [rewrite(item) for item in value]
        if isinstance(value, dict):
            result = {key: rewrite(item) for key, item in value.items()}
            if "path" in result and "sha256" in result:
                result["sha256"] = ref(result["path"])["sha256"]
            return result
        if isinstance(value, str):
            for before, after in ((parent_source, SOURCE), (PARENT, OUTPUT)):
                if value == str(before) or value.startswith(str(before) + "/"):
                    return str(after) + value[len(str(before)):]
        return value

    plan = rewrite(copy.deepcopy(old))
    previous_method = next(iter(plan["conditions"]))
    method = "moka_original_public_native_stop160"
    condition = plan["conditions"].pop(previous_method)
    condition.update(native_task_stop_v1=True, max_chunks=160,
                     contact_stop="public_native_completion_or_measured_placement")
    plan["conditions"][method] = condition
    for case in plan["cases"]:
        if not case.get("original_goal_source"):
            raise ValueError("native stop requires an unchanged original task goal")
        case["condition"] = method
    plan.update(source_snapshot=identity, source_identity=ref(identity_path),
                source_commit=identity["commit"], comparison_parent=ref(old_path),
                producer=ref(__file__), native_completion_is_public=True,
                private_predicates_control_stopping=False,
                purpose="original selection100: public native completion stop, production160 chunks",
                source_overlay=overlay, launcher_identity=ref(launcher_path),
                jobs_submitted=0)
    plan["producer_dependencies"].append(ref(identity_path))
    manifest = OUTPUT / "selection100.json"
    manifest.write_text(json.dumps(plan, indent=2) + "\n")
    print(json.dumps({"source": str(SOURCE), "manifest": ref(manifest),
                      "archive": identity["archive"], "launcher": ref(launcher_path),
                      "confirmation": False, "physical_trials": 100}))


if __name__ == "__main__":
    main()
