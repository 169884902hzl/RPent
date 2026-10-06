"""CPU routes from immutable public prefixes; no physics or contact is run."""

import argparse
from collections import Counter
import hashlib
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np

from robots.libero.v5_state import Candidate, Entity


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class CPUStop(Exception):
    pass


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--coverage", type=Path, required=True)
    parser.add_argument("--coverage-sha", required=True)
    parser.add_argument("--runtime", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    assert sha(args.coverage) == args.coverage_sha
    coverage = json.loads(args.coverage.read_text())
    spec = importlib.util.spec_from_file_location("place548_cpu_runtime", args.runtime)
    runtime = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(runtime)
    eligible = [r for r in coverage["cases"] if r["target"] and r["target"]["name"] == "cabinet"
                and r["type"] == "place_on"]
    inputs = {r["captured_ledger"] for r in eligible}
    ledgers = {path: Path(path).read_text().splitlines() for path in inputs}
    results = []
    for entry in eligible:
        row = json.loads(ledgers[entry["captured_ledger"]][entry["line"] - 1])
        public = row["first_attempt"]["public_before"]
        entities = {e["id"]: Entity(**{k: v for k, v in e.items() if k in Entity.__dataclass_fields__})
                    for e in public["entities"]}
        robot = public["robot"]
        action = Candidate.from_text(entry["selected"])
        primitives = SimpleNamespace(_last_obs_eef_pos=np.asarray(robot["eef_xyz"]),
                                     _last_obs_gripper=robot["gripper_opening"],
                                     env=SimpleNamespace(terminated=False, truncated=False))
        scene = SimpleNamespace(entities=entities, view_axes=((1, 0, 0), (0, -1, 0)))
        executor = runtime.V5Executor(SimpleNamespace(primitives=primitives), scene,
                                      strict_place_v6=True, target_cache_v1=True, held_occlusion_v1=True)
        executor.held = robot["held"]
        # Offset is not serialized in the public prefix. A zero placeholder
        # permits the CPU route to stop before any movement; no waypoint
        # reachability or physical-success claim uses this placeholder.
        executor.held_offset = np.zeros(3)
        support = executor.measured_placement_target(action)
        events = []
        def move(xyz, gripper):
            events.append({"route": "geometric_support", "gripper": gripper})
            raise CPUStop()
        def contact(prompt, chunks, stop):
            events.append({"route": "contact_subtask", "prompt": prompt, "chunks": chunks, "stop": stop})
            raise CPUStop()
        executor.move, executor.vla_act = move, contact
        error, receipt = None, {}
        try:
            executor._execute(action, receipt, None)
        except CPUStop:
            pass
        except Exception as failure:
            error = f"{type(failure).__name__}: {failure}"
        expected_ids = {s["id"] for s in entry["current_visible_associated_top_surfaces"]}
        results.append({"case": entry["case"], "selected": entry["selected"],
                        "resolved_support_id": support.id if support else None,
                        "resolved_support_matches_unique_public_part": support is not None and expected_ids == {support.id},
                        "events": events, "error": error, "receipt": receipt,
                        "captured_ledger": entry["captured_ledger"], "line": entry["line"]})
    text = args.runtime.read_text()
    start = text.index('        if action.tool == "place":')
    end = text.index('        if action.tool == "articulate":', start)
    report = {"version": "place548-public-support-route/1", "scope": "CPU route only; zero motion/contact actions; original labels and receipts unchanged",
              "coverage_sha256": sha(args.coverage), "runtime_path": str(args.runtime),
              "runtime_sha256": sha(args.runtime), "place_branch_sha256": hashlib.sha256(text[start:end].encode()).hexdigest(),
              "script_sha256": sha(__file__), "cases": results,
              "summary": {"cases": len(results), "unique_support_matches": sum(r["resolved_support_matches_unique_public_part"] for r in results),
                          "exceptions": sum(r["error"] is not None for r in results),
                          "route_counts": dict(Counter(event["route"] for r in results for event in r["events"]))}}
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"output": str(args.output), "sha256": sha(args.output), **report["summary"]}))


if __name__ == "__main__":
    main()
