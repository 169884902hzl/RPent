import random
from types import SimpleNamespace

import pytest

from robots.libero.v5_full_task import add_full_task_choice, execute_full_task
from robots.libero.v5_state import Candidate


def test_full_task_cap_and_round_trip():
    choices = [Candidate("grasp", f"e{i}", mode="direct") for i in range(20)]
    choices += [Candidate(tool) for tool in ("finish", "ask_help", "retreat", "reperceive")]
    result = add_full_task_choice(choices, random.Random(5))
    assert len(result) == 24
    assert all(Candidate(tool) in result for tool in ("finish", "ask_help", "retreat", "reperceive"))
    assert Candidate.from_text("vla_task()") in result


def test_full_task_uses_public_instruction_and_keeps_native_stop():
    calls = []
    executor = SimpleNamespace(
        vla_task_diagnostic_v1=True, instruction="put the bowl in the drawer and close it",
        max_chunks=104,
        vla_act=lambda *args: calls.append(args) or {
            "executed": True, "chunks": 51, "stop": "execution_interrupted"},
        capture=lambda: None,
        scene=SimpleNamespace(vocabulary={"bowl", "drawer"}, refresh=lambda names: calls.append(names)),
    )
    receipt = {}
    execute_full_task(executor, receipt)
    assert calls[0] == (executor.instruction, 104, "chunk_budget")
    assert receipt["stop"] == "execution_interrupted"
    assert receipt["verification"] == "unmeasured"
    assert "official_success" not in receipt
    executor.vla_task_diagnostic_v1 = False
    with pytest.raises(ValueError, match="disabled"):
        execute_full_task(executor, {})
