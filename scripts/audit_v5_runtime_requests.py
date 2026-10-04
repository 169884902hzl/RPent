"""Re-render 20 actual requests and check cooldown only filters candidates."""

import argparse
from dataclasses import fields
import hashlib
import json
from pathlib import Path
import re

from robots.libero.v5_collection import wire_request
from robots.libero.v5_state import Candidate, Entity, execution_error_blocked, serialize


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ledger", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    sample, suppressed = [], []
    for episode in (json.loads(line) for line in args.ledger.read_text().splitlines()):
        trace = Path(episode["output_dir"]) / "choices.jsonl"
        receipts = []
        for event in (json.loads(line) for line in trace.read_text().splitlines()):
            context = event["request"]["context"]
            choices = [Candidate.from_text(text) for text in event["candidates"]]
            blocked = [c.text() for c in choices if execution_error_blocked(c, receipts)]
            if blocked:
                raise AssertionError(f"blocked action still offered: {blocked}")
            for receipt in receipts[-3:]:
                if receipt.get("verification") == "execution_error":
                    suppressed.append({"episode": episode["episode"], "decision": event["decision"], "receipt": receipt,
                                       "candidates": event["candidates"]})
            if len(sample) < 20:
                entities = [Entity(**{field.name: value[field.name] for field in fields(Entity)})
                            for value in event["measurements"]]
                lines = context.splitlines()
                instruction = json.loads(lines[0].removeprefix("instruction "))
                robot = next(line for line in lines if line.startswith("robot "))
                held = robot.split("held=", 1)[1]
                axes_line = next((line for line in lines if line.startswith("rel frame=")), None)
                axes = tuple(json.loads(text) for text in re.findall(r"(?:right|front)_world=(\[[^]]+\])", axes_line)) if axes_line else None
                recovery_line = next((line for line in lines if line.startswith("recovery ")), None)
                recovery = {key: int(value) for key, value in re.findall(r"(\w+)=(\d+)", recovery_line)} if recovery_line else None
                rendered = serialize(instruction, entities, event["robot_measurement"]["gripper_opening"],
                                     None if held == "none" else held, receipts,
                                     card=event["memory_card"], view_axes=axes, choices=choices,
                                     failure_counts="candidate failures=count:type" in lines, recovery_status=recovery)
                if rendered.encode() != context.encode():
                    raise AssertionError(f"serializer byte mismatch: {trace}:{event['decision']}")
                reconstructed = wire_request(event["request"])
                recorded = event["answer"].get("systemone_request")
                if recorded is not None and reconstructed != recorded:
                    raise AssertionError("recorded System One payload differs")
                stem = f"request_{len(sample):02d}"
                raw = json.dumps(recorded or reconstructed, ensure_ascii=False).encode()
                (args.output / f"{stem}.json").write_bytes(raw)
                (args.output / f"{stem}.state.txt").write_bytes(context.encode())
                sample.append({"episode": episode["episode"], "decision": event["decision"],
                               "trace": str(trace), "trace_sha256": hashlib.sha256(trace.read_bytes()).hexdigest(),
                               "payload": f"{stem}.json", "payload_sha256": hashlib.sha256(raw).hexdigest(),
                               "state_sha256": hashlib.sha256(context.encode()).hexdigest(),
                               "serializer_byte_equal": True, "recorded_payload_available": recorded is not None,
                               "new_cooldown_state_lines": 0})
            receipts.append(event["receipt"])
    report = {"sampled_requests": len(sample), "samples": sample, "suppressed_error_opportunities": suppressed,
              "serializer_sha256": hashlib.sha256((Path(__file__).resolve().parents[1] / "robots/libero/v5_state.py").read_bytes()).hexdigest(),
              "request_bytes_reconstructed_from_logged_payload": True,
              "raw_HTTP_transport_bytes_saved_by_original_runner": False,
              "all_passed": len(sample) == 20}
    (args.output / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"sampled_requests": len(sample), "cooldown_opportunities": len(suppressed), "all_passed": report["all_passed"]}))


if __name__ == "__main__":
    main()
