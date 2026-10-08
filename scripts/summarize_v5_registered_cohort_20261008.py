"""Close a pinned development cohort, including its retained startup episode."""

import argparse
from collections import defaultdict
import json
from pathlib import Path

from pair_v5_current_cohorts_20261008 import pair
from summarize_v5_interim80_once_20261008 import (
    annotate, group_report, key, pinned, read_rows, ref,
)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--preparation", type=Path, required=True)
    parser.add_argument("--cohort-root", type=Path, required=True)
    parser.add_argument("--cohort", required=True)
    parser.add_argument("--startup-job", required=True)
    parser.add_argument("--array-job", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--previous", action="append", type=Path, default=[])
    args = parser.parse_args()
    preparation = args.preparation.resolve(strict=True)
    index_path = preparation / "manifest.json"
    index = json.loads(index_path.read_text())
    plans = [json.loads(pinned(item).read_text()) for item in index["files"]
             if Path(item["path"]).name.startswith(args.cohort + "_part")]
    episodes = [e for plan in plans for e in plan["episodes"]]
    expected = {key(e) for e in episodes}
    if len(expected) != len(episodes):
        raise ValueError("duplicate registered cohort identity")
    base = args.cohort_root.resolve(strict=True) / args.cohort
    contract_path = base / f"startup_preflight/job{args.startup_job}/part0/startup_contract.json"
    contract = json.loads(contract_path.read_text())
    if contract["status"] != "pass" or not contract.get("physical_actions"):
        raise ValueError("missing actual same-source/launcher physical startup")
    if contract["manifest_index_sha256"] != ref(index_path)["sha256"]:
        raise ValueError("startup preparation identity differs")
    ledgers = [pinned(contract["episodes"]),
               *sorted((base / f"job{args.array_job}").glob("part*/probe/episodes.jsonl"))]
    seen, rows, by_suite = set(), [], defaultdict(list)
    for ledger in ledgers:
        ledger_ref = ref(ledger)
        for raw in read_rows(ledger):
            identity = key(raw["episode"])
            if identity not in expected or identity in seen:
                raise ValueError(f"unexpected or duplicate cohort identity: {identity}")
            seen.add(identity)
            row = annotate(raw, ledger_ref, "same_source_startup_or_formal")
            rows.append(row)
            by_suite[identity[0]].append(row)
    if seen != expected:
        raise ValueError(f"cohort incomplete: {len(seen)}/{len(expected)}")
    if any(row["accounting_group"] != "functional" for row in rows):
        raise ValueError("unresolved infrastructure outcomes; preserve and repair before closing")
    rows.sort(key=lambda row: key(row["episode"]))
    summary = {"cohort": args.cohort, "metric": "official native physical success",
               "total": group_report(rows, len(expected)),
               "by_suite": {name: group_report(items, sum(e["suite"] == name for e in episodes))
                            for name, items in sorted(by_suite.items())},
               "correct_finish_secondary": sum(r["result"].get("correct_finish") is True for r in rows),
               "non_successes": [row for row in rows if row["result"].get("official_success") is not True],
               "behavior_frozen": False, "evidence_role": "interim development; no skill confirmation",
               "source_commit": index["source_commit"], "source_path": index["source_path"]}
    paired = {}
    for previous in args.previous:
        payload = json.loads(previous.read_text())
        if isinstance(payload, list):
            historical = payload
        else:
            historical = payload.get("effective_rows", payload.get("episodes"))
        if historical is None:
            raise ValueError("previous summary has no indexed episode rows")
        paired[str(previous)] = pair(historical, rows, str(previous))
    args.output.mkdir(parents=True, exist_ok=False)
    paths = []
    for filename, value in (("summary.json", summary), ("paired.json", paired)):
        path = args.output / filename
        path.write_text(json.dumps(value, indent=2) + "\n")
        paths.append(path)
    path = args.output / "episodes.jsonl"
    path.write_text("".join(json.dumps(row) + "\n" for row in rows))
    paths.append(path)
    manifest = {"generator": ref(__file__), "source_snapshot": index["source_snapshot"],
                "inputs": [ref(index_path), ref(contract_path), *map(ref, ledgers), *map(ref, args.previous)],
                "outputs": list(map(ref, paths)), "training_allowed": False}
    (args.output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps({"total": summary["total"], "by_suite": summary["by_suite"],
                      "manifest": ref(args.output / "manifest.json")}))


if __name__ == "__main__":
    main()
