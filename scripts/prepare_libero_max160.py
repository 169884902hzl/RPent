"""Select the preregistered MAX sample without reading policy outcomes."""

import argparse
import hashlib
import json
import random
from collections import Counter
from pathlib import Path


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def prepare(registration_path, output):
    registration = json.loads(registration_path.read_bytes())
    source_path = Path(registration["source_manifest"]["path"])
    if digest(source_path) != registration["source_manifest"]["sha256"]:
        raise ValueError("registered Lite manifest changed")
    source = json.loads(source_path.read_bytes())
    cases = source["cases"]
    if len(cases) != 800 or len({c["case_id"] for c in cases}) != 800:
        raise ValueError("Lite must contain 800 unique pairs")
    events = sorted({c["scenario"]["change_type"] for c in cases})
    if len(events) != registration["events_expected"]:
        raise ValueError("event coverage differs from preregistration")
    rng = random.Random(registration["selection_seed"])
    selected = []
    for event in events:
        for track in ("plus", "pro"):
            pool = sorted((c for c in cases
                           if c["scenario"]["change_type"] == event
                           and ("pro" if c.get("substrate_variant", {}).get("benchmark")
                                == "LIBERO-PRO" else "plus") == track),
                          key=lambda c: c["case_id"])
            selected.extend(rng.sample(pool, registration["per_event_source_quotas"][track]))
    if len(selected) != registration["total_pairs"]:
        raise ValueError("selected pair count differs from preregistration")
    counts = Counter(c["scenario"]["change_type"] for c in selected)
    if set(counts.values()) != {registration["per_event"]}:
        raise ValueError("event quotas differ from preregistration")
    output.mkdir(parents=True, exist_ok=False)
    manifest = {**source, "cases": selected}
    manifest["benchmark_id"] = "libero-max-codex3-development160"
    manifest["protocol"] = {**source["protocol"], "profile": "development160",
                            "selection_contract": "20 per event:14Plus+6PRO;seed20261007"}
    manifest_path = output / "selected160.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    for track in ("plus", "pro"):
        subset = [c for c in selected if ("pro" if c.get("substrate_variant", {}).get("benchmark")
                  == "LIBERO-PRO" else "plus") == track]
        (output / (track + ".json")).write_text(json.dumps({**manifest, "cases": subset}, indent=2) + "\n")
    summary = {"registration": {"path": str(registration_path), "sha256": digest(registration_path)},
               "source_manifest": registration["source_manifest"],
               "sampler_sha256": digest(Path(__file__)),
               "selected_manifest": {"path": str(manifest_path), "sha256": digest(manifest_path)},
               "event_counts": dict(counts), "pairs": len(selected),
               "source_counts": dict(Counter("pro" if c.get("substrate_variant", {}).get("benchmark")
                                             == "LIBERO-PRO" else "plus" for c in selected)),
               "selected_case_ids": [c["case_id"] for c in selected],
               "all_case_metadata_unchanged": all(c in cases for c in selected),
               "policy_results_read": False, "physical_pairs_executed": 0,
               "training_allowed": False, "manual_allowed": False, "memory_allowed": False}
    (output / "manifest.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps({k: v for k, v in summary.items() if k != "selected_case_ids"}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--registration", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    prepare(args.registration.resolve(), args.output.resolve())
