# Copyright 2026 Zhilun Hu.
# SPDX-License-Identifier: Apache-2.0
"""Audit legal cards and recover original plans from explicitly hashed labels."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path

from robots.libero.v5_original_card_evidence import ORIGINAL_SUITES, digest, reconstruct_card


def pinned(descriptor: dict) -> bytes:
    """Read an explicit manifest reference after checking its complete SHA."""
    payload = Path(descriptor["path"]).read_bytes()
    if hashlib.sha256(payload).hexdigest() != descriptor["sha256"]:
        raise ValueError(f"manifest reference changed: {descriptor['path']}")
    return payload


def descriptor(path: Path) -> dict:
    """Describe one explicit input or produced output."""
    return {"path": str(path.resolve()), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def main() -> None:
    """Preserve legacy cards; produce independently evidenced replacements."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--legal-manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    legal = json.loads(args.legal_manifest.read_bytes())
    if legal.get("origin") != "original_oracle" or legal.get("PRO_inputs_used") is not False or legal.get("RPent_cards_in_training"):
        raise ValueError("legal memory manifest is not original-only")
    card_manifest_ref = {"path": legal["source_card_manifest"], "sha256": legal["source_card_manifest_sha256"]}
    card_manifest = json.loads(pinned(card_manifest_ref))
    source_ref = {"path": card_manifest["input_manifest"], "sha256": card_manifest["input_manifest_sha256"]}
    source = json.loads(pinned(source_ref))
    if source.get("PRO_inputs_used") is not False:
        raise ValueError("physical label manifest is not original-only")
    registry = json.loads(pinned(source["original_target_registry"]))
    episode_ref = {"path": registry["source_episodes"], "sha256": registry["source_episodes_sha256"]}
    episodes = {e["output"]: e for e in json.loads(pinned(episode_ref))}
    trace_refs = defaultdict(list)
    for item in source["runtime_logs"]:
        trace_refs[item["sha256"]].append(item)
    statistics = Counter()
    originals, card_audits = [], []
    for item in legal["cards"]:
        card = json.loads(pinned(item))
        skills = {s["skill"] for s in card["steps"]}
        statistics["cards"] += 1
        statistics["counterfactual_cards"] += "/cf_" in item["task"]
        statistics["finish_only_cards"] += skills == {"finish"}
        for skill in ("grasp", "place", "articulate"):
            statistics["cards_with_" + skill] += skill in skills
        card_audits.append({"source": item, "steps": card["steps"], "source_episode": card["source_episode"]})
        if "/cf_" in item["task"]:
            continue
        identity = card["source_episode"]
        if identity["suite"] not in ORIGINAL_SUITES or not 10 <= identity["seed"] < 40:
            raise ValueError("base card is outside original training tasks")
        matches = []
        for trace_ref in trace_refs[card["source_choices_sha256"]]:
            episode = episodes.get(str(Path(trace_ref["path"]).parent))
            if episode is None:
                continue
            result = episode["result"]
            if all(result[k] == identity[k] for k in ("suite", "task", "seed")) and digest(result) == card["source_episode_result_sha256"]:
                matches.append((trace_ref, result))
        if len(matches) != 1:
            raise ValueError("base card has no unique explicitly registered source trajectory")
        trace_ref, result = matches[0]
        if result.get("provider") != "oracle" or result.get("official_success") is not True:
            raise ValueError("base card source is not an officially successful original oracle")
        records = [json.loads(line) for line in pinned(trace_ref).splitlines()]
        originals.append({"descriptor": item, "card": card, "trace": trace_ref, "records": records})
    selected_parents = {str(Path(o["trace"]["path"]).parent) for o in originals}
    labels = defaultdict(dict)
    label_sources = []
    checked_label_refs = {}
    for ref in source["files"]:
        if ref.get("bucket") != "train":
            continue
        payload = pinned(ref)
        label_sources.append(ref)
        for line in payload.splitlines():
            row = json.loads(line)
            correction = row.get("label_correction", {})
            parent = str(Path(correction.get("source_file", "")).parent)
            if parent not in selected_parents:
                continue
            if row.get("suite") not in ORIGINAL_SUITES or not 10 <= row["init_state_index"] < 40:
                raise ValueError("selected physical label is outside original training states")
            source_path = correction["source_file"]
            expected = correction["source_file_sha256"]
            if source_path not in checked_label_refs:
                pinned({"path": source_path, "sha256": expected})
                checked_label_refs[source_path] = expected
            elif checked_label_refs[source_path] != expected:
                raise ValueError("physical source file has inconsistent declared hashes")
            decision = row["step"]
            if decision in labels[parent] and digest(labels[parent][decision]) != digest(row):
                raise ValueError("ambiguous physical evidence for one recorded decision")
            labels[parent][decision] = row
    profiles = json.loads(pinned(legal["files"]["object_skill_cards.json"]))
    lessons = json.loads(pinned(legal["files"]["failure_lessons.json"]))
    args.output.mkdir(parents=True, exist_ok=False)
    output_cards, rebuild_audits = [], []
    decisions = Counter()
    for original in originals:
        parent = str(Path(original["trace"]["path"]).parent)
        rebuilt, audit = reconstruct_card(original["card"], original["records"], labels[parent])
        audit["trace"] = original["trace"]
        rebuild_audits.append(audit)
        for item in audit["decisions"]:
            decisions[item["reason"]] += 1
            step = item.get("step")
            if step and step not in original["card"]["steps"]:
                statistics["omitted_" + step["skill"] + "_supported_by_physical_evidence"] += 1
        if rebuilt is not None:
            path = args.output / "cards" / (original["descriptor"]["task"].replace("/", "_t") + ".json")
            path.parent.mkdir(exist_ok=True)
            path.write_text(json.dumps(rebuilt, indent=2) + "\n")
            output_cards.append({**descriptor(path), "task": original["descriptor"]["task"],
                                 "source_episode": rebuilt["source_episode"]})
    report = {"version": "original-branch-card-audit/1-dev", "scope": "original task physical labels only; no PRO instructions/BDDL opened",
              "inputs": {"legal_manifest": descriptor(args.legal_manifest), "source_card_manifest": card_manifest_ref,
                         "physical_manifest": source_ref, "original_registry": source["original_target_registry"],
                         "original_episodes": episode_ref, "label_files": label_sources},
              "statistics": {**dict(statistics), "base_original_cards": len(originals),
                             "physically_evidenced_rebuilds": len(output_cards),
                             "needs_original_recollection": len(originals) - len(output_cards)},
              "legacy_cards": card_audits, "original_rebuilds": rebuild_audits, "decision_evidence_counts": dict(decisions),
              "object_skill_profiles": profiles["profiles"], "failure_lessons": lessons["rules"],
              "profile_application_limit": "historical general profile applies staging height only; visual success rates do not select a method",
              "failure_lessons_application_limit": "historical nonempty rules uniformly enable approach/retry/wrist refinement; rule text is not rendered",
              "historical_scores_unchanged": {"A3_N_new41": "21/40", "A3_legal_new41": "18/40", "task_card_coverage": "1/40"},
              "script": descriptor(Path(__file__)), "helper": descriptor(Path(__file__).resolve().parents[1] / "robots/libero/v5_original_card_evidence.py")}
    report_path = args.output / "report.json"
    report_path.write_text(json.dumps(report, indent=2) + "\n")
    manifest = {"version": "category-card/1", "origin": "original_oracle", "files": output_cards,
                "PRO_inputs_used": False, "RPent_cards_in_training": False, "coordinates_in_steps": False,
                "admission": "development evidence audit; not connected to runtime or training", "report": descriptor(report_path),
                "missing_tasks": [{"source_episode": a["source_episode"], "reason": a["reason"]}
                                  for a in rebuild_audits if a["status"] != "physically_evidenced_plan"]}
    (args.output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps({"statistics": report["statistics"], "report": descriptor(report_path),
                      "manifest": descriptor(args.output / "manifest.json")}))


if __name__ == "__main__":
    main()
