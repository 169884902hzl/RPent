"""Pin full public instruction diagnostics on the registered original/development identities."""

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
        raise ValueError("archive differs from snapshot")
    with tarfile.open(args.archive) as stream:
        names = sorted(m.name for m in stream.getmembers() if m.isfile())
    source_ref = {"path": str(source), "commit": meta["commit"], "archive": archive,
        "files": [{**ref(source / name), "relative_path": name} for name in names]}
    base = root / "results/harness_v5/interim574_20261007/preparation"
    templates = {
        "expert": base / "expert_coverage200_20261008_r1/manifest.json",
        "A3-N": base / "A3_resume_legal_r2_20261008/manifest.json"}
    registration = base / "manifest.json"
    original200 = base / "registered_original_gate_200.json"
    args.output.mkdir(parents=True, exist_ok=False)
    for cohort, index_path in templates.items():
        index = json.loads(index_path.read_text())
        template = json.loads(Path(index["files"][0]["path"]).read_text())
        if cohort == "expert":
            episodes = json.loads(original200.read_text())["episodes"]
        else:
            registered = json.loads(registration.read_text())
            episodes = [e for item in registered["files"]
                        if Path(item["path"]).name.startswith("A3-N_part")
                        for e in json.loads(Path(item["path"]).read_text())["episodes"]]
        expected = 200 if cohort == "expert" else 80
        assert len(episodes) == len({(e["suite"], e["task"], e["seed"]) for e in episodes}) == expected
        output = args.output / cohort
        output.mkdir()
        budget = {**template["budget"], "vla_task_diagnostic_v1": True}
        files = []
        for part in range(8):
            plan = {**template, "source_path": str(source), "source_commit": meta["commit"],
                "cohort": cohort, "budget": budget, "episodes": episodes[part::8],
                "purpose": "full public instruction candidate structure development diagnostic",
                "confirmation": False, "behavior_frozen": False, "training_allowed": False,
                "startup_repair_only": False}
            files.append(dump(output / f"{cohort}_part{part}.json", plan))
        payload = {**index, "source_path": str(source), "source_commit": meta["commit"],
            "source_snapshot": source_ref, "files": files, "planned": {cohort: expected},
            "references": [ref(index_path), ref(registration), ref(original200), ref(Path(__file__)),
                           ref(source / "source_snapshot.json")],
            "batch_runner": ref(source / "v5_batch_eval.py"),
            "launcher": ref(source / "scripts/run_v5_interim574.sbatch"),
            "runtime_supplement": [ref(source / "typed_choice_eval.py")],
            "original_sentence_source": "current public task instruction; no PRO template files read",
            "gpu_submitted": False, "audit": {"training_allowed": False, "confirmation": False}}
        print(json.dumps(dump(output / "manifest.json", payload)))


if __name__ == "__main__":
    main()
