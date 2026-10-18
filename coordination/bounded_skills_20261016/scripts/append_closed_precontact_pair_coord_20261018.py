# Copyright 2026 Zhilun Hu.
# SPDX-License-Identifier: Apache-2.0
"""Append the closed development pairs and verify only the new shared-log bytes."""

import fcntl
import hashlib
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


def main() -> None:
    """Deliver the existing source-pinned report without scanning the shared log."""
    base = Path(
        "/public/home/sunyihan/rpent_libero_eval/coordination/bounded_skills_20261016"
    )
    report = base / "progress_closed_precontact_pair_20261018.md"
    raw = (
        f"\n[Codex3 | {datetime.now(ZoneInfo('America/Los_Angeles')).isoformat()}"
        " | closed same-state pairs and original oracle continuation]\n"
        f"Delivery for Codex1/Codex2: {report}\n\n"
        + report.read_text()
        + "\n"
    ).encode()
    path = Path("/public/home/sunyihan/rd_instruction_20260923/COORDINATION.md")
    with path.open("ab") as stream:
        fcntl.flock(stream, fcntl.LOCK_EX)
        stream.seek(0, 2)
        start = stream.tell()
        stream.write(raw)
        stream.flush()
        end = stream.tell()
    with path.open("rb") as stream:
        stream.seek(start)
        if stream.read(len(raw)) != raw:
            raise RuntimeError("Shared coordination append did not match the report")
    receipt = {
        "path": str(path),
        "start": start,
        "end": end,
        "bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "source_report": str(report),
        "source_commit": "ec89f741b4b729b0ac854b7510ec74105a5a13e9",
        "formal_array": "9248",
        "training": False,
        "confirmation": False,
    }
    output = base / "reports/coord_closed_precontact_pair_append_20261018.json"
    output.write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps(receipt))


if __name__ == "__main__":
    main()
