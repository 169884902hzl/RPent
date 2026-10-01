"""Export actual and auxiliary long requests from one explicit source manifest."""

import argparse
import hashlib
import json
import sys
from pathlib import Path


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
    manifest = json.loads(args.manifest.read_text())
    args.output.mkdir(parents=True, exist_ok=False)
    requests = {}
    descriptors = [(d, "actual_request_or_independent_receipt_state") for d in manifest["source_files"]]
    descriptors += [(d, "labeled_auxiliary_request") for d in manifest["files"] + manifest["validation_files"]
                    if d["bucket"] == "auxiliary"]
    for descriptor, source_type in descriptors:
        path = Path(descriptor["path"])
        assert sha(path) == descriptor["sha256"]
        lines = path.read_text().splitlines()
        assert len(lines) == descriptor["rows"]
        for line_no, line in enumerate(lines, 1):
            raw = json.loads(line)
            request = raw["request"]
            key = hashlib.sha256(json.dumps(request, ensure_ascii=False,
                    separators=(",", ":"), allow_nan=False).encode()).hexdigest()
            if key in requests:
                continue
            q = request["questions"]["action"]
            schema = {"action": {"type": "enum", "description": q["instructions"],
                      "choices": list(q["criteria"]), "choice_descriptions": q["criteria"]}}
            prepared = parallel_schema.prepare_prompts(tokenizer, request["state"], schema, 3072)
            requests[key] = {"request": request, "request_sha256": key,
                "prompt_tokens": len(prepared.full_ids[0]), "source_type": source_type,
                "source_file": str(path), "source_file_sha256": descriptor["sha256"],
                "source_line": line_no, "not_for_training": True}
    ordered = sorted(requests.values(), key=lambda r: (-r["prompt_tokens"], r["request_sha256"]))
    files = []
    for name, rows in (("longest128", ordered[:128]),
                       ("over2048", [r for r in ordered if r["prompt_tokens"] > 2048])):
        path = args.output / (name + ".jsonl")
        path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows))
        files.append({"path": str(path), "sha256": sha(path), "rows": len(rows)})
    report = {"purpose": "supplement to existing job2846 memory probe; no new GPU job",
        "input_manifest": str(args.manifest), "input_manifest_sha256": sha(args.manifest),
        "source_script_sha256": sha(__file__), "request_count": len(ordered),
        "token_max": ordered[0]["prompt_tokens"],
        "actual_or_receipt_max": max(r["prompt_tokens"] for r in ordered
                    if r["source_type"] != "labeled_auxiliary_request"),
        "over2048": sum(r["prompt_tokens"] > 2048 for r in ordered),
        "files": files, "training_started": False, "GPU_smoke_completed": False}
    (args.output / "manifest.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report))


if __name__ == "__main__":
    main()
