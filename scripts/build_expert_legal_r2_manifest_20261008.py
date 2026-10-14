#!/usr/bin/env python3
"""Materialize the registered legal-r2 expert remainder and error retries.

The 200-episode registration and prior physical ledger are immutable.  This
script only emits the 24 identities explicitly marked unattempted and the six
one-time retries for the recorded program-error identities.  It never reads
or rewrites prior result rows.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


REMAINDER = [
    ("libero_10", 4, 3), ("libero_10", 3, 1), ("libero_10", 1, 4),
    ("libero_goal", 5, 0), ("libero_10", 7, 4), ("libero_10", 6, 2),
    ("libero_10", 5, 0), ("libero_10", 7, 3), ("libero_goal", 6, 3),
    ("libero_10", 9, 2), ("libero_goal", 5, 1), ("libero_10", 8, 0),
    ("libero_goal", 3, 4), ("libero_10", 6, 3), ("libero_10", 9, 1),
    ("libero_goal", 8, 1), ("libero_goal", 6, 4), ("libero_10", 9, 3),
    ("libero_goal", 5, 2), ("libero_10", 8, 1), ("libero_goal", 9, 4),
    ("libero_10", 8, 2), ("libero_goal", 7, 0), ("libero_10", 9, 4),
]

PROGRAM_RETRIES = [
    {"suite": "libero_10", "task": 0, "seed": 2, "error": "StopIteration",
     "result_sha256": "d586ec2e5c0497a995b9af3f0fa8fb68279afc326500f30739436f698fbcbc0a",
     "choices_sha256": "580daff93092645eaaa08efb8544cb3f92986ba47cc46bb139bb91c797833724"},
    {"suite": "libero_object", "task": 7, "seed": 3,
     "error": "ValueError: Candidate(tool='ask_help', object=None, target=None, mode=None) is not in list",
     "result_sha256": "29dcb387eef410247ef7ec68aeed913ea3d496645845369283c469d2b1b00209",
     "choices_sha256": "9951a70c225ce4e2b005283f5239349e5d6cfa428489d7d515d66607963f8aaf"},
    {"suite": "libero_object", "task": 9, "seed": 1, "error": "StopIteration",
     "result_sha256": "4f3c07ab4ced520e66f2e27ffa2a1e8e6196eefdb68b11f6dc81e7ae6fefc466",
     "choices_sha256": "d85812d0d7a29a6dc542fec077916139fa06852d32ceb61eeb4835c3494f5c4a"},
    {"suite": "libero_10", "task": 2, "seed": 1, "error": "StopIteration",
     "result_sha256": "c4637bfb6d843e7e612187168fdd144dd70a4a1a282f601b65b670ac5eebff78",
     "choices_sha256": "929fddb4c2d515a72ee4f8969fb0d710171473b589a661e0fcee2e4f1530505f"},
    {"suite": "libero_10", "task": 0, "seed": 4,
     "error": "ValueError: Candidate(tool='ask_help', object=None, target=None, mode=None) is not in list",
     "result_sha256": "39124be2290fad365057812f90833c435635044e9a0e3cbc656f44d07dae4371",
     "choices_sha256": "ea8db24e37c71749331b93fd535c696f44a6ed46765a263d6816e737ce496596"},
    {"suite": "libero_object", "task": 8, "seed": 0,
     "error": "ValueError: Candidate(tool='ask_help', object=None, target=None, mode=None) is not in list",
     "result_sha256": "4dbdea68c5ec4427b21947379bb8c2579da43a1761971782dce513550a7fc8a7",
     "choices_sha256": "f62c3ceec6865ed6696faa0101abe02d436fa8907cc372a842a0a5ed947e18c4"},
]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def ref(path: Path) -> dict[str, str]:
    return {"path": str(path.resolve()), "sha256": sha256(path)}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-snapshot", type=Path, required=True)
    parser.add_argument("--template", type=Path,
                        default=Path("results/harness_v5/interim574_20261007/preparation/expert_part0.json"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    source_meta = json.loads((args.source_snapshot / "source_snapshot.json").read_text())
    template = json.loads(args.template.read_text())
    output = args.output.resolve()
    if output.exists():
        raise SystemExit(f"refusing to replace existing manifest directory: {output}")
    output.mkdir(parents=True)
    source_tree = str(args.source_snapshot.resolve())
    source_commit = source_meta["commit"]
    episodes = [{"suite": suite, "task": task, "seed": seed}
                for suite, task, seed in REMAINDER]
    part_refs = []
    for index in range(8):
        payload = dict(template)
        payload.update({"source_path": source_tree, "source_commit": source_commit,
                        "episodes": episodes[index::8], "cohort": "expert",
                        "resume_policy": "unattempted_only",
                        "preserved_attempts": 176,
                        "program_error_retry": False})
        path = output / f"expert_part{index}.json"
        path.write_text(json.dumps(payload, indent=2) + "\n")
        part_refs.append(ref(path))
    retry_path = output / "program_error_retries.json"
    retry_path.write_text(json.dumps({
        "policy": "each original program-error identity may be rerun exactly once",
        "source_commit": source_commit,
        "source_path": source_tree,
        "retries": PROGRAM_RETRIES,
        "original_records_preserved": True,
    }, indent=2) + "\n")
    manifest = {
        "cohort": "expert",
        "registered_episodes": 200,
        "preserved_attempts": 176,
        "planned_unattempted": len(episodes),
        "episodes": episodes,
        "source_snapshot": source_meta,
        "source_path": source_tree,
        "source_commit": source_commit,
        "shards": part_refs,
        "files": part_refs,
        "batch_runner": ref(args.source_snapshot / "v5_batch_eval.py"),
        "launcher": ref(args.source_snapshot / "scripts/run_v5_interim574.sbatch"),
        "runtime_supplement": [ref(args.source_snapshot / "typed_choice_eval.py")],
        "references": [],
        "program_error_retries": ref(retry_path),
        "scheduler_only_cancellation": {
            "job": "4417_6/7",
            "physical_attempts": 0,
            "identity_materialized": False,
            "do_not_infer_episode_count": True,
        },
        "all_previous_physical_records_retained": True,
        "gpu_submitted": False,
    }
    manifest_path = output / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps({"manifest": ref(manifest_path), "shards": 8,
                      "unattempted": len(episodes), "retries": len(PROGRAM_RETRIES)}, indent=2))


if __name__ == "__main__":
    main()
