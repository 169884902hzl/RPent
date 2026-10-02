# Copyright 2026 Zhilun Hu.
# SPDX-License-Identifier: Apache-2.0
"""Read hash-pinned RPent files for evaluation; never select files by scanning."""

import hashlib
import json
from pathlib import Path


def read_original_files(index: Path) -> tuple[str, dict]:
    """Keep original file content intact, with its identity outside the state."""
    data = json.loads(index.read_text())
    if data.get("evaluation_only") is not True or data.get("training_allowed") is not False:
        raise ValueError("RPent original files require an evaluation-only index")
    texts = []
    files = []
    for item in data["files"]:
        path = Path(item["path"])
        payload = path.read_bytes()
        digest = hashlib.sha256(payload).hexdigest()
        if digest != item["sha256"]:
            raise ValueError("RPent original memory file changed")
        texts.append("FILE " + item["name"] + "\n" + payload.decode("utf-8"))
        files.append({"name": item["name"], "sha256": digest, "bytes": len(payload)})
    return "\n\n".join(texts), {
        "index_sha256": hashlib.sha256(index.read_bytes()).hexdigest(),
        "files": files,
        "content_transformed": False,
        "content_truncated": False,
        "delivery": "Original matched task files in a separate system message; no planner retrieval tools",
        "missing_files": data.get("missing_files", []),
        "evaluation_only": True,
    }
