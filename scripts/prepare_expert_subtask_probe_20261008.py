#!/usr/bin/env python3
"""Prepare two visited original-state development probes for oracle coverage."""

import argparse
import hashlib
import json
from pathlib import Path
import tarfile

from prepare_expert_remote_resume_20261008 import packet, ref


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--archive", type=Path)
    parser.add_argument("--template-index", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    snapshot = args.snapshot.resolve(strict=True)
    meta_path = snapshot / "source_snapshot.json"
    meta = json.loads(meta_path.read_text())
    index = json.loads(args.template_index.read_text())
    old_plan_ref = index["files"][0]
    old_plan_path = Path(old_plan_ref["path"])
    if ref(old_plan_path)["sha256"] != old_plan_ref["sha256"]:
        raise ValueError("registered template changed")
    template = json.loads(old_plan_path.read_text())
    if template["cohort"] != "expert" or template["behavior_frozen"] or template["training_allowed"]:
        raise ValueError("development expert template required")
    archive = (args.archive or Path(meta["archive"]["path"])).resolve(strict=True)
    if ref(archive)["sha256"] != meta["archive"]["sha256"]:
        raise ValueError("snapshot archive changed")
    with tarfile.open(archive) as stream:
        names = [item.name for item in stream.getmembers() if item.isfile()]
    source = {"path": str(snapshot), "commit": meta["commit"],
              "archive": ref(archive), "files": [{**ref(snapshot / name), "relative_path": name}
                                                  for name in sorted(names)]}
    oracle = snapshot / "robots/libero/v5_oracle_policy.py"
    if "or subtask or self._fallback" not in oracle.read_text():
        raise ValueError("snapshot lacks the matching-subtask expert repair")
    episodes = [{"suite": "libero_10", "task": 2, "seed": 4},
                {"suite": "libero_object", "task": 8, "seed": 0}]
    template.update(purpose="visited original-state expert macro-coverage development probe",
                    confirmation=False, training_allowed=False, behavior_frozen=False)
    audit = {"preserved_unique_physical_identities": 0,
             "policy": "new development probe; retain every previous attempt separately",
             "registered_development_identities": episodes,
             "confirmation": False, "training_allowed": False,
             "historical_200_ledger_changed": False,
             "source_oracle_sha256": hashlib.sha256(oracle.read_bytes()).hexdigest()}
    references = [ref(meta_path), ref(args.template_index), old_plan_ref, ref(Path(__file__))]
    result = packet(args.output.resolve(), episodes, template, index, source, references, 1, audit)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
