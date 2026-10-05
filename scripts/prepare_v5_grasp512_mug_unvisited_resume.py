"""Continue only unvisited registered mug states after private metrology failure."""

import argparse
import ast
import copy
from collections import Counter
import hashlib
import json
from pathlib import Path
import shutil
import subprocess


def identity(path):
    return {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def without_contact_sample(text):
    tree = ast.parse(text)
    tree.body = [node for node in tree.body if not (isinstance(node, ast.FunctionDef) and node.name == "contact_sample")]
    return ast.dump(tree)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--original-manifest", type=Path, required=True)
    parser.add_argument("--visited-ledger", type=Path, required=True)
    parser.add_argument("--expected-ledger-sha", required=True)
    parser.add_argument("--original-source", type=Path, required=True)
    parser.add_argument("--patched-truth", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--launcher", type=Path, required=True)
    args = parser.parse_args()
    assert identity(args.visited_ledger)["sha256"] == args.expected_ledger_sha
    raw = args.visited_ledger.read_bytes()
    assert raw.endswith(b"\n"), "preserved ledger has an incomplete tail"
    visited = [json.loads(line) for line in raw.splitlines()]
    original = json.loads(args.original_manifest.read_text())
    cases = original["cases"][3::4]
    assert len(cases) == 100 and {case["group"] for case in cases} == {"mug"}
    originals = {case["name"]: case for case in cases}
    assert len(originals) == 100
    seen = set()
    for row in visited:
        name = row["case"]["name"]
        assert name not in seen and row["case"] == originals[name]
        seen.add(name)
    # The failed final state executed contact despite having no choices line.
    # Every visited state stays excluded, regardless of its outcome or truth.
    assert len(visited) == 21 and len(visited[-1]["contact_samples"]) == 40
    assert visited[-1]["true_sustained_grasp"] is None
    pending = [case for case in cases if case["name"] not in seen]
    assert len(pending) == 79 and not seen & {case["name"] for case in pending}
    assert not args.output.exists() and not args.source.exists()
    args.output.mkdir(parents=True)
    shutil.copytree(args.original_source, args.source, symlinks=True)
    truth = args.source / "robots/libero/v5_grasp_truth.py"
    old_text, new_text = truth.read_text(), args.patched_truth.read_text()
    assert without_contact_sample(old_text) == without_contact_sample(new_text), "patch changed more than private contact sampling"
    truth.write_text(new_text)
    difference = subprocess.run(["diff", "-qr", str(args.original_source), str(args.source)], text=True, capture_output=True)
    changes = difference.stdout.strip().splitlines()
    assert difference.returncode == 1 and len(changes) == 1 and "robots/libero/v5_grasp_truth.py" in changes[0], changes
    plan = copy.deepcopy(original)
    plan.update(purpose="unvisited remainder of frozen mug confirmation; no visited state repeated",
                cases=pending, parent_manifest=identity(args.original_manifest),
                original_distribution=original.get("distribution"),
                distribution=dict(Counter(case["group"] for case in pending)),
                resume_private_instrument_only={
                    "original_job": "3631", "visited_ledger": identity(args.visited_ledger),
                    "visited_states_preserved": len(visited), "known_complete": 20,
                    "executed_contact_instrument_unknown": [visited[-1]["case"]["name"]],
                    "excluded_all_visited_states": sorted(seen), "remaining_unvisited": len(pending),
                    "same_case_bytes": True, "recipe_changed": False,
                    "qualification_pending_unknown": True, "new_training_rows": 0})
    manifest = args.output / "resume.json"
    manifest.write_text(json.dumps(plan, indent=2) + "\n")
    archive = args.output / "source512.tar"
    subprocess.run(["tar", "--sort=name", "--mtime=UTC 1970-01-01", "--owner=0", "--group=0",
                    "--numeric-owner", "-cf", str(archive), "-C", str(args.source), "."], check=True)
    registration = {"purpose": plan["purpose"], "original_manifest": identity(args.original_manifest),
                    "visited_ledger": identity(args.visited_ledger), "resume_manifest": identity(manifest),
                    "visited": 21, "remaining_unvisited": 79, "instrument_unknown_retained": visited[-1]["case"]["name"],
                    "original_shard_index": 3, "original_shards": 4, "run_shard_index": 0, "run_shards": 1,
                    "source": str(args.source), "patched_truth": identity(truth), "source_difference": changes,
                    "source_archive": identity(archive), "launcher": identity(args.launcher),
                    "public_recipe_changed": False, "already_executed_replayed": False}
    path = args.output / "registration.json"
    path.write_text(json.dumps(registration, indent=2) + "\n")
    print(json.dumps({"registration": identity(path), "manifest": identity(manifest),
                      "source_archive": identity(archive), "patched_truth": identity(truth),
                      "visited": 21, "known_complete": 20, "remaining_unvisited": 79}, indent=2))


if __name__ == "__main__":
    main()
