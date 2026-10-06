"""Hash canonical artifacts for explicitly registered public measurement steps."""

import hashlib
import json
from pathlib import Path
import sys


def main():
    source, destination = map(Path, sys.argv[1:])
    plan = json.loads(source.read_text())
    count = 0
    for case in plan["cases"]:
        for cameras in case["frames"].values():
            for files in cameras.values():
                for ref in files.values():
                    path = Path(ref["path"])
                    if not path.is_absolute() or not path.is_file():
                        raise ValueError("explicit saved public artifact absent: " + str(path))
                    ref["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
                    ref["bytes"] = path.stat().st_size
                    count += 1
    plan["canonical_artifact_path_rule"] = "recorded attempt output/name/{source_step:02d}{suffix}; no directory scan"
    plan["public_file_count"] = count
    destination.write_text(json.dumps(plan, indent=2, allow_nan=False) + "\n")
    print(json.dumps({"explicit_public_files": count, "manifest_sha256": hashlib.sha256(destination.read_bytes()).hexdigest()}))


if __name__ == "__main__":
    main()
