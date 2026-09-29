"""Classify completed typed-choice episodes from their immutable JSONL traces."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


def classify(result_path: Path) -> dict:
    result = json.loads(result_path.read_text())
    trace_path = result_path.with_name("choices.jsonl")
    rows = [json.loads(line) for line in trace_path.read_text().splitlines() if line]
    timings = [row.get("timing_s", {}) for row in rows]
    decision_latencies = [float(t["decision_total"]) for t in timings if "decision_total" in t]
    model_inference_latencies = [float(t["model_inference"]) for t in timings if "model_inference" in t]
    picks = [row for row in rows if row.get("action", {}).get("tool") == "pi0_pick"]
    segmented_before = sum(bool(row.get("pi0_pick_segmented_before")) for row in picks)
    perception_alias_pairs = []
    if rows:
        try:
            initial_state = json.loads(rows[0].get("state", "{}"))
            locations = next(
                (field.get("value", {}) for field in initial_state.get("fields", [])
                 if field.get("name") == "visual_locations"), {}
            )
            names = sorted(locations)
            for index, first in enumerate(names):
                first_xyz = locations[first].get("xyz_m")
                if first_xyz is None:
                    continue
                for second in names[index + 1:]:
                    if (re.sub(r"_[0-9]+$", "", first) == re.sub(r"_[0-9]+$", "", second)
                            and first_xyz == locations[second].get("xyz_m")):
                        perception_alias_pairs.append([first, second])
        except (TypeError, json.JSONDecodeError):
            pass
    evidence: list[str] = []
    category = "success" if result.get("official_success") else "unknown"
    if not result.get("official_success"):
        last = rows[-1] if rows else {}
        action = last.get("action", {})
        tool = action.get("tool")
        receipt = last.get("receipt", {})
        wrong_object = None
        if result.get("suite") == "libero_object_swap" and picks:
            try:
                state = json.loads(rows[0].get("state", "{}"))
                instruction = next(
                    (field.get("value", "") for field in state.get("fields", [])
                     if field.get("name") == "instruction"), ""
                )
                match = re.match(
                    r"(?i)^pick the (.+?) and place it (?:in|on) the ", instruction
                )
                if match:
                    requested = match.group(1).casefold()
                    picked = {
                        re.sub(r"_\d+$", "", row["action"].get("object", ""))
                        .replace("_", " ").casefold()
                        for row in picks
                    }
                    if requested not in picked:
                        wrong_object = (requested, sorted(picked))
            except (TypeError, json.JSONDecodeError):
                pass
        # Preserve the first actionable root cause even when the episode then
        # spends the remaining budget repeating it.
        skill_failures = []
        for row in rows:
            row_tool = row.get("action", {}).get("tool")
            raw = row.get("receipt", {}).get("log", {}).get("result", {})
            if row_tool in {"pi0_pick", "move_to", "release", "rotate_wrist"} and (
                raw.get("success") is False or row.get("receipt", {}).get("error")
            ):
                skill_failures.append(row_tool)
        repeated_actions = []
        seen_actions = {}
        for row in rows:
            selected = row.get("action", {})
            key = tuple((field, selected.get(field)) for field in ("tool", "object", "region", "height", "yaw"))
            seen_actions[key] = seen_actions.get(key, 0) + 1
        repeated_actions = [key for key, count in seen_actions.items() if count >= 3]
        if tool == "finish":
            category = "误报完成"
            evidence.append("finish selected while official_success=false")
        elif wrong_object:
            category = "模型选错"
            evidence.append(
                f"instruction requests {wrong_object[0]}; pi0_pick selected {wrong_object[1]}"
            )
        elif tool in {"segment", "back_project"} and receipt.get("error"):
            category = "感知"
            evidence.append(str(receipt.get("error")))
        elif skill_failures:
            category = "技能执行"
            evidence.append(f"failed skill receipts: {skill_failures}")
        elif repeated_actions:
            category = "模型选错"
            evidence.append(f"repeated selected action(s): {repeated_actions}")
        elif tool in {"pi0_pick", "move_to", "release", "rotate_wrist"}:
            raw = receipt.get("log", {}).get("result", {})
            if raw.get("success") is False or receipt.get("error"):
                category = "技能执行"
                evidence.append(f"{tool} receipt unsuccessful")
            elif tool == "pi0_pick" and not last.get("pi0_pick_segmented_before"):
                category = "模型选错"
                evidence.append("pi0_pick selected before segment call for that object")
            else:
                category = "模型选错"
                evidence.append(f"last selected tool={tool}")
        elif int(result.get("decisions", 0)) >= int(result.get("max_decisions", 15)):
            category = "预算耗尽"
            evidence.append(f"decisions={result.get('decisions')} max={result.get('max_decisions')}")
        else:
            try:
                state = json.loads(last.get("state", "{}"))
                fields = state.get("fields", [])
                field_values = {
                    entry.get("name"): entry.get("value")
                    for entry in fields
                    if isinstance(entry, dict)
                }
                # Keep compatibility with pilot5 traces written before the
                # canonical serializer was introduced.
                held_value = field_values.get(
                    "inferred_held_object", state.get("inferred_held_object")
                )
                has_held = held_value is not None
            except (TypeError, json.JSONDecodeError):
                has_held = False
            has_destination_action = any(
                candidate.get("tool") in {"move_to", "release"}
                for candidate in last.get("candidates", [])
            )
            if has_held and not has_destination_action:
                category = "候选缺失"
                evidence.append("held object but no measured placement candidate")
            else:
                category = "模型选错"
                evidence.append(f"last selected tool={tool or 'none'}")
    result.update({
        "failure_category": category,
        "failure_evidence": evidence,
        "budget_cap_reached": (
            not bool(result.get("official_success"))
            and int(result.get("decisions", 0)) >= int(result.get("max_decisions", 15))
        ),
        "perception_alias_pairs": perception_alias_pairs,
        "decision_latency_s": decision_latencies,
        "mean_decision_latency_s": (
            sum(decision_latencies) / len(decision_latencies)
            if decision_latencies else None
        ),
        "harness_total_latency_s": decision_latencies,
        "mean_harness_total_latency_s": (
            sum(decision_latencies) / len(decision_latencies)
            if decision_latencies else None
        ),
        "model_inference_latency_s": model_inference_latencies,
        "mean_model_inference_latency_s": (
            sum(model_inference_latencies) / len(model_inference_latencies)
            if model_inference_latencies else None
        ),
        "pi0_pick_calls": len(picks),
        "pi0_pick_segmented_before_count": segmented_before,
        "pi0_pick_segmented_before_all": segmented_before == len(picks),
    })
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    rows = [classify(path) for path in sorted(args.root.glob("**/result.json"))]
    text = "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + ("\n" if rows else "")
    if args.output:
        args.output.write_text(text)
    else:
        print(text, end="")


if __name__ == "__main__":
    main()
