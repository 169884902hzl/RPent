"""Collect only registered same-run action prediction/physics pair manifests."""

import argparse
import hashlib
import json
from pathlib import Path


def reference(path):
    path = Path(path).resolve(strict=True)
    return {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def checked(record):
    path = Path(record["path"])
    if not path.is_absolute() or reference(path)["sha256"] != record["sha256"]:
        raise ValueError("registered same-run input changed: " + str(path))
    return path


def collect(registry_path, output):
    registry = json.loads(registry_path.read_text())
    if registry["training_allowed"] is not False:
        raise ValueError("diagnostic pairs must remain excluded from training")
    pairs, finishes, loaded, pending = [], [], [], []
    for entry in registry["pair_manifests"]:
        path = Path(entry["path"])
        if not path.is_absolute():
            raise ValueError("pair manifest must have an explicit absolute path")
        if not path.is_file():
            pending.append(entry)
            continue
        if "sha256" in entry:
            checked(entry)
        manifest = json.loads(path.read_text())
        if manifest["schema"] != "same_run_success578/2" or manifest["training_allowed"]:
            raise ValueError("unexpected pair schema or training permission")
        for name, destination in (("pairs", pairs), ("finish", finishes)):
            raw = checked(manifest[name])
            destination.extend(json.loads(line) for line in raw.read_text().splitlines() if line)
        loaded.append({"manifest": reference(path), "pairs": manifest["pairs"],
                       "finish": manifest["finish"], "counts": manifest["counts"]})
    keys = [row["state_action_key"] for row in pairs + finishes]
    if len(keys) != len(set(keys)):
        raise ValueError("duplicate same-run state/action key")
    known = [row for row in pairs if row["simulation_truth"] is not None
             and row["p_success"] is not None and row["choice_persisted"]
             and row["private_label_persisted"]]
    for row in known:
        if type(row["simulation_truth"]) is not bool or not 0 <= row["p_success"] <= 1:
            raise ValueError("invalid physical label or probability")
        if row["label_source"] != "same_run_passive_simulation_sidecar":
            raise ValueError("public receipt is not a private physics label")
        revision = row["model_identity"]["service_health"]["revision"]
        if revision != registry["model_revision"]:
            raise ValueError("mixed checkpoint revisions")
    output.mkdir(parents=True, exist_ok=False)
    pair_path, finish_path = output / "paired_action_outcomes.jsonl", output / "finish_outcomes.jsonl"
    for path, rows in ((pair_path, pairs), (finish_path, finishes)):
        path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows))
    summary = {"schema": "success578_delivery/1", "registry": reference(registry_path),
               "inputs": loaded, "pending_inputs": pending,
               "pairs": reference(pair_path), "finish": reference(finish_path),
               "counts": {"actions": len(pairs), "finish": len(finishes),
                          "eligible": len(known),
                          "positive": sum(row["simulation_truth"] for row in known),
                          "negative": sum(not row["simulation_truth"] for row in known),
                          "truth_unknown": sum(row["simulation_truth"] is None for row in pairs),
                          "prediction_unknown": sum(row["p_success"] is None for row in pairs)},
               "label_source": "same_run_passive_simulation_sidecar",
               "complete": not pending, "auroc_computed": False,
               "training_allowed": False, "old_public_4103_used": False}
    manifest_path = output / "manifest.json"
    manifest_path.write_text(json.dumps(summary, indent=2) + "\n")
    return {"manifest": reference(manifest_path), "counts": summary["counts"],
            "pending": len(pending)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--registry", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(collect(args.registry.resolve(strict=True), args.output.resolve())))


if __name__ == "__main__":
    main()
