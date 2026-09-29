"""Audit explicitly named development traces; never discover training inputs."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path


def main() -> None:
    """Check the real wire requests and export measured smoke evidence."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--trace", type=Path, required=True)
    parser.add_argument("--result", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    records = [json.loads(line) for line in args.trace.read_text().splitlines() if line]
    result = json.loads(args.result.read_text())
    summary = []
    for record in records:
        request = record["request"]
        text = json.dumps(request)
        assert not re.search(r"\b(?:obj_|zone_|akita_|glazed_)", text)
        assert "BDDL" not in text
        assert 0 < record["prompt_tokens"] <= 2048
        assert len(request["options"]) <= 24
        assert not any(
            x.startswith(("segment(", "back_project(")) for x in request["options"]
        )
        entity_lines = [
            line for line in request["context"].splitlines() if line.startswith("e ")
        ]
        assert entity_lines
        assert all(
            "xyz_cm=" in line
            and "size_cm=" in line
            and "src=perception" in line
            and re.match(r"e e\d+ ", line)
            for line in entity_lines
        )
        assert request["context"].count("\nreceipt ") <= 3
        summary.append(
            {
                k: record[k]
                for k in (
                    "decision",
                    "prompt_tokens",
                    "selected",
                    "receipt",
                    "official_success",
                    "timing_s",
                )
            }
        )
    args.output.write_text(
        json.dumps(
            {
                "mode": "engineering-smoke-only",
                "wire_checks_passed": True,
                "request_count": len(records),
                "qualified_training_rows": 0,
                "oracle_gate_passed": False,
                "result": result,
                "decisions": summary,
                "files": {
                    str(p): hashlib.sha256(p.read_bytes()).hexdigest()
                    for p in (args.trace, args.result)
                },
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
