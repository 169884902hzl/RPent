"""Pin the same expert200/A3-N80 cohorts for native-task budget development."""

import argparse
import json
from pathlib import Path
import tarfile

from prepare_expert_remote_resume_20261008 import dump, ref


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root, source = args.root.resolve(strict=True), args.source.resolve(strict=True)
    meta = json.loads((source / "source_snapshot.json").read_text())
    archive = ref(args.archive)
    if archive["sha256"] != meta["archive"]["sha256"]:
        raise ValueError("archive differs from immutable source")
    with tarfile.open(args.archive) as stream:
        names = sorted(m.name for m in stream.getmembers() if m.isfile())
    source_ref = {"path": str(source), "commit": meta["commit"], "archive": archive,
                  "files": [{**ref(source / name), "relative_path": name} for name in names]}
    base = root / "results/harness_v5/interim574_20261007/preparation"
    registration = base / "manifest.json"
    original = base / "registered_original_gate_200.json"
    args.output.mkdir(parents=True, exist_ok=False)
    for cohort, template_dir, baseline in (
        ("expert", "expert_coverage200_20261008_r1", "fulltask_expert200_20261009_closed_r1"),
        ("A3-N", "A3_resume_legal_r2_20261008", "fulltask_A3N80_20261009_closed_r1"),
    ):
        template_index = base / template_dir / "manifest.json"
        index = json.loads(template_index.read_text())
        template = json.loads(Path(index["files"][0]["path"]).read_text())
        if cohort == "expert":
            episodes = json.loads(original.read_text())["episodes"]
        else:
            episodes = [e for item in json.loads(registration.read_text())["files"]
                        if Path(item["path"]).name.startswith("A3-N_part")
                        for e in json.loads(Path(item["path"]).read_text())["episodes"]]
        expected = 200 if cohort == "expert" else 80
        if len(episodes) != len({(e["suite"], e["task"], e["seed"]) for e in episodes}) or len(episodes) != expected:
            raise ValueError("registered cohort identities changed")
        budget = {**template["budget"], "vla_task_diagnostic_v1": False,
                  "vla_task_v1": True, "skill_budget_v1": True, "task_completion_receipts_v1": True}
        baseline_path = root / "artifacts" / baseline / "manifest.json"
        output = args.output / cohort
        output.mkdir()
        files = []
        for part in range(8):
            plan = {**template, "source_path": str(source), "source_commit": meta["commit"],
                    "cohort": cohort, "budget": budget, "episodes": episodes[part::8],
                    "purpose": "public task macro, incomplete-task recovery and visible action costs; development",
                    "confirmation": False, "behavior_frozen": False, "training_allowed": False,
                    "startup_repair_only": False, "paired_baseline": ref(baseline_path)}
            files.append(dump(output / f"{cohort}_part{part}.json", plan))
        packet = {**index, "source_path": str(source), "source_commit": meta["commit"],
                  "source_snapshot": source_ref, "files": files, "planned": {cohort: expected},
                  "references": [ref(template_index), ref(registration), ref(original), ref(Path(__file__)),
                                 ref(source / "source_snapshot.json"), ref(baseline_path)],
                  "batch_runner": ref(source / "v5_batch_eval.py"),
                  "launcher": ref(source / "scripts/run_v5_interim574.sbatch"),
                  "runtime_supplement": [ref(source / "typed_choice_eval.py")],
                  "gpu_submitted": False, "audit": {"training_allowed": False, "confirmation": False},
                  "unchanged_action_budget": budget["max_episode_steps"], "node_binding": None}
        print(json.dumps(dump(output / "manifest.json", packet)))


if __name__ == "__main__":
    main()
