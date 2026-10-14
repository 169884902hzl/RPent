"""Prepare the full registered 80 states for Jev and the frozen public rule."""

import argparse
import hashlib
import json
from pathlib import Path
from urllib.request import urlopen


def ref(path):
    path = Path(path).resolve(strict=True)
    return {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def pinned(item):
    path = Path(item["path"])
    if not path.is_absolute() or ref(path)["sha256"] != item["sha256"]:
        raise ValueError(f"Pinned input changed: {path}")
    return path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--jev-endpoint", default="http://10.10.223.2:18582")
    parser.add_argument("--rule-endpoint", default="http://110.1.1.1:18415")
    args = parser.parse_args()
    root = args.root.resolve(strict=True)
    cohort = root / "results/harness_v5/interim574_20261007"
    registration_path = cohort / "preparation/manifest.json"
    registration = json.loads(registration_path.read_text())
    originals = [json.loads(pinned(item).read_text()) for item in registration["files"]
                 if Path(item["path"]).name.startswith("A3-N_part")]
    episodes = [episode for plan in originals for episode in plan["episodes"]]
    if len(episodes) != 80 or len({(e["suite"], e["task"], e["seed"]) for e in episodes}) != 80:
        raise ValueError("Expected the full original registered 80 states")
    remaining_path = cohort / "preparation/A3_resume_legal_r2_20261008/manifest.json"
    remaining = json.loads(remaining_path.read_text())
    source = remaining["source_snapshot"]
    for item in [*source["files"], source["archive"], remaining["batch_runner"], *remaining.get("runtime_supplement", [])]:
        pinned(item)
    template = json.loads(pinned(remaining["files"][0]).read_text())
    budget = {**template["budget"], "success_prediction_diagnostic": False}
    behavior_differences = {name: [template["budget"].get(name), value] for name, value in budget.items()
                           if template["budget"].get(name) != value}
    if behavior_differences != {"success_prediction_diagnostic": [True, False]}:
        raise ValueError("Only the reporting-only v5 success head is unavailable for the comparator services")
    launcher = ref(root / "scripts/run_v5_interim80_comparators_20261008.sbatch")
    bridge = ref(root / "scripts/jev_systemone_score_bridge_20261008.py")
    rule_dir = root.parent / "rd_instruction_20260923/v5r_20261001/rule_baseline_20261005"
    rule_identity = ref(rule_dir / "service_identity.json")
    rule_handoff = ref(rule_dir / "HANDOFF_CODEX3.md")
    endpoints = {"A4-N": args.jev_endpoint, "RULE-N": args.rule_endpoint}
    health = {}
    for name, endpoint in endpoints.items():
        with urlopen(endpoint.rstrip("/") + "/health", timeout=15) as response:
            health[name] = json.load(response)
    if health["A4-N"].get("model") != "jev-1.13.0" or health["A4-N"].get("identity_verified") is not True:
        raise ValueError("Official Jev health identity changed")
    if (health["RULE-N"].get("model") != "public_text_rule_20261005_v1"
            or health["RULE-N"].get("revision") != "b29c464a23e659afdb2938308ba9b748a139bc11eaf5e2e9a86a4da6f5c1f4d0"):
        raise ValueError("Frozen public rule identity changed")
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    health_path = out / "endpoint_health.json"
    health_path.write_text(json.dumps(health, indent=2) + "\n")
    files = []
    for name in endpoints:
        for part in range(8):
            plan = {**template, "cohort": name, "episodes": episodes[part::8], "budget": budget,
                "purpose": "interim same registered80; not behavior-freeze evidence",
                "provider": "systemone", "choice_endpoint": endpoints[name],
                "expected_model": health[name]["model"],
                "model_revision": health[name].get("revision", "jev-1.13.0"),
                "model_interface": "unchanged choice System One client",
                "reporting_only_difference_from_A3": behavior_differences,
                "source_path": source["path"], "source_commit": remaining["source_commit"],
                "training_allowed": False, "behavior_frozen": False,
                "resume_policy": "Full original80; startup result counted once; formal array skips exactly its identity"}
            for field in ("preserved_attempts", "launcher_execution_identity", "parent_plan"):
                plan.pop(field, None)
            path = out / f"{name}_part{part}.json"
            path.write_text(json.dumps(plan, indent=2) + "\n")
            files.append(ref(path))
    index = {"purpose": "Jev and frozen rule full80 interim comparators",
        "planned": {"A4-N": 80, "RULE-N": 80}, "files": files,
        "source_path": source["path"], "source_commit": remaining["source_commit"],
        "source_snapshot": source, "batch_runner": remaining["batch_runner"],
        "runtime_supplement": remaining.get("runtime_supplement", []),
        "launcher": launcher, "jev_systemone_bridge": bridge,
        "endpoint_health": ref(health_path), "references": [ref(registration_path), ref(remaining_path),
            *[item for item in registration["files"] if Path(item["path"]).name.startswith("A3-N_part")],
            rule_identity, rule_handoff],
        "budget_difference_from_A3": behavior_differences,
        "reporting_difference_explanation": "v5-only success-prediction head disabled; it never changes action behavior",
        "alignment_notes": ["Official relay exposes /score only; local CPU bridge maps the same action request unchanged to /score.",
            "Official relay does not expose server compute; retain HTTP wall time separately.",
            "Frozen rule /health advertises 2048 but server performs no tokenizer or truncation; harness admission remains 3072.",
            "Frozen rule is state-free CPU logic with deterministic one-hot scores, not calibrated action success probabilities.",
            "A3 once-ledger contains original functional outcomes from startup_r4 and legal_r2 remainder; these comparator runs use legal_r2 for all80."],
        "no_node_binding": True, "GPU_submitted": False, "generator": ref(__file__)}
    manifest_path = out / "manifest.json"
    manifest_path.write_text(json.dumps(index, indent=2) + "\n")
    print(json.dumps({"manifest": ref(manifest_path), "planned": index["planned"], "source": source["path"]}))


if __name__ == "__main__":
    main()
