"""Inspect original diagnostic terminal branches from explicit manifests."""

import argparse
import hashlib
import json
from pathlib import Path


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ledger", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    episodes = [json.loads(line) for line in args.ledger.read_text().splitlines()]
    records = []
    for episode in episodes:
        identity = episode["episode"]
        if identity["suite"] not in ("libero_spatial", "libero_object", "libero_goal", "libero_10"):
            raise ValueError("terminal diagnostic only accepts original tasks")
        directory = Path(episode["output_dir"])
        manifest_path = directory / "training_manifest.json"
        manifest = json.loads(manifest_path.read_text())
        descriptor = manifest["files"]["branches"]
        path = Path(descriptor["path"])
        if digest(path) != descriptor["sha256"]:
            raise ValueError("diagnostic branch file changed")
        branches = [json.loads(line) for line in path.read_text().splitlines()]
        terminal = [row for row in branches if row["before"]["done"]]
        noops = [row for row in terminal if row["action"] in ("finish()", "ask_help()")]
        preserved = [row for row in noops
                     if row["before"]["satisfied"] == row["after"]["satisfied"]
                     and row["after"]["done"]]
        records.append({
            "episode": identity, "result": episode["result"],
            "manifest_path": str(manifest_path), "manifest_sha256": digest(manifest_path),
            "branches_path": str(path), "branches_sha256": descriptor["sha256"],
            "branches": len(branches), "terminal_branches": len(terminal),
            "terminal_physical_branches": len(terminal) - len(noops),
            "terminal_noop_predicates_preserved": len(preserved),
            "terminal_noop_predicates_changed": len(noops) - len(preserved),
            "terminal_execution_errors": sum(bool(row["receipt"].get("error")) for row in terminal),
            "terminal_evidence": terminal,
        })
    passed = bool(records) and all(
        row["terminal_branches"] > 0 and row["terminal_physical_branches"] == 0
        and row["terminal_noop_predicates_changed"] == 0
        and row["terminal_execution_errors"] == 0 for row in records)
    report = {"purpose": "original-only diagnostic, not training or benchmark admission",
              "passed": passed, "episodes": len(records), "records": records,
              "ledger": str(args.ledger), "ledger_sha256": digest(args.ledger),
              "script_sha256": digest(Path(__file__))}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x") as output:
        output.write(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"passed": passed, "episodes": len(records),
                      "output": str(args.output), "sha256": digest(args.output)}))


if __name__ == "__main__":
    main()
