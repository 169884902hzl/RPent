#!/usr/bin/env python3
"""Build an immutable tracked-tree snapshot for an expert resume run.

The resume launcher must use the same source tree for its startup probe and
for every array shard.  This helper intentionally archives only the selected
git commit, so unrelated dirty result files cannot enter the runtime source.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import tarfile
from pathlib import Path


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def run(*args: str, cwd: Path) -> str:
    return subprocess.check_output(args, cwd=cwd, text=True).strip()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--commit", default="HEAD")
    args = parser.parse_args()

    repo = args.repo.resolve()
    commit = run("git", "rev-parse", args.commit, cwd=repo)
    output = args.output.resolve()
    if output.exists():
        raise SystemExit(f"refusing to replace existing snapshot: {output}")
    output.mkdir(parents=True)

    archive = output.with_suffix(".tar")
    archive.parent.mkdir(parents=True, exist_ok=True)
    with archive.open("wb") as stream:
        subprocess.run(["git", "archive", "--format=tar", commit], cwd=repo, stdout=stream, check=True)
    with tarfile.open(archive) as tar:
        tar.extractall(output)
    archive_sha = sha256(archive)

    required = [
        "robots/libero/v5_oracle_policy.py",
        "tests/unit_tests/robots/libero/test_v5_oracle_policy.py",
        "tests/unit_tests/robots/libero/fixtures/oracle_blocked_help_job4417.json",
        "v5_batch_eval.py",
        "typed_choice_eval.py",
        "scripts/run_v5_interim574.sbatch",
    ]
    files = []
    for relative in required:
        path = output / relative
        if not path.is_file():
            raise SystemExit(f"snapshot is missing required file: {relative}")
        files.append({"path": str(path), "sha256": sha256(path)})
    metadata = {
        "repo": str(repo),
        "commit": commit,
        "source_tree": str(output),
        "archive": {"path": str(archive), "sha256": archive_sha},
        "files": files,
        "required_files": files,
        "dirty_worktree_excluded": True,
    }
    (output / "source_snapshot.json").write_text(json.dumps(metadata, indent=2) + "\n")
    print(json.dumps(metadata, indent=2))


if __name__ == "__main__":
    main()
