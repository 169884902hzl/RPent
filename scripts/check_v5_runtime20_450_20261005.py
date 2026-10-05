"""Re-render 20 explicit saved requests without recomputing their physics."""

import argparse
import ast
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import sys


def digest(data):
    return hashlib.sha256(data).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--pairs", type=Path, required=True)
    parser.add_argument("--state-source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    spec = importlib.util.spec_from_file_location("runtime20_state", args.state_source)
    state = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = state
    spec.loader.exec_module(state)
    pairs = json.loads(args.pairs.read_text())["cases"]
    evidence = []
    for pair_index, pair in enumerate(pairs):
        path = Path(pair["after"]["trace"])
        records = [json.loads(line) for line in path.read_text().splitlines()]
        selected = sorted({0, len(records) - 1, len(records) // 2}) if pair_index < 2 else [0, len(records) - 1]
        for index in selected:
            record = records[index]
            request = record["request"]
            context = request["context"]
            lines = context.splitlines()
            instruction = json.loads(lines[0].removeprefix("instruction "))
            robot = re.fullmatch(r"robot gripper_opening=([\d.]+) held=(e\d+|none)",
                                 next(line for line in lines if line.startswith("robot ")))
            axis = next((line for line in lines if line.startswith("rel frame=")), None)
            axes = None
            if axis:
                parsed = re.search(r"right_world=(\[[^]]+\]) front_world=(\[[^]]+\])", axis)
                axes = tuple(tuple(ast.literal_eval(parsed[i])) for i in (1, 2))
            recovery = next((line for line in lines if line.startswith("recovery ")), None)
            recovery_status = {name: int(value) for name, value in re.findall(r"(\w+)=(\d+)", recovery)} if recovery else None
            entities = [state.Entity(**{key: tuple(value) if key in ("xyz", "lower", "upper") else value
                                       for key, value in entity.items() if key in state.Entity.__dataclass_fields__})
                        for entity in record["measurements"]]
            actions = [state.Candidate.from_text(text) for text in request["options"]]
            rendered = state.serialize(instruction, entities, float(robot[1]),
                                       None if robot[2] == "none" else robot[2],
                                       [r["receipt"] for r in records[:index]],
                                       card=record.get("memory_card"), view_axes=axes,
                                       choices=actions, failure_counts="candidate failures=count:type" in lines,
                                       recovery_status=recovery_status)
            recreated = {"context": rendered, "instruction": state.CHOICE_INSTRUCTION,
                         "options": [action.text() for action in actions]}
            old = json.dumps(request, sort_keys=True, ensure_ascii=True, separators=(",", ":")).encode()
            new = json.dumps(recreated, sort_keys=True, ensure_ascii=True, separators=(",", ":")).encode()
            evidence.append({"source": str(path), "source_sha256": digest(path.read_bytes()),
                             "line": index + 1, "original_request": request, "rerendered_request": recreated,
                             "state_utf8_byte_identical": context.encode() == rendered.encode(),
                             "canonical_request_bytes_identical": old == new,
                             "original_sha256": digest(old), "rerendered_sha256": digest(new)})
    if len(evidence) != 20:
        raise ValueError("20 explicit runtime requests required")
    args.output.mkdir(parents=True, exist_ok=False)
    with (args.output / "requests.jsonl").open("x") as stream:
        for row in evidence:
            stream.write(json.dumps(row) + "\n")
    report = {"requests": len(evidence), "source": str(args.state_source),
              "source_sha256": digest(args.state_source.read_bytes()),
              "state_byte_identical": sum(row["state_utf8_byte_identical"] for row in evidence),
              "canonical_request_identical": sum(row["canonical_request_bytes_identical"] for row in evidence),
              "passed": all(row["canonical_request_bytes_identical"] for row in evidence),
              "scope": "serializer bytes with recorded entities, receipts and recovery counters; not new physical replay",
              "cooldown_contract": "candidate removal only; existing failure-count lines stay in the serializer",
              "new_training_rows": 0}
    (args.output / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report))
    if not report["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
