"""Convert explicit measured counts to v5r bands without touching raw evidence."""

import argparse
import collections
import copy
import hashlib
import json
import sys
from pathlib import Path

from robots.libero.v5_progress import PROGRESS_CHOICES, PROGRESS_QUESTION, measured_progress
import shared_v5r_schema as shared


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--choice-package", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    from transformers import AutoTokenizer
    sys.path.insert(0, str(args.choice_package))
    import parallel_schema
    tokenizer = AutoTokenizer.from_pretrained(args.choice_package, local_files_only=True)
    source = json.loads(args.manifest.read_text())
    args.output.mkdir(parents=True, exist_ok=False)
    rows, levels, tokens = [], collections.Counter(), []
    for descriptor in source["files"]:
        if descriptor["bucket"] != "auxiliary":
            continue
        path = Path(descriptor["path"])
        assert sha(path) == descriptor["sha256"]
        for line in path.read_text().splitlines():
            row = json.loads(line)
            if row["question_type"] == "progress":
                evidence = row["label_evidence"]
                answer, measured = measured_progress(evidence["satisfied_count"], evidence["total_count"])
                updated = shared.auxiliary(row, "progress", PROGRESS_QUESTION, PROGRESS_CHOICES,
                                           {answer: 1.0}, measured)
                result = copy.deepcopy(row)
                for key in ("request", "target", "option_names", "acceptable_actions", "evaluated_actions",
                            "unknown_actions", "judge", "label_evidence"):
                    result[key] = updated[key]
                result["progress_conversion"] = {"original_evidence": evidence, "source_file": str(path),
                                                 "source_sha256": descriptor["sha256"],
                                                 "script_sha256": sha(__file__)}
                assert result["request"]["state"].encode() == row["request"]["state"].encode()
                assert result["base_request_sha256"] == row["base_request_sha256"]
                row = result
                levels[answer] += 1
            _, prepared = shared.prepare_example(row, tokenizer, parallel_schema, limit=3072)
            row["prompt_tokens"] = len(prepared.full_ids[0])
            tokens.append(row["prompt_tokens"])
            rows.append(row)
    path = args.output / "auxiliary.jsonl"
    path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows))
    report = {**source, "upstream_manifest": str(args.manifest), "upstream_manifest_sha256": sha(args.manifest),
              "files": [d for d in source["files"] if d["bucket"] != "auxiliary"] + [{
                  "bucket": "auxiliary", "path": str(path), "sha256": sha(path), "rows": len(rows)}],
              "progress_bands": PROGRESS_CHOICES, "progress_counts": dict(levels),
              "progress_conversion_script_sha256": sha(__file__),
              "auxiliary_token_max": max(tokens), "full_training_admission": False}
    (args.output / "manifest.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"auxiliary_rows": len(rows), "progress_counts": dict(levels),
                      "max_tokens": max(tokens), "manifest_sha256": sha(args.output / "manifest.json")}))


if __name__ == "__main__":
    main()
