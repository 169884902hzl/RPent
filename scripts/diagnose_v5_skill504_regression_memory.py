"""Pair registered development runs and retain measured skill failure evidence.

Inputs are explicit hashed indices, ledgers and trace paths. No directory
enumeration, task-file access or instruction-text processing is performed.
These observations do not identify the causal switch without paired replay.
"""

import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import re
import statistics

def descriptor(path):
    path = Path(path)
    return {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def pinned(source):
    path = Path(source["path"])
    if descriptor(path)["sha256"] != source["sha256"]:
        raise ValueError("registered input changed: " + str(path))
    return json.loads(path.read_text())


def key(episode):
    return episode["suite"], episode["task"], episode["seed"]


def normalize(row, *, baseline):
    result = row if baseline else row["result"]
    terminal = result.get("primary_terminal") or result.get("termination_category")
    request_failure = terminal == "over_token"
    non_model = terminal in {"startup_error", "infrastructure_error", "model_error", "context_error"} or (
        not baseline and result.get("status") != "completed")
    infrastructure = non_model and not request_failure
    return {"episode": row["episode"], "output_dir": row["output_dir"],
            "official_success": bool(result.get("official_success", False)),
            "terminal": terminal, "infrastructure_failure": infrastructure,
            "request_failure": request_failure, "non_model_failure": non_model or request_failure,
            "derived_failure_category": "over_token" if request_failure else
                                         "infrastructure_failure" if infrastructure else terminal,
            "wall_s": result.get("wall_s"), "source_hashes": result.get("source_hashes", {}),
            "decisions": result.get("decisions"), "correct_finish_secondary": result.get("correct_finish")}


def paired(left, right):
    cells, suites, episodes = Counter(), defaultdict(Counter), []
    for identity in sorted(left.keys() & right.keys()):
        a, b = left[identity], right[identity]
        category = ("infrastructure_pair" if a["infrastructure_failure"] or b["infrastructure_failure"] else
                    "request_failure_pair" if a["request_failure"] or b["request_failure"] else
                    "both_success" if a["official_success"] and b["official_success"] else
                    "regression" if a["official_success"] else "gain" if b["official_success"] else "both_failed")
        cells[category] += 1
        suites[identity[0]][category] += 1
        episodes.append({"episode": dict(suite=identity[0], task=identity[1], seed=identity[2]),
                         "category": category, "left_success": a["official_success"], "right_success": b["official_success"]})
    valid = sum(cells[c] for c in ("both_success", "gain", "regression", "both_failed"))
    return {"recorded_pairs": len(episodes), "valid_pairs": valid, "cells": dict(cells),
            "success_delta_pp": 100*(cells["gain"]-cells["regression"])/valid if valid else None,
            "by_suite": {k: dict(v) for k, v in suites.items()}, "episodes": episodes}


def action_key(receipt):
    return tuple(receipt.get(k) for k in ("tool", "object", "target", "mode"))


def action_text(receipt):
    return receipt.get("card_action") or "%s(%s)" % (
        receipt.get("tool", "unknown"),
        ",".join(str(receipt[k]) for k in ("object", "target", "mode") if receipt.get(k) is not None))


def failure_reason(receipt):
    if receipt.get("error") or receipt.get("verification") == "execution_error":
        return "execution_error"
    if receipt.get("failure_reason"):
        return receipt["failure_reason"]
    if any(receipt.get(k) is False for k in ("grasp_verified", "place_verified", "articulate_verified")):
        return "verification_failed"
    return receipt.get("verification", "unrecorded")


def observe_trace(path):
    rows = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    counts, tools, requested, actions, reasons = Counter(), Counter(), Counter(), Counter(), Counter()
    grasps, errors, sequence = [], [], []
    previous, streak, longest, longest_step = None, 0, 0, None
    actual_previous, actual_streak, actual_longest = None, 0, 0
    exception_messages, exception_families = Counter(), Counter()
    repeated_after_failure, last_attempt = Counter(), {}
    by_object = defaultdict(Counter)
    for event in rows:
        receipt = event.get("receipt", {})
        tool = receipt.get("tool", "unknown")
        selected = event.get("selected", "unknown()")
        names = {e["id"]: e["name"] for e in event.get("measurements", ())}
        obj, target = names.get(receipt.get("object")), names.get(receipt.get("target"))
        identity = action_key(receipt)
        tools[tool] += 1
        requested[selected.split("(", 1)[0]] += 1
        actions[action_text(receipt)] += 1
        reason = failure_reason(receipt)
        reasons[reason] += 1
        counts["executed_true" if receipt.get("executed") is True else
               "executed_false" if receipt.get("executed") is False else "executed_unrecorded"] += 1
        if selected == previous:
            streak += 1
        else:
            previous, streak = selected, 1
        if streak > longest:
            longest, longest_step = streak, event.get("decision")
        actual_streak = actual_streak + 1 if identity == actual_previous else 1
        actual_previous = identity
        actual_longest = max(actual_longest, actual_streak)
        last = last_attempt.get(identity)
        if last is not None and failure_reason(last) not in ("verified", "perception", "unverified", "unrecorded"):
            repeated_after_failure[action_text(receipt)] += 1
        last_attempt[identity] = receipt
        evidence = {"decision": event.get("decision"), "selected": selected,
                    "object_category": obj, "target_category": target,
                    "receipt": receipt, "official_success": event.get("official_success")}
        if event.get("predicate_verification_evidence") is not None:
            evidence["predicate_verification_evidence"] = event["predicate_verification_evidence"]
        sequence.append(evidence)
        if receipt.get("error") or receipt.get("verification") == "execution_error":
            errors.append(evidence)
            counts["execution_error"] += 1
            exception_messages[str(receipt.get("error", "execution_error_without_message"))] += 1
            family = re.sub(r"[-+]?\d+(?:\.\d+)?\s*m\b", "<distance> m", str(receipt.get("error", "execution_error_without_message")))
            exception_families[family] += 1
        if event.get("memory_card") is not None:
            counts["steps_with_memory_card"] += 1
        if tool in ("grasp", "regrasp_restage"):
            grasps.append(evidence)
            label = ("verified" if receipt.get("grasp_verified") is True else
                     "not_verified" if receipt.get("grasp_verified") is False else "unrecorded")
            counts["grasp_attempts"] += 1
            counts["grasp_" + label] += 1
            by_object[obj or "unrecorded"]["attempts"] += 1
            by_object[obj or "unrecorded"][label] += 1
            by_object[obj or "unrecorded"]["mode:" + str(receipt.get("mode", tool))] += 1
            if receipt.get("executed") is not True:
                counts["grasp_execution_not_confirmed"] += 1
        if tool in ("place", "adjust_place"):
            counts["place_attempts"] += 1
            counts["place_" + ("verified" if receipt.get("place_verified") is True else
                             "not_verified" if receipt.get("place_verified") is False else "unrecorded")] += 1
        if tool == "articulate":
            counts["articulate_attempts"] += 1
            counts["articulate_" + ("verified" if receipt.get("articulate_verified") is True else
                                   "not_verified" if receipt.get("articulate_verified") is False else "unrecorded")] += 1
    return {"trace": descriptor(path), "decisions": len(rows), "counts": dict(counts),
            "actual_tools": dict(tools), "requested_tools": dict(requested),
            "failure_reasons": dict(reasons), "action_frequencies": dict(actions),
            "longest_identical_selected_streak": longest, "longest_streak_ending_decision": longest_step,
            "longest_identical_actual_action_streak": actual_longest, "execution_exception_messages": dict(exception_messages),
            "execution_exception_families": dict(exception_families),
            "repeated_action_after_prior_failed_attempt": dict(repeated_after_failure),
            "grasp_by_object_category": {k: dict(v) for k, v in by_object.items()},
            "grasp_evidence": grasps, "execution_error_evidence": errors, "sequence": sequence}


def observed_bottleneck(result):
    """Describe observed evidence, not unobserved physical truth or causality."""
    if result["official_success"]:
        return "official_success"
    if result["non_model_failure"]:
        return result["derived_failure_category"]
    count = result["trace_observations"]["counts"]
    if count.get("execution_error", 0):
        return "skill_execution_error_present"
    if count.get("grasp_attempts", 0) and not count.get("grasp_verified", 0):
        return "grasp_attempts_without_measured_verification"
    if count.get("place_not_verified", 0):
        return "placement_verification_failure_present"
    if count.get("grasp_verified", 0) and not count.get("place_attempts", 0):
        return "verified_grasp_without_place_attempt"
    if count.get("place_verified", 0):
        return "verified_placement_without_official_completion"
    if count.get("grasp_verified", 0) and count.get("place_attempts", 0):
        return "verified_grasp_with_unverified_placement"
    if count.get("articulate_attempts", 0):
        return "articulation_without_official_completion"
    return "no_verified_skill_progress_recorded"


def load_group(reference):
    index = pinned(reference["index"])
    group = index["groups"][reference["group"]]
    manifest = pinned(group["manifest"])
    expected = {key(e) for e in manifest["episodes"]}
    indexed, sources = {}, []
    for source in group["results"]:
        path = Path(source["path"])
        source_now = descriptor(path)
        if source.get("sha256") and source["sha256"] != source_now["sha256"]:
            raise ValueError("completed ledger changed: " + str(path))
        sources.append(source_now)
        data = path.read_text()
        rows = json.loads(data) if source["format"] == "json" else [json.loads(s) for s in data.splitlines() if s.strip()]
        for row in rows:
            identity = key(row["episode"])
            if identity in indexed or identity not in expected:
                raise ValueError("duplicate or unregistered episode: " + repr(identity))
            result = normalize(row, baseline=group.get("baseline", False))
            trace_path = Path(row["output_dir"]) / "choices.jsonl"
            result["trace_observations"] = observe_trace(trace_path)
            result["observed_bottleneck"] = observed_bottleneck(result)
            indexed[identity] = result
    if indexed.keys() != expected or len(expected) != 40:
        raise ValueError("registered development cohort is not complete40")
    model_identity = None
    if group.get("model_identity"):
        path = Path(group["model_identity"])
        content = json.loads(path.read_text())
        if group.get("expected_weight_sha256") and (
            content.get("status") != "ok" or content.get("revision") != group["expected_weight_sha256"]):
            raise ValueError("model identity differs from registration")
        model_identity = {"source": descriptor(path), **{k: content.get(k) for k in
                          ("status", "model", "revision", "max_context_tokens")}}
    totals, tools, errors = Counter(), Counter(), Counter()
    for row in indexed.values():
        totals.update(row["trace_observations"]["counts"])
        tools.update(row["trace_observations"]["actual_tools"])
        errors.update(row["trace_observations"]["execution_exception_families"])
    walls = [r["wall_s"] for r in indexed.values() if isinstance(r["wall_s"], (int, float))]
    summary = {"group": reference["group"], "index": reference["index"], "sources": sources,
               "source_scope": group.get("source_scope"), "memory_scope": group.get("memory_scope", "none"),
               "model_identity": model_identity,
               "recorded": len(indexed), "official_success": sum(r["official_success"] for r in indexed.values()),
               "observed_bottlenecks": dict(Counter(r["observed_bottleneck"] for r in indexed.values())),
               "trace_counts": dict(totals), "actual_tools": dict(tools),
               "execution_exception_families": dict(errors),
               "episodes_with_task_card": sum(bool(r["trace_observations"]["counts"].get("steps_with_memory_card")) for r in indexed.values()),
               "wall_median_s": statistics.median(walls) if walls else None}
    return summary, indexed


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text())
    comparisons = []
    cache = {}
    for item in manifest["comparisons"]:
        groups = []
        for side in ("left", "right"):
            ref = item[side]
            identity = (ref["index"]["path"], ref["index"]["sha256"], ref["group"])
            if identity not in cache:
                cache[identity] = load_group(ref)
            groups.append(cache[identity])
        left, right = groups
        pairing = paired(left[1], right[1])
        episodes = [{**row, "left": left[1][key(row["episode"])],
                     "right": right[1][key(row["episode"])]} for row in pairing["episodes"]]
        comparisons.append({"name": item["name"], "left_summary": left[0], "right_summary": right[0],
                            "paired": pairing, "episodes": episodes})
    prefix_sources = []
    for source in manifest.get("physical_prefix_reports", ()):
        prefix = pinned(source)
        prefix_sources.append({"source": source, "prefixes": prefix.get("prefixes"),
                               "causal_conclusion": prefix.get("causal_conclusion"),
                               "memory_cards": prefix.get("memory_cards")})
    report = {"schema": "v5-skill504-paired-observation/1", "manifest": descriptor(args.manifest),
              "script": descriptor(__file__), "comparisons": comparisons,
              "physical_prefix_reports": prefix_sources,
              "scope": "development paired observations; no score replacement, causal attribution or training data",
              "grasp_truth_limit": "grasp_verified is runtime visual verification, not sustained-grasp simulation truth; historical traces do not establish its errors",
              "control_loop_limit": "repeated selections are counted; unchanged scene is not imputed where before/after measurements are unavailable",
              "training_isolation": "No PRO task files or instruction text processed; only explicit registered episode metadata, receipts and measured categories."}
    args.output.mkdir(parents=True, exist_ok=False)
    (args.output / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    lines = ["# skill504 paired regression and memory observations", "",
             "Development evidence only. Grasp verification is measured evidence, not simulation truth.", ""]
    for comp in comparisons:
        a, b = comp["left_summary"], comp["right_summary"]
        lines += [f"## {comp['name']}", "", f"Official physical success: {a['official_success']}/40 → {b['official_success']}/40.",
                  f"Paired cells: {json.dumps(comp['paired']['cells'], sort_keys=True)}.", "",
                  f"Memory scopes: before={a['memory_scope']}; after={b['memory_scope']}.",
                  f"Observed task-card coverage: {a['episodes_with_task_card']}/40 → {b['episodes_with_task_card']}/40 episodes.",
                  "This is not a test of a complete three-part legal-memory package when task cards are missing.", "",
                  f"Execution errors: {a['trace_counts'].get('execution_error',0)} → {b['trace_counts'].get('execution_error',0)}.",
                  f"Measured grasp verifications / attempts: {a['trace_counts'].get('grasp_verified',0)}/{a['trace_counts'].get('grasp_attempts',0)} → {b['trace_counts'].get('grasp_verified',0)}/{b['trace_counts'].get('grasp_attempts',0)}.", "",
                  "| Episode | Pair | Grasp verified/attempts, before → after | After observed bottleneck | Max same-action streak |",
                  "|---|---|---|---|---:|"]
        for row in comp["episodes"]:
            if row["category"] not in ("regression", "gain"):
                continue
            ep = row["episode"]
            left_counts = row["left"]["trace_observations"]["counts"]
            right_obs = row["right"]["trace_observations"]
            right_counts = right_obs["counts"]
            lines.append(f"| {ep['suite']} t{ep['task']} init{ep['seed']} | {row['category']} | "
                         f"{left_counts.get('grasp_verified',0)}/{left_counts.get('grasp_attempts',0)} → "
                         f"{right_counts.get('grasp_verified',0)}/{right_counts.get('grasp_attempts',0)} | "
                         f"{row['right']['observed_bottleneck']} | {right_obs['longest_identical_actual_action_streak']} |")
        lines += ["", "All 40 paired episodes, exact trace SHA, actual/requested skills, receipts, object-category counts and repeated failed attempts are retained in report.json.", ""]
    lines += ["No causal switch is inferred from unpaired contact-policy samples. No historical failure is removed or rescored."]
    (args.output / "REPORT.md").write_text("\n".join(lines) + "\n")
    print(json.dumps({"comparisons": [{"name": c["name"], "left_success": c["left_summary"]["official_success"],
                                       "right_success": c["right_summary"]["official_success"], "cells": c["paired"]["cells"]}
                                      for c in comparisons], "report": descriptor(args.output / "report.json")}))


if __name__ == "__main__":
    main()
