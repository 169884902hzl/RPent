"""Join only the declared shared-launcher D2 run; never select a best rerun."""

import argparse
import hashlib
import importlib.util
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


def read(path):
    return json.loads(path.read_bytes())


def reference(path):
    return {"path": str(path.resolve()), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def vla_exits(branch):
    """Keep the skill's exit when a later handoff check changes the receipt."""
    if branch.get("method") != "call_vla" or not branch.get("choices"):
        return []
    path = Path(branch["choices"]["path"])
    if reference(path) != branch["choices"]:
        raise ValueError("closed branch choices changed")
    exits = []
    for line in path.open():
        row = json.loads(line)
        for detail in row.get("execution_details", []):
            execution = detail.get("execution", {})
            if "skill_stop_reason" in execution:
                exits.append({"decision_index": row["index"],
                    "skill_stop_reason": execution["skill_stop_reason"],
                    "handoff_stop_reason": execution.get("stop_reason"),
                    "choices": branch["choices"]})
    return exits


def collect(preparation, results):
    plan = read(preparation / "batch_plan.json")
    submission = read(preparation / "full_d2_submission.json")
    batches = [plan["batches"][i] for i in submission["indices"]]
    first = batches[0]
    manifest_path = Path(first["manifest"]["path"])
    if reference(manifest_path) != first["manifest"]:
        raise ValueError("registered D2 manifest changed")
    manifest = read(manifest_path)
    cases = manifest["cases"]
    registered, reports, errors, branches, sources = set(), [], [], [], []
    for batch_index, batch in zip(submission["indices"], batches):
        if (batch["domain"] != "d2" or any(batch[key] != first[key]
                for key in ("manifest", "source", "source_commit"))):
            raise ValueError("cannot combine domains or source snapshots")
        directory = results / f"job{submission['job']}_{batch_index}" / f"N{plan['selected_n']}"
        for ordinal, index in enumerate(batch["indices"]):
            if index in registered:
                raise ValueError("duplicate registered case")
            registered.add(index)
            case = cases[index]
            worker_dir = directory / f"{ordinal:03d}_{case['name']}"
            assignment_path = worker_dir / "assignment.json"
            if not assignment_path.exists():
                continue
            assignment = read(assignment_path)
            if (assignment["startup"] or assignment["domain"] != "d2"
                    or assignment["manifest"] != first["manifest"]
                    or assignment["case_index"] != index or assignment["case"] != case):
                raise ValueError("worker assignment differs from registration")
            for path in sorted((worker_dir / case["name"]).glob("subtask*/*/summary.json")):
                branch = read(path)
                branches.append({**reference(path), **{key: branch.get(key) for key in (
                    "method", "subtask", "success", "reason", "sim_steps", "wall_s")},
                    "case": case["name"], "vla_exit_evidence": vla_exits(branch)})
            worker_path = worker_dir / "worker_summary.json"
            if not worker_path.exists():
                continue
            worker = read(worker_path)
            if worker["case"] != case or worker["source_commit"] != first["source_commit"]:
                raise ValueError("worker result differs from registration")
            if worker["exit_code"] != 0:
                errors.append({**reference(worker_path), "error": worker.get("message")})
                continue
            result = worker["result"]
            case_path = worker_dir / case["name"] / "summary.json"
            if read(case_path) != result:
                raise ValueError("case result differs from worker receipt")
            reports.append(result)
            sources.append(reference(case_path))
    if registered != set(range(len(cases))) or len(cases) != 40:
        raise ValueError("declared run does not cover exactly the forty D2 cases")
    return manifest, reports, {
        "manifest": reference(manifest_path), "submission": reference(preparation / "full_d2_submission.json"),
        "source": first["source"], "result_sources": sources, "worker_errors": errors,
        "closed_branch_records": branches,
        "closed_branch_label_counts": dict(Counter(
            "known" if type(row["success"]) is bool else "unknown" for row in branches)),
        "vla_inner_stop_counts": dict(Counter(event["skill_stop_reason"]
            for row in branches for event in row["vla_exit_evidence"])),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--preparation", type=Path, required=True)
    parser.add_argument("--results", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    plan, reports, provenance = collect(args.preparation, args.results)
    source = Path(provenance["source"])
    sys.path.insert(0, str(source))
    spec = importlib.util.spec_from_file_location("pinned_d2_summary", source / "scripts/summarize_bounded_hybrid_d2.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    result = module.summarize(plan, reports)
    result.update(**provenance, generated_utc=datetime.now(timezone.utc).isoformat(),
                  collector=reference(Path(__file__)), summarizer=reference(Path(spec.origin)))
    with args.output.open("x") as stream:
        json.dump(result, stream, indent=2)
        stream.write("\n")
    print(json.dumps({key: result[key] for key in ("registered_cases", "case_status",
        "independent_full_replay", "closed_branch_label_counts", "vla_inner_stop_counts", "worker_errors")}))


if __name__ == "__main__":
    main()
