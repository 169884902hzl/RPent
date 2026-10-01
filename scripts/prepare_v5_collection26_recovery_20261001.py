"""Copy only explicitly registered, unstarted original collection parts."""

import argparse
import hashlib
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    args = parser.parse_args()
    root = Path("/public/home/sunyihan/rpent_libero_eval")
    previous = root / "source_v5_original_training1_retry1_20261001"
    plans = previous / "configs/original_training1_registered_parts_v2_20261001"
    output = args.source / "configs/collection26_recovery_parts_20261001"
    output.mkdir(exist_ok=False)
    sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
    reserved = set()
    for index in range(5):
        plan = json.loads((plans / f"part_{index}.json").read_text())
        reserved.update((e["suite"], e["task"], e["seed"]) for e in plan["episodes"])
    parts = []
    seen = set()
    for index in range(5, 22):
        original_output = root / "results/harness_v5/original_training1_660_20261001" / f"job2840_task{index}"
        if original_output.exists():
            raise ValueError(f"old part has started; refusing duplicate collection: {index}")
        original = plans / f"part_{index}.json"
        plan = json.loads(original.read_text())
        assert plan["libero_type"] == "standard" and len(plan["episodes"]) == 30
        for e in plan["episodes"]:
            key = e["suite"], e["task"], e["seed"]
            assert e["suite"] in ("libero_spatial", "libero_object", "libero_goal", "libero_10")
            assert 10 <= e["seed"] < 40 and key not in reserved and key not in seen
            seen.add(key)
        path = output / f"part_{index - 5}.json"
        path.write_text(json.dumps(plan, indent=2) + "\n")
        parts.append({"array_task": index - 5, "old_unstarted_part": index,
                      "plan": str(path), "sha256": sha(path),
                      "original_plan": str(original), "original_plan_sha256": sha(original),
                      "episodes": len(plan["episodes"])})
    config = json.loads((previous / "configs/v5_original_training1_collection_20261001.json").read_text())
    config["shared_schema"] = str(args.source / "shared_v5r_schema.py")
    config["shared_schema_sha256"] = sha(Path(config["shared_schema"]))
    config["wording_bank"] = str(args.source / "configs/v5_original_wording_bank30_20261001.json")
    if sha(Path(config["wording_bank"])) != config["wording_bank_sha256"]:
        raise ValueError("original-only wording bank differs from the registered collection")
    config["split"] = "train"
    config_path = args.source / "configs/collection26_recovery_config_20261001.json"
    with config_path.open("x") as handle:
        json.dump(config, handle, indent=2)
        handle.write("\n")
    manifest = {"purpose": "unstarted original task collection recovery, not training admission",
                "episodes": len(seen), "parts": parts, "source": str(args.source),
                "collection_config": str(config_path), "collection_config_sha256": sha(config_path),
                "reserved_old_parts": list(range(5)), "overlap_with_reserved_old_episodes": 0,
                "training_init_indices": list(range(10, 40)), "excluded_init_indices": list(range(10)) + [40],
                "state_source": "perception", "private_truth": "labels_only", "PRO_inputs_used": False,
                "new_gpu_concurrency": 1, "pause_marker": "per_array_task_path",
                "old_pending_parts": list(range(5, 22)), "generator_sha256": sha(Path(__file__))}
    path = args.source / "configs/collection26_recovery_index_20261001.json"
    path.write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps({"episodes": len(seen), "parts": len(parts), "index": str(path), "sha256": sha(path)}))


if __name__ == "__main__":
    main()
