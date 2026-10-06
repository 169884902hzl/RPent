"""CPU-only contact routing check from 24 frozen public measurements."""

from collections import Counter
import hashlib
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import numpy as np

from robots.libero.v5_runtime import V5Executor
from robots.libero.v5_state import Candidate, Entity


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    directory = Path(__file__).resolve().parent
    root = directory.parents[3]
    source = root / "robots/libero/v5_runtime.py"
    inputs = directory / "public_prefixes_24.jsonl"
    assert sha(inputs) == "bc228dc6333f5afa29aa9395912180ae0db673c4fb1c6af263da4a291b5ba822"
    cases = []
    for line in inputs.read_text().splitlines():
        row = json.loads(line)
        public = row["public_before"]
        entities = {value["id"]: Entity(**{k: v for k, v in value.items()
                    if k in Entity.__dataclass_fields__}) for value in public["entities"]}
        robot = public["robot"]
        primitives = SimpleNamespace(_last_obs_eef_pos=np.asarray(robot["eef_xyz"]),
            _last_obs_gripper=robot["gripper_opening"],
            env=SimpleNamespace(terminated=False, truncated=False))
        scene = SimpleNamespace(entities=entities)
        executor = V5Executor(SimpleNamespace(primitives=primitives), scene,
                              fixture_in_contact_v1=True, held_occlusion_v1=True)
        executor.held = robot["held"]
        # Routing depends on public entity identity/geometry, not this offset.
        # No movement or contact is executed during this CPU check.
        executor.held_offset = np.zeros(3)
        motions, contacts = [], []
        def move(*args, **kwargs):
            motions.append(args)
            raise AssertionError("visible drawer surface requested geometric descent")
        def contact(prompt, budget, stop):
            contacts.append({"prompt": prompt, "budget": budget, "stop": stop})
            return {"executed": False, "chunks": 0, "stop": "cpu_no_contact_execution",
                    "object_released": False}
        executor.move, executor.vla_act = move, contact
        action = Candidate("place", row["selected"]["object"],
                           row["selected"]["target"], row["selected"]["mode"])
        receipt, error = {}, None
        try:
            executor._execute(action, receipt, None)
        except Exception as failure:
            error = f"{type(failure).__name__}: {failure}"
        category = ("development_exception" if error else "contact_route_uniquely_bound"
                    if contacts else "public_binding_unmeasured"
                    if receipt.get("failure_reason") == "selected_instance_not_uniquely_measured"
                    else "unexpected_route")
        cases.append({"case": row["case"], "category": category, "error": error,
                      "geometric_moves_requested": len(motions), "contact_route": contacts,
                      "public_receipt": receipt, "ledger": row["ledger"], "line": row["line"]})
    runtime_text = source.read_text()
    start = runtime_text.index('        if action.tool == "place":')
    stop = runtime_text.index('        if action.tool == "articulate":', start)
    result = {"version": "place544-public-prefix-routing/1", "input": str(inputs),
              "input_sha256": sha(inputs), "runtime_path": str(source),
              "runtime_sha256_at_cpu_check": sha(source), "script_sha256": sha(Path(__file__)),
              "place_branch_sha256": hashlib.sha256(runtime_text[start:stop].encode()).hexdigest(),
              "actual_command": "PYTHONPATH=. python3 " + str(Path(__file__).resolve().relative_to(root)),
              "interpreter": sys.executable, "python_version": sys.version.split()[0],
              "scope": "CPU control-route check only; contact stub performs zero actions; no physical replay or success claim; no original label or verdict changed",
              "fixture_in_contact_v1": True, "cases": cases,
              "category_counts": dict(Counter(case["category"] for case in cases)),
              "geometric_moves_requested": sum(case["geometric_moves_requested"] for case in cases)}
    output = directory / "public_prefix_routing_CPU.json"
    output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"report": str(output), "sha256": sha(output),
                      "category_counts": result["category_counts"],
                      "geometric_moves_requested": result["geometric_moves_requested"]}))


if __name__ == "__main__":
    main()
