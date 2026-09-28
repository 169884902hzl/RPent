"""Classify completed typed-choice episodes from their immutable JSONL traces."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def classify(result_path: Path) -> dict:
    result = json.loads(result_path.read_text())
    trace_path = result_path.with_name("choices.jsonl")
    rows = [json.loads(line) for line in trace_path.read_text().splitlines() if line]
    timings = [row.get("timing_s", {}) for row in rows]
    decision_latencies = [float(t["decision_total"]) for t in timings if "decision_total" in t]
    picks = [row for row in rows if row.get("action", {}).get("tool") == "pi0_pick"]
    segmented_before = sum(bool(row.get("pi0_pick_segmented_before")) for row in picks)
    evidence: list[str] = []
    category = "success" if result.get("official_success") else "unknown"
    if not result.get("official_success"):
        last = rows[-1] if rows else {}
        action = last.get("action", {})
        tool = action.get("tool")
        receipt = last.get("receipt", {})
        if tool == "finish":
            category = "误报完成"
            evidence.append("finish selected while official_success=false")
        elif int(result.get("decisions", 0)) >= int(result.get("max_decisions", 15)):
            category = "预算耗尽"
            evidence.append(f"decisions={result.get('decisions')} max={result.get('max_decisions')}")
        elif tool in {"segment", "back_project"} and receipt.get("error"):
            category = "感知"
            evidence.append(str(receipt.get("error")))
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
        else:
            try:
                has_held = json.loads(last.get("state", "{}")).get("inferred_held_object") is not None
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
        "decision_latency_s": decision_latencies,
        "mean_decision_latency_s": (
            sum(decision_latencies) / len(decision_latencies)
            if decision_latencies else None
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
