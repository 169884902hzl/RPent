#!/usr/bin/env python3
"""Pin the current expert ledgers and prepare exact unattempted/retry cohorts."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def ref(path: Path) -> dict:
    path = path.resolve(strict=True)
    return {"path": str(path), "sha256": digest(path)}


def read_pinned(item: dict) -> dict:
    path = Path(item["path"])
    if not path.is_absolute() or digest(path) != item["sha256"]:
        raise ValueError(f"pinned input changed: {path}")
    return json.loads(path.read_text())


def identity(episode: dict) -> tuple:
    return episode["suite"], int(episode["task"]), int(episode["seed"])


def dump(path: Path, value: dict) -> dict:
    path.write_text(json.dumps(value, indent=2) + "\n")
    return ref(path)


def packet(output: Path, episodes: list, template: dict, index: dict,
           source: dict, references: list, shards: int, audit: dict) -> dict:
    output.mkdir(parents=True, exist_ok=False)
    files = []
    for part in range(shards):
        plan = {**template, "source_path": source["path"],
                "source_commit": source["commit"], "episodes": episodes[part::shards],
                "preserved_attempts": audit["preserved_unique_physical_identities"],
                "resume_policy": audit["policy"], "cohort": "expert"}
        if not plan["episodes"]:
            raise ValueError("empty formal shard")
        files.append(dump(output / f"expert_part{part}.json", plan))
    source_path = Path(source["path"])
    manifest = {**index, "source_path": source["path"], "source_commit": source["commit"],
                "source_snapshot": source, "files": files, "references": references,
                "planned": {"expert": len(episodes)},
                "preserved_attempts": audit["preserved_unique_physical_identities"],
                "batch_runner": ref(source_path / "v5_batch_eval.py"),
                "launcher": ref(source_path / "scripts/run_v5_interim574.sbatch"),
                "runtime_supplement": [ref(source_path / "typed_choice_eval.py")],
                "audit": dump(output / "identity_audit.json", audit),
                "gpu_submitted": False}
    manifest_ref = dump(output / "manifest.json", manifest)
    launcher = source_path / "scripts/run_v5_interim574.sbatch"
    prefix = (f"env INTERIM574_SOURCE={source['path']} INTERIM574_PREP={output} "
              "INTERIM574_COHORT=expert ")
    commands = {
        "manifest": manifest_ref,
        "source": source["path"],
        "launcher": ref(launcher),
        "startup_episode": episodes[0],
        "cpu_preflight": prefix + f"INTERIM574_PREFLIGHT_ONLY=1 bash {launcher}",
        "startup": prefix + f"INTERIM574_STARTUP_PREFLIGHT=1 sbatch --parsable --nice=0 --array=0%1 {launcher}",
        "formal_template": prefix + "INTERIM574_STARTUP_PREFLIGHT=0 INTERIM574_STARTUP_CONTRACT=<contract> "
                           f"sbatch --parsable --nice=0 --array=0-{shards-1}%<allocated-free-cards> {launcher}",
        "formal_excludes_completed_startup_identity": True,
        "node_binding": None,
    }
    dump(output / "commands.json", commands)
    return {"manifest": manifest_ref, "commands": ref(output / "commands.json"),
            "planned": len(episodes), "shards": shards}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path("/public/home/sunyihan/rpent_libero_eval"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = args.root.resolve(strict=True)
    base = root / "results/harness_v5/interim574_20261007"
    prep = base / "preparation"
    r2 = prep / "repair_legal_r2/cohorts/manifest.json"
    index = json.loads(r2.read_text())
    source = index["source_snapshot"]
    for item in [*source["files"], source["archive"]]:
        path = Path(item["path"])
        if not path.is_absolute() or digest(path) != item["sha256"]:
            raise ValueError(f"source pin changed: {path}")
    policy = Path(source["path"]) / "robots/libero/v5_oracle_policy.py"
    if digest(policy) != "070a4a692ddf4af99f364f63a5366276928f4c78623c86049bb04c4c0beaca8d":
        raise ValueError("legal-r2 does not contain the verified 602be11 oracle fix")

    old_ledger_index = prep / "repair_legal_r2/retained_ledger_index.json"
    retained = json.loads(old_ledger_index.read_text())
    ledger_refs = list(retained["files"])
    ledger_refs += [ref(p) for p in sorted((base / "expert/job4472").glob("part*/probe/episodes.jsonl"))]
    ledger_refs += [ref(base / "expert/startup_preflight/job4466/part0/probe/episodes.jsonl")]
    if len({r["path"] for r in ledger_refs}) != len(ledger_refs):
        raise ValueError("duplicated ledger reference")
    rows, seen = [], set()
    for item in ledger_refs:
        path = Path(item["path"])
        if digest(path) != item["sha256"]:
            raise ValueError(f"ledger changed: {path}")
        for line, text in enumerate(path.read_text().splitlines(), 1):
            if not text.strip():
                continue
            row = json.loads(text)
            key = identity(row["episode"])
            if key in seen:
                raise ValueError(f"duplicate physical identity in selected ledger chain: {key}")
            if row["result"].get("status") == "startup_error":
                raise ValueError(f"selected physical chain includes startup-only failure: {key}")
            seen.add(key)
            rows.append({"ledger": item, "line": line, **row})
    registration = json.loads((prep / "repair_r4/manifest.json").read_text())
    original_plans = [read_pinned(r) for r in registration["files"]
                      if Path(r["path"]).name.startswith("expert_part")]
    registered = [e for p in original_plans for e in p["episodes"]]
    expected = {identity(e) for e in registered}
    if len(registered) != 200 or len(expected) != 200 or not seen <= expected:
        raise ValueError("registered expert cohort changed")
    # Reuse legal-r2 ordering and budgets while excluding all completed attempts.
    r2_plans = [read_pinned(r) for r in index["files"]]
    remainder = [e for plan in r2_plans for e in plan["episodes"] if identity(e) not in seen]
    if {identity(e) for e in remainder} != expected - seen:
        raise ValueError("legal-r2 remainder does not exhaust the registered unattempted identities")
    if len(remainder) != 73 or len(seen) != 127:
        raise ValueError(f"ledger moved: {len(seen)} preserved / {len(remainder)} unattempted; recalculate before submitting")

    errors = [row for row in rows if "job4417" in row["ledger"]["path"] and
              ("StopIteration" in str(row["result"].get("error", "")) or
               " is not in list" in str(row["result"].get("error", "")))]
    if len(errors) != 6:
        raise ValueError("program-error retry identities changed")
    retries = []
    for row in errors:
        output = Path(row["output_dir"])
        retries.append({**row["episode"], "program_error_retry": True,
                        "rerun_of": {"ledger": row["ledger"], "line": row["line"],
                                     "result": ref(output / "result.json"),
                                     "choices": ref(output / "choices.jsonl"),
                                     "original_error": row["result"]["error"]}})
    if set(map(identity, retries)) & set(map(identity, remainder)):
        raise ValueError("retry overlaps unattempted cohort")
    # A startup probe from another source must not count as new physical evidence.
    other_startup = base / "expert/startup_preflight/job4576/part0/startup_contract.json"
    ignored = json.loads(other_startup.read_text()) if other_startup.exists() else None
    cancellation_plans = [read_pinned(r) for r in registration["files"]
                          if Path(r["path"]).name in ("expert_part6.json", "expert_part7.json")]
    cancelled = [e for p in cancellation_plans for e in p["episodes"]]
    audit = {
        "registered": 200, "preserved_unique_physical_identities": len(seen),
        "unattempted": len(remainder), "unattempted_episodes": remainder,
        "ledger_files": ledger_refs, "preserved_rows": rows,
        "policy": "unattempted_only; preserve prior physical successes and failures",
        "previous_24_summary_invalid": True,
        "previous_24_duplicate_identity": {"suite": "libero_10", "task": 8, "seed": 2},
        "scheduler_cancellation": {"job": "4417_6/7", "physical_attempts_in_cancelled_shards": 0,
            "planned_identities": len(cancelled),
            "already_attempted_elsewhere": [e for e in cancelled if identity(e) in seen],
            "unattempted_elsewhere": [e for e in cancelled if identity(e) not in seen]},
        "ignored_other_source_startup": ignored,
        "source_file_count_verified": len(source["files"]),
        "source_policy_sha256": digest(policy),
        "source_reused_without_runtime_edits": True,
    }
    args.output.mkdir(parents=True, exist_ok=False)
    audit_ref = dump(args.output / "ledger_audit.json", audit)
    references = [ref(r2), ref(old_ledger_index), ref(prep / "repair_r4/manifest.json"),
                  *ledger_refs, audit_ref, ref(Path(__file__))]
    packets = {
        "unattempted": packet(args.output / "unattempted73", remainder, r2_plans[0], index,
                              source, references, 8, audit),
        "program_error_retry": packet(args.output / "program_error_retry6", retries, r2_plans[0], index,
                                      source, references, 3,
                                      {**audit, "policy": "program_error_retry_once", "retries": retries}),
    }
    # Preserve scheduler evidence without changing holds, cancellations, or priorities.
    scheduler = subprocess.check_output([
        "sacct", "-X", "-j", "4417,4472", "--format=JobID,State,ExitCode,NodeList,Elapsed", "-P"
    ], text=True)
    (args.output / "scheduler_evidence.txt").write_text(scheduler)
    result = {"root": str(args.output), "audit": audit_ref, "packets": packets,
              "scheduler": ref(args.output / "scheduler_evidence.txt"), "gpu_submitted": False}
    dump(args.output / "handoff.json", result)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
