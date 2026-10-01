"""Join explicit train/validation provenance without promoting audit status."""

import argparse
import collections
import hashlib
import json
from pathlib import Path

import numpy as np


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rows(descriptors):
    for d in descriptors:
        assert sha(d["path"]) == d["sha256"]
        lines = Path(d["path"]).read_text().splitlines()
        assert len(lines) == d["rows"]
        yield from map(json.loads, lines)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--train-manifest", type=Path, required=True)
    p.add_argument("--validation-manifest", type=Path, required=True)
    p.add_argument("--target-registry", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    train = json.loads(a.train_manifest.read_text())
    validation = json.loads(a.validation_manifest.read_text())
    t_files = [d for d in train["files"] if d["bucket"] in ("train", "auxiliary")]
    v_files = [d for d in validation["files"] if d["bucket"] in ("train", "auxiliary")]
    training, heldout = list(rows(t_files)), list(rows(v_files))
    assert training and heldout
    assert all(r["split"] == "train" and 10 <= r["init_state_index"] < 40 for r in training)
    assert all(r["split"] == "validation" and r["init_state_index"] in range(5) for r in heldout)
    assert not {r["scene_id"] for r in training} & {r["scene_id"] for r in heldout}
    assert not {r["request"]["state"] for r in training} & {r["request"]["state"] for r in heldout}
    stats = {}
    for name, group in (("train", training), ("validation", heldout)):
        kinds = collections.Counter(r["question_type"] for r in group)
        assert all(len(r["request"]["questions"]["action"]["criteria"]) == 5
                   for r in group if r["question_type"] == "progress")
        assert all(r["prompt_tokens"] <= 3072 for r in group)
        lengths = [r["prompt_tokens"] for r in group]
        stats[name] = {"rows": len(group), "by_question": dict(kinds),
                       "by_task": dict(collections.Counter(str((r["suite"], r["task_id"])) for r in group)),
                       "token_p95": float(np.percentile(lengths, 95)), "token_max": max(lengths),
                       "over2048": sum(n > 2048 for n in lengths),
                       "init_state_indices": sorted({r["init_state_index"] for r in group})}
    registry = json.loads(a.target_registry.read_text())
    assert registry["PRO_text_read"] is False
    a.output.mkdir(parents=True, exist_ok=False)
    report = {**train, "purpose": "labeled original/CF LIBERO prefix ready for independent review; NOT training admission",
              "validation_files": v_files, "validation_status": "independent original canonical wording/init0-4, physical branch labels",
              "validation_manifest": str(a.validation_manifest), "validation_manifest_sha256": sha(a.validation_manifest),
              "source_files": train["source_files"] + validation["source_files"],
              "runtime_logs": train["runtime_logs"] + validation["runtime_logs"],
              "original_target_registry": {"path": str(a.target_registry), "sha256": sha(a.target_registry)},
              "statistics": stats, "train_validation_init_overlap": 0, "train_validation_state_overlap": 0,
              "full_training_admission": False, "training_started": False,
              "remaining": "Codex1 independent strict review and isolation-side PRO target comparison; no automatic SFT submission",
              "packager_sha256": sha(__file__)}
    (a.output / "manifest.json").write_text(json.dumps(report, indent=2) + "\n")
    (a.output / "summary.json").write_text(json.dumps(stats, indent=2) + "\n")
    print(json.dumps({"statistics": stats, "manifest_sha256": sha(a.output / "manifest.json")}))


if __name__ == "__main__":
    main()
