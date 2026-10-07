"""Extract identities only from six hash-pinned explicit confirmation plans."""

import argparse
import hashlib
import json
from pathlib import Path

ROOT = "/public/home/sunyihan/rpent_libero_eval/results/harness_v5/"
SOURCES = [
    ("grasp492_first4_confirmation_20261005/preparation/full.json", "dfa8c31e0568d52e9ffb19ca4d7d338284eb08460aa6424e523d9fe012a67ac9", "independent_confirmation_first_four_classes"),
    ("grasp512_mug_unvisited_resume_20261005/preparation/resume.json", "f3a73d239a9b1bfcdd2ec9610aeb202ba57a48e1e745eedb8756e34be867c975", "independent_confirmation_first_four_classes"),
    ("grasp510_box_remaining_20261005/preparation/remaining52.json", "cd93583d546deb434c6233ab57367f8c510098ac3e8430b88478a33290a6f48a", "remaining_unexecuted_box_confirmation"),
    ("grasp535_remaining_confirmation_CPU_20261005/frypan/full.json", "92f6a9cc86135361ba8dedb6bfb4be40d562ad547cd6591d311e22d4e0f86887", "independent_confirmation_remaining_class"),
    ("grasp535_remaining_confirmation_CPU_20261005/moka_pot/full.json", "ef7e22819cde9a9d12e627663df842d86f5c2aaf97bba4f9c1f482d4aabb106e", "independent_confirmation_remaining_class"),
    ("pan556_coupled_lift_confirmation100_CPU_20261006/preparation/pan_coupled_lift_confirmation100.json", "32e11afe73db40727b6f9574e68be2127033c4fdd47f7ea355b3debe23987737", "original_pan_coupled_lift_confirmation100_registered_resets"),
]
AMBIGUOUS = [
    ("skill535_articulate_place_confirmation_20261005/preparation/fixtures.json", "ffb890d894609f3046e88832a33189053a50bb66c6ca333aca6c4c6d98585645"),
    ("skill535_articulate_place_confirmation_20261005/preparation/place.json", "d9c39247883a38e8587364e0bd9c9d73a87f720f866bea7e70c767077c53dc35"),
]


def pinned(path, digest):
    data = Path(path).read_bytes()
    if hashlib.sha256(data).hexdigest() != digest:
        raise ValueError(f"registered file changed: {path}")
    return json.loads(data)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(exist_ok=False, parents=True)
    by_identity = {}
    sources = []
    for relative, digest, cohort in SOURCES:
        path = ROOT + relative
        plan = pinned(path, digest)
        if plan.get("cohort") != cohort or plan.get("not_reserved") is True:
            raise ValueError(f"expected actual registered confirmation cohort: {path}")
        reference = {"path": path, "sha256": digest, "cohort": cohort}
        unique = set()
        for case in plan["cases"]:
            episode = {key: case["episode"][key] for key in ("suite", "task", "seed")}
            state_sha = case["state_sha256"]
            if len(state_sha) != 64 or any(c not in "0123456789abcdef" for c in state_sha):
                raise ValueError(f"invalid state SHA: {case['name']}")
            key = (*episode.values(), state_sha)
            unique.add(key)
            record = by_identity.setdefault(key, {"episode": episode, "state_sha256": state_sha,
                "permanent_training_exclusion": True, "registration_refs": []})
            refs = record["registration_refs"]
            existing = next((ref for ref in refs if ref["path"] == path), None)
            if existing is None:
                existing = {**reference, "registered_cases": []}
                refs.append(existing)
            if case["name"] not in existing["registered_cases"]:
                existing["registered_cases"].append(case["name"])
        sources.append({**reference, "registered_case_rows": len(plan["cases"]), "distinct_identities": len(unique)})
    ambiguous = []
    ambiguous_identities = {}
    for relative, digest in AMBIGUOUS:
        path = ROOT + relative
        plan = pinned(path, digest)
        ambiguous.append({"path": path, "sha256": digest, "cohort": plan.get("cohort"),
            "confirmation_declaration": plan.get("confirmation"), "case_rows": len(plan["cases"]),
            "reason": "manifest declares independent confirmation, while current launcher uses selection; registration role unresolved",
            "not_admitted_to_this_registry": True})
        for case in plan["cases"]:
            episode = {key: case["episode"][key] for key in ("suite", "task", "seed")}
            key = (*episode.values(), case["state_sha256"])
            record = ambiguous_identities.setdefault(key, {"episode": episode,
                "state_sha256": case["state_sha256"], "training_allowed": False,
                "permanent_training_exclusion": False, "registration_refs": []})
            reference = {"path": path, "sha256": digest}
            if reference not in record["registration_refs"]:
                record["registration_refs"].append(reference)
    hold = args.output / "ambiguous_training_hold_identities.json"
    hold.write_text(json.dumps({"version": "libero_ambiguous_registration_training_hold/1",
        "reason": "10/06 user calls these selection batches; legacy confirmation declaration conflicts; Codex1 must clarify protocol metadata without outcomes before future collection",
        "permanent_confirmation_exclusion": False, "training_allowed": False,
        "records": sorted(ambiguous_identities.values(), key=lambda r: (*r["episode"].values(), r["state_sha256"]))}, indent=2) + "\n")
    hold_ref = {"path": str(hold), "sha256": hashlib.sha256(hold.read_bytes()).hexdigest(),
                "distinct_identities": len(ambiguous_identities)}
    gaps = [
        "Only these six explicit registered plans were extracted; no claim of complete historical confirmation coverage.",
        "Two skill535 articulate/place plans have conflicting confirmation/selection registration and need an explicit role decision.",
        "grasp495/497 and other historical confirmation registrations are not located in this pass.",
        "skill544 pool_only/not_reserved states and layout union100 base tuples are not automatically excluded as confirmations.",
        "Six distinct place4311 development identities are separately excluded by their diagnostic registry, not relabelled as confirmations.",
    ]
    records = sorted(by_identity.values(), key=lambda row: (*row["episode"].values(), row["state_sha256"]))
    result = {"version": "libero_official_confirmation_exclusions/1", "training_allowed": False,
        "coverage_complete": False, "records": records, "registration_sources": sources,
        "gaps": gaps, "ambiguous_registration": ambiguous, "ambiguous_training_hold": hold_ref,
        "outcome_records_read": False, "no_artifacts_directory_discovery": True,
        "producer": {"path": str(Path(__file__).resolve()), "sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}}
    path = args.output / "official_confirmation_exclusions.json"
    path.write_text(json.dumps(result, indent=2) + "\n")
    report = {"registry": {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()},
        "registered_rows": sum(s["registered_case_rows"] for s in sources), "distinct_episode_state_identities": len(records),
        "distinct_state_sha256": len({r["state_sha256"] for r in records}), "sources": sources,
        "coverage_complete": False, "ambiguous_registration": ambiguous,
        "ambiguous_training_hold": hold_ref, "gaps": gaps}
    (args.output / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report))


if __name__ == "__main__":
    main()
