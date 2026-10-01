"""Register newly qualified original tasks without duplicating reserved episodes."""

import argparse
import hashlib
import json
import re
from collections import defaultdict
from pathlib import Path

import numpy as np

from scripts.prepare_v5_original_counterfactuals_20261001 import rewrites

NEW_TASKS = {
    ("libero_object", 3), ("libero_object", 6), ("libero_object", 7),
    ("libero_object", 8), ("libero_spatial", 3), ("libero_spatial", 5),
}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    from libero.libero import benchmark

    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    args = parser.parse_args()
    root = Path("/public/home/sunyihan/rpent_libero_eval")
    gate = root / "results/harness_v5/original_gate_proven36_200_20261001"
    previous = root / "source_v5_original_training1_retry1_20261001"
    reserved = set()
    sources = {}
    for part in range(22):
        path = previous / f"configs/original_training1_registered_parts_v2_20261001/part_{part}.json"
        sources[str(path)] = sha(path)
        for e in json.loads(path.read_text())["episodes"]:
            reserved.add((e["suite"], e["task"], e["seed"]))
    groups = defaultdict(list)
    for shard in range(2):
        path = gate / f"job2887_task{shard}/episodes.jsonl"
        data = path.read_bytes()
        sources[str(path)] = hashlib.sha256(data).hexdigest()
        for line in data.splitlines():
            record = json.loads(line)
            e = record["episode"]
            groups[(e["suite"], e["task"])].append(record)
    parts = args.source / "configs/qualified_collection48_parts_20261001"
    parts.mkdir(exist_ok=False)
    original_bank = args.source / "configs/v5_original_wording_bank30_20261001.json"
    bank = json.loads(original_bank.read_text())
    config = json.loads((previous / "configs/v5_original_training1_collection_20261001.json").read_text())
    assert sha(original_bank) == config["wording_bank_sha256"]
    for key in sorted(NEW_TASKS):
        task = benchmark.get_benchmark_dict()[key[0]]().get_task(key[1])
        language = task.language
        match = re.fullmatch(r"pick up the (.+) and place it (in|on) the (.+)", language)
        if match is None:
            raise ValueError(f"unregistered original instruction pattern: {key}")
        variants = rewrites(match[1], match[3], match[2])
        assert len(variants) == len(set(variants)) == 30
        bank["tasks"][f"{key[0]}/{key[1]}"] = {
            "suite": key[0], "task": key[1], "instruction": language,
            "instruction_sha256": hashlib.sha256(language.encode()).hexdigest(),
            "evidence": sources, "rewrites": variants,
        }
    bank["instruction_count"] = sum(len(t["rewrites"]) for t in bank["tasks"].values())
    bank["qualified_collection48_original_bank_sha256"] = sha(original_bank)
    bank_path = args.source / "configs/qualified_collection48_wording_bank_20261001.json"
    bank_path.write_text(json.dumps(bank, indent=2) + "\n")
    config.update(shared_schema=str(args.source / "shared_v5r_schema.py"),
                  shared_schema_sha256=sha(args.source / "shared_v5r_schema.py"),
                  wording_bank=str(bank_path), wording_bank_sha256=sha(bank_path), split="train")
    config_path = args.source / "configs/qualified_collection48_config_20261001.json"
    config_path.write_text(json.dumps(config, indent=2) + "\n")
    budget = {"max_decisions": 100, "max_chunks": 80,
              "max_episode_steps": 10000, "prompt_limit": 3072}
    registered, seen, smoke = [], set(), None
    for key, records in sorted(groups.items()):
        if key not in NEW_TASKS:
            continue
        correct = sum(bool(r["result"].get("correct_finish")) for r in records)
        if len(records) != 5 or correct < 4:
            continue
        assert {r["episode"]["seed"] for r in records} == set(range(5))
        assert key[0] in ("libero_spatial", "libero_object", "libero_goal", "libero_10")
        unused = [i for i in range(10, 40) if (*key, i) not in reserved]
        if not unused:
            continue
        task_rewrites = bank["tasks"][f"{key[0]}/{key[1]}"]["rewrites"]
        assert len(task_rewrites) == len(set(task_rewrites)) == 30
        states = benchmark.get_benchmark_dict()[key[0]]().get_task_init_states(key[1])
        assert len(states) >= 40
        episodes = [{"suite": key[0], "task": key[1], "seed": i,
                     "init_state_sha256": hashlib.sha256(np.asarray(states[i]).tobytes(order="C")).hexdigest()}
                    for i in unused]
        if smoke is None:
            assert episodes[0]["seed"] == 10
            smoke = episodes.pop(0)
            seen.add((*key, 10))
        for e in episodes:
            identity = (e["suite"], e["task"], e["seed"])
            assert identity not in reserved and identity not in seen
            seen.add(identity)
        path = parts / f"part_{len(registered)}.json"
        plan = {"purpose": "newly qualified original collection; no PRO inputs",
                "libero_type": "standard", "budget": budget, "episodes": episodes}
        path.write_text(json.dumps(plan, indent=2) + "\n")
        registered.append({"part": len(registered), "suite": key[0], "task": key[1],
                           "expert_correct5": correct, "path": str(path),
                           "sha256": sha(path), "episodes": len(episodes)})
    if smoke is None:
        raise ValueError("no newly qualified unreserved original task")
    smoke_path = args.source / "configs/qualified_collection48_smoke_20261001.json"
    smoke_path.write_text(json.dumps({"purpose": "new contact receipt source physical smoke",
                                     "libero_type": "standard", "budget": budget,
                                     "episodes": [smoke]}, indent=2) + "\n")
    index = {"purpose": "new task qualification, not full expert gate or SFT admission",
             "parts": registered, "smoke": str(smoke_path), "smoke_sha256": sha(smoke_path),
             "registered_episodes": len(seen), "tasks": len(registered),
             "collection_config": str(config_path), "collection_config_sha256": sha(config_path),
             "source_snapshots": sources, "reserved_episode_overlap": len(seen & reserved),
             "excluded_init_indices": list(range(10)) + [40], "PRO_inputs_used": False,
             "state_source": "perception", "private_truth": "labels_only",
             "generator_sha256": sha(Path(__file__))}
    path = args.source / "configs/qualified_collection48_index_20261001.json"
    path.write_text(json.dumps(index, indent=2) + "\n")
    print(json.dumps({"index": str(path), "sha256": sha(path),
                      "tasks": len(registered), "episodes": len(seen),
                      "reserved_episode_overlap": index["reserved_episode_overlap"]}))


if __name__ == "__main__":
    main()
