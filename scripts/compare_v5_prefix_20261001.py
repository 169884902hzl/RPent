# Copyright 2026 Zhilun Hu.
# SPDX-License-Identifier: Apache-2.0
"""Compare two explicit cumulative prefixes without discovering data files."""

from __future__ import annotations

import argparse
import collections
import hashlib
import json
from pathlib import Path


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def read_rows(manifest):
    rows = {}
    for descriptor in manifest["files"]:
        if descriptor["bucket"] not in ("train", "auxiliary"):
            continue
        path = Path(descriptor["path"])
        data = path.read_bytes()
        assert hashlib.sha256(data).hexdigest() == descriptor["sha256"]
        lines = data.splitlines()
        assert len(lines) == descriptor["rows"]
        for raw in lines:
            row = json.loads(raw)
            key = (row["scene_id"], row["stage"], row["step"],
                   row["question_type"], digest(row["request"]))
            if key in rows:
                raise ValueError(f"duplicate source decision/question: {key}")
            rows[key] = row
    return rows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--old", type=Path, required=True)
    parser.add_argument("--new", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    old, new = [json.loads(p.read_text()) for p in (args.old, args.new)]
    before, after = read_rows(old), read_rows(new)
    fields = ("request", "acceptable_actions", "evaluated_actions", "unknown_actions",
              "judge", "schema_version", "serialization_version", "prompt_tokens",
              "source_hashes", "init_state_sha256", "instruction_sha256", "split", "bucket")
    missing = [key for key in before if key not in after]
    changes = [
        {"key": key, "changed_fields": [field for field in fields
                                          if row.get(field) != after[key].get(field)]}
        for key, row in before.items() if key in after
        and any(row.get(field) != after[key].get(field) for field in fields)
    ]
    extra = [row for key, row in after.items() if key not in before]
    old_validation = {(d["path"], d["sha256"], d["rows"]) for d in old["validation_files"]}
    new_validation = {(d["path"], d["sha256"], d["rows"]) for d in new["validation_files"]}
    summary = {
        "purpose": "cumulative prefix preservation and actual increment; not training admission",
        "old_manifest": str(args.old), "new_manifest": str(args.new),
        "old_sha256": hashlib.sha256(args.old.read_bytes()).hexdigest(),
        "new_sha256": hashlib.sha256(args.new.read_bytes()).hexdigest(),
        "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "old_rows": len(before), "new_rows": len(after),
        "missing_old_rows": missing, "changed_old_rows": changes,
        "additional_rows": len(extra),
        "additional_by_question": dict(collections.Counter(r["question_type"] for r in extra)),
        "additional_by_task": dict(collections.Counter(str((r["suite"], r["task_id"])) for r in extra)),
        "validation_descriptor_changes": len(old_validation ^ new_validation),
        "full_training_admission": False,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(summary, indent=2) + "\n")
    assert not missing and not changes and old_validation == new_validation
    print(json.dumps({k: v for k, v in summary.items() if k not in ("missing_old_rows", "changed_old_rows")}))


if __name__ == "__main__":
    main()
