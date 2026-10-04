"""Prepare the registered v6 instruction-only condition from explicit train files."""

import argparse
from collections import Counter
import hashlib
import importlib.util
import json
from pathlib import Path
import random
import sys

import numpy as np

from robots.libero.v6_text import instruction, replace_instruction


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--manifest-sha256", required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--config-sha256", required=True)
    parser.add_argument("--choice-package", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=366)
    args = parser.parse_args()
    if sha(args.manifest) != args.manifest_sha256 or sha(args.config) != args.config_sha256:
        raise ValueError("registered input changed")
    manifest, config = json.loads(args.manifest.read_text()), json.loads(args.config.read_text())
    path = Path(manifest["train"]["path"])
    if sha(path) != manifest["train"]["sha256"]:
        raise ValueError("registered training file changed")
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    for row in rows:
        if (row.get("split") != "train" or row.get("domain") != "libero"
                or not row["scene_id"].startswith("original/") or not 10 <= row["init_state_index"] <= 39):
            raise ValueError("instruction donor outside original training split")
    # Donors come exclusively from the same admitted original training package.
    bank = sorted({(row["suite"], row["task_id"], instruction(row["request"]["state"])) for row in rows})
    rng = random.Random(args.seed)
    selected = set(rng.sample(range(len(rows)), round(.15 * len(rows))))
    schema = Path(config["shared_schema"])
    if sha(schema) != config["shared_schema_sha256"]:
        raise ValueError("registered renderer changed")
    spec = importlib.util.spec_from_file_location("v6_shared_schema", schema)
    shared = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(shared)
    sys.path.insert(0, str(args.choice_package))
    import parallel_schema
    from transformers import AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(args.choice_package, local_files_only=True)
    args.output.mkdir(parents=True, exist_ok=False)
    counts, by_task, tokens = Counter(), {}, []
    train, rejected = args.output / "train.jsonl", args.output / "rejected.jsonl"
    with train.open("x") as kept, rejected.open("x") as failures:
        for index, row in enumerate(rows):
            condition = "normal"
            if index in selected:
                donors = [text for suite, task, text in bank
                          if (suite, task) != (row["suite"], row["task_id"])
                          and text != instruction(row["request"]["state"])]
                if not donors:
                    raise ValueError("no different original training task for instruction swap")
                row = replace_instruction(row, rng.choice(donors))
                condition = "wrong_instruction"
            try:
                _, prepared = shared.prepare_example(row, tokenizer, parallel_schema, limit=3072)
            except ValueError as error:
                if "token" not in str(error).lower() and "3072" not in str(error):
                    raise
                counts["over_token_rejected"] += 1
                failures.write(json.dumps({"source_line": index + 1, "reason": str(error)}) + "\n")
                continue
            row["prompt_tokens"] = len(prepared.full_ids[0])
            if row["prompt_tokens"] > 3072:
                raise ValueError("renderer returned over-limit request")
            row["source_key"]["request_hash"] = shared.digest(row["request"])
            row["image_alignment"]["state_text_sha256"] = hashlib.sha256(row["request"]["state"].encode()).hexdigest()
            counts[condition] += 1
            by_task.setdefault(f"{row['suite']}/{row['task_id']}", Counter())[condition] += 1
            tokens.append(row["prompt_tokens"])
            kept.write(json.dumps(row, ensure_ascii=False) + "\n")
    report = {
        "rule": "instruction_swap_train_only/1", "seed": args.seed,
        "target_fraction": .15, "input_rows": len(rows), "counts": dict(counts),
        "actual_fraction": counts["wrong_instruction"] / max(1, counts["normal"] + counts["wrong_instruction"]),
        "by_task": {k: dict(v) for k, v in by_task.items()},
        "token_p95": float(np.percentile(tokens, 95)) if tokens else None,
        "token_max": max(tokens) if tokens else None,
        "labels_images_candidates_unchanged": True, "model_visible_condition_marker": False,
        "donor_scope": "original training rows init10..39 from explicit input manifest; no PRO/human/sealed/Jev inputs",
        "manifest": {"path": str(args.manifest), "sha256": args.manifest_sha256},
        "train": {"path": str(train), "sha256": sha(train)},
        "rejected": {"path": str(rejected), "sha256": sha(rejected)},
        "schema_sha256": sha(schema), "script_sha256": sha(__file__),
        "shared_corruption_sha256": sha(Path(__file__).resolve().parents[1] / "robots/libero/v6_text.py"),
        "full_training_admission": False,
        "shared_Codex2_implementation_alignment": "implementation published for both domains; pending consumer confirmation",
        "new_independent_decision_states": 0,
    }
    (args.output / "manifest.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({k: report[k] for k in ("counts", "actual_fraction", "token_p95", "token_max")}))


if __name__ == "__main__":
    main()
