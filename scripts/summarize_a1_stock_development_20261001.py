"""Summarize declared A1 development ledgers without replaying any episode."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

from audit_a1m_tool_receipts_20261001 import summarize as receipt_summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    plan_bytes = args.plan.read_bytes()
    plan = json.loads(plan_bytes)
    expected = {(e["suite"], e["task"], e["seed"]) for e in plan["episodes"]}
    if len(expected) != len(plan["episodes"]):
        raise ValueError("duplicate planned scenes")
    sources, missing, rows, seen = [], [], [], set()

    def read(path: Path) -> bytes:
        data = path.read_bytes()
        sources.append({"path": str(path), "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)})
        return data

    for declared in plan["ledgers"]:
        ledger = Path(declared["path"])
        if not ledger.exists():
            missing.append(str(ledger))
            continue
        data = read(ledger)
        if declared.get("sha256") and sources[-1]["sha256"] != declared["sha256"]:
            raise ValueError("immutable completed ledger changed")
        for line in data.splitlines():
            record = json.loads(line)
            e = record["episode"]
            key = (e["suite"], e["task"], e["seed"])
            if key not in expected or key in seen:
                raise ValueError(f"unplanned or repeated scene: {key}")
            seen.add(key)
            root = Path(record["output_dir"])
            tag = f"{key[0]}_t{key[1]}_s{key[2]}"
            if root != Path(declared["root"]) / tag:
                raise ValueError("episode path differs from declared ledger root")
            files = {"cli": root / "cli.log", "states": root / "states.json",
                     "command": root / "command.json", "transcript": root / f"transcript_{tag.removeprefix('libero_')}.json"}
            blobs = {}
            for name, path in files.items():
                if not path.exists():
                    missing.append(str(path))
                    blobs[name] = None
                else:
                    blobs[name] = read(path)
            transcript = json.loads(blobs["transcript"]) if blobs["transcript"] else {}
            log = blobs["cli"].decode(errors="replace") if blobs["cli"] else ""
            states = json.loads(blobs["states"]) if blobs["states"] else None
            if states is not None:
                steps = states if isinstance(states, list) else states.get("steps", states.get("records", []))
                physical = any(s.get("terminated", False) for s in steps)
                if bool(record["official_success"]) != physical:
                    raise ValueError("ledger physical result differs from recorded states")
            else:
                physical = False
            finish = transcript.get("finish") or {}
            messages = transcript.get("messages", [])
            assistant = next((m for m in reversed(messages) if m.get("role") == "assistant"), {})
            last_text = str(assistant.get("content", ""))
            if physical:
                category = "physical_success"
            elif any(blob is None for blob in blobs.values()):
                category = "infrastructure_missing_artifact"
            elif "ModelHTTPError" in log and "400" in log and "context" in log:
                category = "context_rejected_http400"
            elif "model ended turn without a tool call" in log:
                category = "no_structured_call_markup" if any(s in last_text for s in ("tool_call", "tool_response", "<invoke", "<function", "```")) else "no_structured_call_prose"
            elif finish.get("status") == "success":
                category = "false_finish"
            elif finish.get("status") == "failure":
                category = "finish_failure_after_execution"
            elif "API planner timed out" in log or "API planner timed out" in str(transcript.get("error", "")):
                category = "planner_wall_budget_recorded"
            elif record["wall_s"] >= plan["budget"]["planner_timeout_s"] and not finish and not assistant:
                category = "planner_wall_budget_inferred"
            elif record["exit_code"] != 0:
                category = "infrastructure_cli_error"
            else:
                category = "unclassified"
            rows.append({**record, "physical_success": physical,
                         "explicit_successful_finish": physical and finish.get("status") == "success",
                         "primary_terminal": category, "last_assistant_text": last_text[:2000],
                         "transcript_receipts": receipt_summary(messages)})

    generation = defaultdict(Counter)
    latest_history = {}
    raw_counts = Counter()
    tokenizer = None
    if plan.get("response_logs"):
        from tokenizers import Tokenizer
        token_path = Path(plan["tokenizer"])
        read(token_path)
        tokenizer = Tokenizer.from_file(str(token_path))
    for declared in plan.get("response_logs", []):
        path = Path(declared["path"])
        if not path.exists():
            missing.append(str(path))
            continue
        digest = hashlib.sha256()
        size = 0
        with path.open("rb") as source:
            for line in source:
                digest.update(line)
                size += len(line)
                try:
                    record = json.loads(line)
                except ValueError:
                    raw_counts["invalid_lines"] += 1
                    continue
                raw_counts["responses"] += 1
                raw_counts[f"http_{record['status_code']}"] += 1
                response_model = record.get("response", {}).get("model")
                if response_model:
                    raw_counts[f"response_model:{response_model}"] += 1
                messages = record.get("request", {}).get("messages", [])
                system = "\n".join(str(m.get("content", "")) for m in messages if m.get("role") == "system")
                tags = set(re.findall(r"/episodes/(libero_\w+_t\d+_s\d+)", system))
                if len(tags) != 1:
                    raw_counts["unassigned_requests"] += 1
                    continue
                tag = tags.pop()
                latest_history[tag] = {"request_sha256": record["request_sha256"], **receipt_summary(messages)}
                usage = record.get("response", {}).get("usage") or {}
                generation[tag]["largest_prompt_tokens"] = max(generation[tag]["largest_prompt_tokens"], usage.get("prompt_tokens") or 0)
                for choice in record.get("response", {}).get("choices", []):
                    tools = choice.get("message", {}).get("tool_calls") or []
                    names = [c["function"]["name"] for c in tools]
                    ids = choice.get("token_ids")
                    generation[tag]["replies"] += 1
                    generation[tag]["structured_tool_replies"] += bool(names)
                    if ids is None:
                        generation[tag]["original_tokens_unavailable"] += 1
                        continue
                    raw = tokenizer.decode(ids, skip_special_tokens=False)
                    original_names = re.findall(r"<function=([^>\s]+)>", raw)
                    generation[tag]["generation_parser_name_mismatches"] += original_names != names
                    if not names:
                        generation[tag]["no_structured_tool_replies"] += 1
                        latest_history[tag]["last_no_tool_generation"] = raw[:2000]
        sha = digest.hexdigest()
        if declared.get("sha256") and sha != declared["sha256"]:
            raise ValueError("immutable raw response log changed")
        sources.append({"path": str(path), "sha256": sha, "bytes": size})

    suites = defaultdict(Counter)
    for row in rows:
        c = suites[row["episode"]["suite"]]
        c["attempted"] += 1
        c["physical_success"] += row["physical_success"]
        c["successful_finish"] += row["explicit_successful_finish"]
        c[f"terminal_{row['primary_terminal']}"] += 1
    summary = {"purpose": "A1_stock_development_diagnostic_not_Table_A_or_final_test", "condition": plan["condition"],
               "plan_sha256": hashlib.sha256(plan_bytes).hexdigest(), "planned": len(expected), "attempted": len(rows),
               "complete": seen == expected and not missing,
               "physical_success": sum(r["physical_success"] for r in rows),
               "successful_finish": sum(r["explicit_successful_finish"] for r in rows),
               "missing": missing, "unattempted": [list(k) for k in sorted(expected - seen)],
               "terminal_counts": dict(Counter(r["primary_terminal"] for r in rows)),
               "by_suite": {k: dict(v) for k, v in suites.items()}, "upstream_counts": dict(raw_counts),
               "generation_by_episode": {k: dict(v) for k, v in generation.items()},
               "limits": "No episodes or model requests replayed. Intermediate Pi0 false receipts are not proven physical failures. Latest captured history can omit execution of the last generated calls. Framework/dependencies/parser change jointly; exact leaderboard parity and API-repeat variability remain unverified."}
    args.output.mkdir(parents=True, exist_ok=False)
    for name, value in (("summary.json", summary), ("episodes.json", rows), ("sources.json", sources), ("executed_tool_receipts.json", latest_history)):
        (args.output / name).write_text(json.dumps(value, indent=2) + "\n")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
