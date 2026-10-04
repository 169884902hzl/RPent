"""Instruction-only v6 corruption; images, choices and physical labels stay fixed."""

import copy
import hashlib
import json


def instruction(state: str) -> str:
    first = state.splitlines()[0]
    if not first.startswith("instruction "):
        raise ValueError("state has no leading instruction")
    value = json.loads(first.removeprefix("instruction "))
    if not isinstance(value, str):
        raise ValueError("instruction must be text")
    return value


def replace_instruction(row: dict, donor: str) -> dict:
    """Change only the leading instruction line, with provenance outside input."""
    state = row["request"]["state"]
    original = instruction(state)
    if donor == original or not donor.strip():
        raise ValueError("corruption requires a different nonempty instruction")
    result = copy.deepcopy(row)
    _, separator, rest = state.partition("\n")
    result["request"]["state"] = "instruction " + json.dumps(donor, ensure_ascii=True) + separator + rest
    result["v6_text_provenance"] = {
        "rule": "instruction_swap_train_only/1",
        "original_state_sha256": hashlib.sha256(state.encode()).hexdigest(),
        "original_instruction_sha256": hashlib.sha256(original.encode()).hexdigest(),
        "visible_instruction_sha256": hashlib.sha256(donor.encode()).hexdigest(),
        "labels_unchanged": True,
    }
    return result
