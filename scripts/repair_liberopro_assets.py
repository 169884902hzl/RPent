#!/usr/bin/env python3
# Copyright 2026 Zhilun Hu.
# SPDX-License-Identifier: Apache-2.0
"""Pin, back up, compare and install the authoritative LIBERO-PRO assets."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import tarfile
from pathlib import Path

REPO = "zhouxueyang/LIBERO-Pro"
ROOTS = ("bddl_files", "init_files")
BASES = ("libero_spatial", "libero_object", "libero_goal", "libero_10")
FINAL_SUITES = tuple(f"{base}_{axis}" for base in BASES for axis in ("swap", "task"))


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def write_json(path: Path, value: object) -> None:
    with path.open("x") as stream:
        json.dump(value, stream, indent=2, sort_keys=True)
        stream.write("\n")


def inventory(root: Path) -> dict:
    return {
        str(path.relative_to(root)): {
            "sha256": digest(path),
            "bytes": path.stat().st_size,
        }
        for name in ROOTS
        for path in sorted((root / name).rglob("*"))
        if path.is_file()
    }


def download(args: argparse.Namespace) -> None:
    from huggingface_hub import HfApi, snapshot_download

    api = HfApi(endpoint="https://hf-mirror.com")
    info = api.dataset_info(REPO, revision=args.revision, files_metadata=True)
    if info.sha != args.revision:
        raise ValueError(f"revision resolved to {info.sha}, expected {args.revision}")
    expected = [item for item in info.siblings if item.rfilename.startswith(ROOTS)]
    identity = {
        "repo_id": REPO,
        "repo_type": "dataset",
        "revision": info.sha,
        "endpoint": api.endpoint,
        "dataset_path": str(args.dataset),
        "expected_files": [item.rfilename for item in expected],
    }
    identity_path = args.output / "download_identity.json"
    if identity_path.exists():
        if json.loads(identity_path.read_text()) != identity:
            raise ValueError("download resume identity changed")
    else:
        write_json(identity_path, identity)
    snapshot_download(
        repo_id=REPO,
        repo_type="dataset",
        revision=info.sha,
        local_dir=args.dataset,
        endpoint=api.endpoint,
        allow_patterns=[f"{name}/**" for name in ROOTS],
        max_workers=args.max_workers,
    )
    files = inventory(args.dataset)
    for item in expected:
        entry = files[item.rfilename]
        if item.size is not None and entry["bytes"] != item.size:
            raise ValueError(f"size mismatch: {item.rfilename}")
        lfs_hash = item.lfs.sha256 if item.lfs is not None else None
        if lfs_hash is not None and entry["sha256"] != lfs_hash:
            raise ValueError(f"LFS SHA-256 mismatch: {item.rfilename}")
        entry["hub_lfs_sha256"] = lfs_hash
    write_json(args.output / "hf_files.json", files)
    print(json.dumps({"revision": info.sha, "downloaded_files": len(files)}))


def compare(args: argparse.Namespace) -> None:
    current = inventory(args.install)
    archive_path = args.output / "installed_before.tar.gz"
    with tarfile.open(archive_path, "x:gz") as archive:
        for name in ROOTS:
            archive.add(args.install / name, arcname=name)
    # Verify the complete backup against the installation before any writes.
    with tarfile.open(archive_path, "r:gz") as archive:
        members = {item.name: item for item in archive.getmembers() if item.isfile()}
        if members.keys() != current.keys():
            raise ValueError("backup inventory differs from installed inventory")
        for name, item in members.items():
            with archive.extractfile(item) as stream:
                value = hashlib.sha256(stream.read()).hexdigest()
            if value != current[name]["sha256"]:
                raise ValueError(f"backup hash mismatch: {name}")
    write_json(args.output / "installed_before.json", current)
    hf = json.loads((args.output / "hf_files.json").read_text())
    differences = []
    for name in sorted(current.keys() | hf.keys()):
        before, after = current.get(name), hf.get(name)
        if before is None:
            status = "hf_only"
        elif after is None:
            status = "installed_only_preserved"
        elif before["sha256"] != after["sha256"]:
            status = "changed"
        else:
            continue
        differences.append(
            {"path": name, "status": status, "before": before, "hf": after}
        )
    write_json(args.output / "differences.json", differences)
    write_json(
        args.output / "backup_identity.json",
        {
            "path": str(archive_path),
            "sha256": digest(archive_path),
            "installed_root": str(args.install),
            "file_count": len(current),
        },
    )
    print(
        json.dumps(
            {"backed_up_files": len(current), "different_files": len(differences)}
        )
    )


def install(args: argparse.Namespace) -> None:
    expected = json.loads((args.output / "installed_before.json").read_text())
    if inventory(args.install) != expected:
        raise ValueError("installation changed since backup; compare a fresh version")
    queue = subprocess.check_output(
        ["squeue", "-u", os.environ["USER"], "-h", "-o", "%i|%j|%T"],
        text=True,
    )
    active = [line for line in queue.splitlines() if "libero" in line.lower()]
    if active:
        raise RuntimeError(f"LIBERO jobs still queued or running: {active}")
    hf = json.loads((args.output / "hf_files.json").read_text())
    for name, entry in hf.items():
        source = args.dataset / name
        if digest(source) != entry["sha256"]:
            raise ValueError(f"download changed after audit: {name}")
        target = args.install / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    installed = inventory(args.install)
    for name, entry in hf.items():
        if installed[name]["sha256"] != entry["sha256"]:
            raise ValueError(f"installed hash mismatch: {name}")
    write_json(args.output / "installed_after.json", installed)
    write_json(
        args.output / "sync_result.json",
        {
            "copied_files": len(hf),
            "all_hf_hashes_match": True,
            "queue_before_sync": queue.splitlines(),
            "source": str(args.dataset),
            "target": str(args.install),
            "revision": args.revision,
        },
    )
    print(json.dumps({"copied_files": len(hf), "all_hf_hashes_match": True}))


def verify(args: argparse.Namespace) -> None:
    import liberopro.liberopro.benchmark as benchmark
    from liberopro.liberopro import get_libero_path

    rows, errors = [], []
    suites = [
        f"{base}_{axis}" for base in BASES for axis in ("swap", "task", "lan", "object")
    ]
    for suite in suites:
        cohort = benchmark.get_benchmark(suite)()
        if cohort.get_num_tasks() != 10:
            errors.append(f"{suite}: {cohort.get_num_tasks()} tasks, expected 10")
        for index in range(cohort.get_num_tasks()):
            task = cohort.get_task(index)
            bddl = Path(cohort.get_task_bddl_file_path(index))
            init = (
                Path(get_libero_path("init_states"))
                / task.problem_folder
                / task.init_states_file
            )
            match = re.search(r"\(:language\s+([^)]+)\)", bddl.read_text())
            language = match.group(1).strip() if match else None
            trials = len(cohort.get_task_init_states(index))
            row = {
                "suite": suite,
                "task_id": index,
                "task_name": task.name,
                "trials": trials,
                "language": task.language,
                "bddl_language": language,
                "language_matches_bddl": language == task.language,
                "bddl_path": str(bddl),
                "bddl_sha256": digest(bddl),
                "init_path": str(init),
                "init_sha256": digest(init),
                "final_suite": suite in FINAL_SUITES,
                "d2_init40_available": trials > 40
                if suite in FINAL_SUITES and index < 5
                else None,
            }
            rows.append(row)
            if trials < 10 or language != task.language:
                errors.append(
                    f"{suite}/{index}: trials={trials}, language_match={language == task.language}"
                )
            if suite in FINAL_SUITES and index < 5 and trials <= 40:
                errors.append(
                    f"D2 {suite}/{index}: init40 unavailable, trials={trials}"
                )
            print(f"{suite} task{index}: trials={trials} language={task.language!r}")
    write_json(
        args.output / args.report_name,
        {
            "revision": args.revision,
            "rows": rows,
            "errors": errors,
            "final_tasks": sum(row["final_suite"] for row in rows),
            "d2_unchanged_40_available": all(
                row["d2_init40_available"]
                for row in rows
                if row["d2_init40_available"] is not None
            ),
            "passed": not errors,
        },
    )
    if errors:
        raise RuntimeError("; ".join(errors))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "operation", choices=("download", "compare", "install", "verify")
    )
    parser.add_argument("--revision", required=True)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--install", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--report-name", default="validation_after.json")
    parser.add_argument("--max-workers", type=int, default=4)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    {"download": download, "compare": compare, "install": install, "verify": verify}[
        args.operation
    ](args)


if __name__ == "__main__":
    main()
