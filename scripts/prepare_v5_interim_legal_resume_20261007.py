"""Resume only explicitly registered, unattempted interim expert episodes."""
import argparse
import hashlib
import json
from pathlib import Path


def ref(path):
    path = Path(path).resolve(strict=True)
    return {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def read_pinned(item):
    path = Path(item["path"])
    if not path.is_absolute() or ref(path)["sha256"] != item["sha256"]:
        raise ValueError(f"Pinned input changed: {path}")
    return path


def key(episode):
    return episode["suite"], int(episode["task"]), int(episode["seed"])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--parent-index", type=Path, required=True)
    parser.add_argument("--source-plan", type=Path, required=True)
    parser.add_argument("--ledger-index", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    parent = json.loads(args.parent_index.read_text())
    source = json.loads(args.source_plan.read_text())["source_snapshot"]
    ledger_index = json.loads(args.ledger_index.read_text())
    if ledger_index["all_running_shards_terminal"] is not True:
        raise ValueError("Wait for the current episodes' natural boundaries before computing remainder")
    plans = [json.loads(read_pinned(item).read_text()) for item in parent["files"]
             if Path(item["path"]).name.startswith("expert_part")]
    episodes = [episode for plan in plans for episode in plan["episodes"]]
    expected = {key(episode) for episode in episodes}
    if len(episodes) != 200 or len(expected) != 200:
        raise ValueError("Expected the original registered 200 unique expert episodes")
    attempted = set()
    for item in ledger_index["files"]:
        for line in read_pinned(item).read_text().splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            identity = key(row["episode"])
            if identity not in expected or identity in attempted:
                raise ValueError(f"Unexpected or duplicate preserved interim episode: {identity}")
            attempted.add(identity)
    remainder = [episode for episode in episodes if key(episode) not in attempted]
    out = args.output.resolve()
    if out.exists():
        raise FileExistsError("Keep the prior preparation immutable")
    out.mkdir(parents=True)
    template = plans[0]
    files = []
    for part in range(8):
        payload = {**template, "source_path": source["path"], "source_commit": source["commit"],
                   "episodes": remainder[part::8], "preserved_attempts": len(attempted),
                   "resume_policy": "Unattempted episodes only; completed failures remain failures"}
        if not payload["episodes"]:
            raise ValueError("Eight nonempty resume shards required by this launcher")
        path = out / f"expert_part{part}.json"
        path.write_text(json.dumps(payload, indent=2) + "\n")
        files.append(ref(path))
    source_root = Path(source["path"])
    for item in [*source["files"], source["archive"]]:
        read_pinned(item)
    index = {**parent, "files": files, "source_path": source["path"],
             "source_commit": source["commit"], "source_snapshot": source,
             "batch_runner": ref(source_root / "v5_batch_eval.py"),
             "launcher": ref(source_root / "scripts/run_v5_interim574.sbatch"),
             "runtime_supplement": [ref(source_root / "typed_choice_eval.py")],
             "planned": {"expert": len(remainder)},
             "preserved_attempts": len(attempted), "full_cohort_unique_episodes": 200,
             "references": [*parent["references"], ref(args.parent_index), ref(args.source_plan),
                            ref(args.ledger_index), *ledger_index["files"]]}
    (out / "manifest.json").write_text(json.dumps(index, indent=2) + "\n")
    print(json.dumps({"index": ref(out / "manifest.json"), "preserved": len(attempted),
                      "remaining": len(remainder), "shards": len(files)}))


if __name__ == "__main__":
    main()
