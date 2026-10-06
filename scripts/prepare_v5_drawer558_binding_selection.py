"""Pin a five-state original development replay for measured drawer binding."""

import argparse
import copy
import hashlib
import json
from pathlib import Path


def ref(path):
    path = Path(path).resolve(strict=True)
    return {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--source-archive", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    for path in (args.input, args.source, args.source_archive, args.output):
        if not path.is_absolute():
            parser.error("all paths must be absolute")
    plan = copy.deepcopy(json.loads(args.input.read_text()))
    if plan["cohort"] != "selection" or plan["qualification_authorized"] is not False:
        raise ValueError("input must be the preserved development selection")
    plan["cases"] = [case for case in plan["cases"] if case["condition"] == "native_original160"]
    if len(plan["cases"]) != 5:
        raise ValueError("expected the same five native original cases")
    plan["conditions"] = {"native_original160": plan["conditions"]["native_original160"]}
    plan["conditions"]["native_original160"]["overrides"]["drawer_current_binding_v4"] = True
    for case in plan["cases"]:
        case["name"] = case["name"].replace("drawer557_", "drawer558_")
    for item in plan["source_snapshot"]["files"]:
        item.update(ref(args.source / item["relative_path"]))
    plan["source_snapshot"].update(path=str(args.source), commit=args.source_commit,
                                   archive=ref(args.source_archive))
    plan.update(version="drawer558-current-measured-part-selection/1", cases_count=5,
                purpose="physical validation of current moving-plane identity with unchanged public gates",
                input_manifest=ref(args.input), producer=ref(Path(__file__)),
                producer_dependencies=[], runtime_default_changed=False,
                state_repetition="same5 previously visited original states; no confirmation admission",
                software_checks={"focused_CPU_passed": 156,
                                 "public_saved_replay": "5/5 fused endpoints, prior4false+1null"})
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x") as handle:
        handle.write(json.dumps(plan, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({"manifest": ref(args.output), "cases": 5, "cohort": "selection"}))


if __name__ == "__main__":
    main()
