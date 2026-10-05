"""Select the first registered case in each skill/arm, without reading outcomes."""

import argparse
import copy
import hashlib
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    raw = args.manifest.read_bytes()
    plan = json.loads(raw)
    seen, selected = set(), []
    for case in plan["cases"]:
        identity = (case["type"], case["condition"])
        if identity not in seen:
            selected.append(case)
            seen.add(identity)
    smoke = copy.deepcopy(plan)
    smoke.update(cases=selected, purpose="first registered case per type/arm development smoke; no qualification",
                 parent_manifest={"path": str(args.manifest), "sha256": hashlib.sha256(raw).hexdigest()},
                 selection="first case in parent order; no outcomes read", qualification_authorized=False)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x") as output:
        output.write(json.dumps(smoke, indent=2) + "\n")
    print(json.dumps({"path": str(args.output), "rows": len(selected),
                      "sha256": hashlib.sha256(args.output.read_bytes()).hexdigest()}))


if __name__ == "__main__":
    main()
