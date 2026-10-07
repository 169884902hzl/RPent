"""CPU preparation for one-source passive truth/prediction diagnostics.

Only explicit manifest entries are read. No GPU submission or artifact discovery.
The formal array must wait for this snapshot's real same-launcher startup contract.
"""

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import tarfile


OVERLAYS = (
    "scripts/run_v5_success578.sbatch",
    "scripts/run_original_success578.py",
    "scripts/original_success578_server.py",
)


def ref(path):
    path = Path(path).resolve(strict=True)
    return {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def checked(record):
    path = Path(record["path"])
    if not path.is_absolute() or ref(path)["sha256"] != record["sha256"]:
        raise ValueError("registered input changed: " + str(path))
    return path


def prepare(args):
    base_path = checked({"path": str(args.base_index), "sha256": args.base_sha})
    parent_path = checked({"path": str(args.parent_index), "sha256": args.parent_sha})
    code_path = args.code_index.resolve(strict=True)
    base = json.loads(base_path.read_text())["source_snapshot"]
    parent = json.loads(parent_path.read_text())
    code = json.loads(code_path.read_text())
    overlays = {entry["relative_path"]: checked(entry) for entry in code["files"]}
    if set(overlays) != set(OVERLAYS):
        raise ValueError("only the three owned success578 source files may be overlaid")
    checked(base["archive"])
    source, output = args.snapshot.resolve(), args.output.resolve()
    source.mkdir(parents=True, exist_ok=False)
    output.mkdir(parents=True, exist_ok=False)
    files, copied = [], set()
    for entry in base["files"]:
        old = checked(entry)
        relative = entry["relative_path"]
        if old != Path(base["path"]) / relative or Path(relative).is_absolute() or ".." in Path(relative).parts:
            raise ValueError("source file escapes its declared snapshot")
        target = source / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(overlays.get(relative, old), target)
        files.append({**ref(target), "relative_path": relative})
        copied.add(relative)
    for relative in OVERLAYS:
        if relative not in copied:
            target = source / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(overlays[relative], target)
            files.append({**ref(target), "relative_path": relative})
    archive = Path(str(source) + ".tar")
    if archive.exists():
        raise FileExistsError(archive)
    with tarfile.open(archive, "w") as stream:
        for entry in files:
            stream.add(entry["path"], arcname=entry["relative_path"], recursive=False)
    identity = {"path": str(source), "commit": code["commit"],
                "identity_kind": "explicit_legal_r2_plus_passive_success578_overlay",
                "base_source_commit": base["commit"], "base_source_index": ref(base_path),
                "code_index": ref(code_path), "files": files, "archive": ref(archive)}
    identity_path = output / "source_identity.json"
    identity_path.write_text(json.dumps(identity, indent=2) + "\n")
    parents = [json.loads(checked(entry).read_text()) for entry in parent["files"]
               if Path(entry["path"]).name.startswith("truth_part")]
    episodes = [episode for plan in parents for episode in plan["episodes"]]
    if len(episodes) != 20 or len({(e["suite"], e["task"], e["seed"]) for e in episodes}) != 20:
        raise ValueError("preserve the registered twenty unique original diagnostic states")
    if any(e["suite"] not in ("libero_spatial", "libero_object", "libero_goal", "libero_10")
           or not 0 <= e["task"] < 10 for e in episodes):
        raise ValueError("truth diagnosis is restricted to original forty tasks")
    plans = []
    for part, old in enumerate(parents):
        plan = {**old, "source_path": str(source), "source_commit": code["commit"],
                "source_snapshot": identity, "cohort": "truth", "libero_type": "standard",
                "budget": {**old["budget"], "success_prediction_diagnostic": True,
                           "success_top3_v1": False},
                "same_run_pairing_schema": "same_run_success578/2",
                "startup_policy": "same_source_same_launcher_real_one_episode_before_remaining_shards",
                "private_labels_affect_selection": False, "diagnostic_control_steps": 0,
                "behavior_frozen": False, "training_allowed": False}
        path = output / f"truth_part{part}.json"
        path.write_text(json.dumps(plan, indent=2) + "\n")
        plans.append(ref(path))
    index = {"purpose": "same-run execution-before probabilities, choices and passive private labels",
             "files": plans, "references": [ref(parent_path), ref(base_path), ref(code_path),
                 ref(identity_path)], "source_path": str(source), "source_commit": code["commit"],
             "source_snapshot": identity, "planned": {"truth": 20},
             "batch_runner": ref(source / "v5_batch_eval.py"),
             "launcher": ref(source / "scripts/run_v5_success578.sbatch"),
             "runtime_supplement": [ref(source / "typed_choice_eval.py")],
             "labels": {"location": "private_action_labels.jsonl sidecar",
                        "unknown": None, "finish": "separate_from_action_auroc",
                        "extra_control_steps": 0, "returned_to_planner": False},
             "old4103_pairing_allowed": False, "training_allowed": False}
    manifest_path = output / "manifest.json"
    manifest_path.write_text(json.dumps(index, indent=2) + "\n")
    receipt = {"manifest": ref(manifest_path), "source_identity": ref(identity_path),
               "source_path": str(source), "launcher": index["launcher"],
               "registered_episodes": len(episodes), "GPU_submitted": False,
               "CPU_launcher_preflight_pending": True, "real_startup_contract_pending": True}
    (output / "preparation.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps(receipt))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-index", type=Path, required=True)
    parser.add_argument("--base-sha", required=True)
    parser.add_argument("--parent-index", type=Path, required=True)
    parser.add_argument("--parent-sha", required=True)
    parser.add_argument("--code-index", type=Path, required=True)
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    prepare(parser.parse_args())
