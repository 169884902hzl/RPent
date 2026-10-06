"""Check explicit smoke inputs and asset identities before GPU initialization."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path


def identity(path: Path) -> dict:
    path = path.resolve(strict=True)
    with path.open("rb") as handle:
        digest = hashlib.sha256()
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return {"path": str(path), "sha256": digest.hexdigest()}


def asset_check(manifest: Path, output: Path) -> None:
    from rlinf.envs.libero.utils import benchmark
    plan = json.loads(manifest.read_text())
    records = []
    for episode in plan["episodes"]:
        suite = benchmark.get_benchmark(episode["suite"])()
        task = suite.get_task(episode["task"])
        bddl = Path(suite.get_task_bddl_file_path(episode["task"]))
        init = Path(benchmark.get_libero_path("init_states")) / task.problem_folder / task.init_states_file
        states = suite.get_task_init_states(episode["task"])
        if not 0 <= episode["seed"] < len(states):
            raise ValueError(f"missing official initial state: {episode}")
        records.append({"episode": episode, "bddl": identity(bddl), "init": identity(init), "trials": len(states)})
    output.write_text(json.dumps(records, indent=2) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path)
    parser.add_argument("--source", type=Path)
    parser.add_argument("--preparation", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--assets", type=Path)
    args = parser.parse_args()
    if args.assets:
        asset_check(args.assets.resolve(strict=True), args.output)
        return
    root = args.root.resolve(strict=True)
    source = args.source.resolve(strict=True)
    prep = args.preparation.resolve(strict=True)
    index = json.loads((prep / "manifest.json").read_text())
    files = []
    for record in index["files"]:
        path = Path(record["path"])
        if not path.is_absolute():
            raise ValueError(f"relative smoke plan path: {path}")
        actual = identity(path)
        if actual["sha256"] != record["sha256"]:
            raise ValueError(f"changed smoke manifest: {path}")
        files.append(actual)
    rd = root.parent / "rd_instruction_20260923"
    resources = [root / ".venv/bin/python", root / "runtime_config/config.yaml",
                 root / "assets/sam3/sam3.pt", root / "assets/pi05",
                 rd / "v31_package_decider_2048_socket_20260925a/parallel_schema.py",
                 rd / "v31_package_decider_2048_socket_20260925a/tokenizer_config.json",
                 rd / "v5r_20261001/qualified_service_sources_bf097673/v5r_server.py",
                 rd / "v5_models/qwen3_5_4b_851bf6e8/config.json",
                 rd / "v5r_20261001/v5_main_job3088/candidate_step750/pytorch_model.bin"]
    # Large weights have a registered identity checked by the service. Avoid
    # hashing the same 8 GB eight times; existence is still checked on CPU.
    checked_resources = [{"path": str(p.resolve(strict=True)), "bytes": p.stat().st_size} for p in resources]
    files.extend(identity(source / name) for name in (
        "harness_v5_eval.py", "v5_batch_eval.py", "robots/libero/v5_runtime.py",
        "robots/libero/v5_state.py", "robots/libero/v5_recovery.py",
        "robots/libero/v5_action_effect.py", "robots/libero/v5_subtasks.py",
        "scripts/run_v5_runtime536_smoke20.sbatch"))
    part = int(os.environ.get("SLURM_ARRAY_TASK_ID", "0"))
    for cohort, kind in (("original", "standard"), ("development", "pro")):
        env = dict(os.environ, LIBERO_TYPE=kind)
        subprocess.run([sys.executable, str(Path(__file__).resolve()),
                        "--assets", str(prep / f"{cohort}_part{part}.json"),
                        "--output", str(args.output.with_name(f"assets_{cohort}.json"))], env=env, check=True)
    args.output.write_text(json.dumps({"passed": True, "files": files, "resources": checked_resources}, indent=2) + "\n")


if __name__ == "__main__":
    main()
