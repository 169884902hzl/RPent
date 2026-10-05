# Copyright 2026 Zhilun Hu.
# SPDX-License-Identifier: Apache-2.0
"""Four true Pi0.5 noise seeds from one restored original-task branch point.

The callable runs on an owned live executor. It changes neither the shared
RPent service nor the collection loop. CLI preparation reads explicit manifest
files only; it does not execute actions, create training rows, or start servers.
Freeze registration is required before the callable can execute branches.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path

import numpy as np

from robots.libero.v5_collection import accepted_branch
from robots.libero.v5_state import serialize

SEED_CONTRACT = "pi05_policy_noise_seed/1"
MANIFEST_SCHEMA = "pi05_original_four_seed_branch/1"
MAX_SEED = 2**63 - 1
ORIGINAL_SUITES = {"libero_spatial", "libero_object", "libero_goal", "libero_10"}
SCENE_FIELDS = (
    "entities", "vocabulary", "last_measurement_s", "_scores", "_ids", "support_z",
    "fixture_measurement_evidence", "rejected_fixture_measurements", "fixture_front_axes",
    "_rejected_fixture_entities", "perception_evidence", "measurement_clouds",
    "work_surface_measurement", "_drawer_endpoint_anchors",
)
EXECUTOR_FIELDS = (
    "held", "held_offset", "receipts", "target_cache", "last_verification_measurements",
    "motion_evidence", "public_recovery", "wrist_scan_direction",
)
PHYSICAL_TOOLS = {
    "grasp", "regrasp_restage", "place", "adjust_place", "articulate", "card_next", "vla_subtask",
}


def json_text(value: object, *, indent: int | None = None) -> str:
    """Serialize private NumPy RPC records without dropping diagnostics."""
    def convert(item):
        if isinstance(item, np.ndarray):
            return item.tolist()
        if isinstance(item, np.generic):
            return item.item()
        raise TypeError(f"unsupported branch diagnostic: {type(item).__name__}")
    return json.dumps(value, default=convert, allow_nan=False, ensure_ascii=False,
                      sort_keys=True, indent=indent)


def digest(value: object) -> str:
    return hashlib.sha256(json_text(value).encode()).hexdigest()


def file_sha(path: str | Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def explicit_json(entry: dict) -> dict:
    """Read one registered file, with no directory discovery."""
    path = Path(entry["path"])
    if any(part in {"sealed_test_v4", "sealed_test"} for part in path.parts):
        raise ValueError("sealed inputs are not branch collection inputs")
    if file_sha(path) != entry["sha256"]:
        raise ValueError(f"registered file identity changed: {path}")
    return json.loads(path.read_text())


def validate_plan(plan: dict, *, require_frozen: bool = True) -> dict:
    """Require four disjoint policy-noise ranges and original train init10–39."""
    if plan["schema"] != MANIFEST_SCHEMA:
        raise ValueError("unexpected explicit branch manifest schema")
    noise_calls = plan["max_noise_calls"]
    if isinstance(noise_calls, bool) or not isinstance(noise_calls, int) or noise_calls < 1:
        raise ValueError("positive registered noise-call budget required")
    seeds = plan["policy_noise_base_seeds"]
    if len(seeds) != 4 or len(set(seeds)) != 4:
        raise ValueError("exactly four different policy noise base seeds required")
    for seed in seeds:
        if isinstance(seed, bool) or not isinstance(seed, int) or not 0 <= seed <= MAX_SEED - noise_calls + 1:
            raise ValueError("registered policy noise seed range is invalid")
    if any(b - a < noise_calls for a, b in zip(sorted(seeds), sorted(seeds)[1:])):
        raise ValueError("per-chunk policy noise seed ranges must not overlap")
    episodes = plan["episodes"]
    identities = []
    for episode in episodes:
        suite, task, seed = (episode[k] for k in ("suite", "task", "seed"))
        if (suite not in ORIGINAL_SUITES or isinstance(task, bool) or not isinstance(task, int)
                or not 0 <= task < 10 or isinstance(seed, bool) or not isinstance(seed, int)
                or not 10 <= seed < 40):
            raise ValueError("collection only admits original40 task0–9 train init10–39")
        identities.append((suite, task, seed))
    if len(set(identities)) != len(identities):
        raise ValueError("duplicate registered original episode")
    freeze = explicit_json(plan["freeze"])
    if require_frozen and freeze.get("status") != "frozen":
        raise ValueError("physical branch collection requires a frozen runtime identity")
    source = plan["source_files"]
    source_root = Path(__file__).resolve().parents[1]
    if not source:
        raise ValueError("explicit source file identities required")
    for name, entry in source.items():
        if file_sha(entry["path"]) != entry["sha256"] or freeze["source_sha256"].get(name) != entry["sha256"]:
            raise ValueError(f"source differs from registered freeze: {name}")
    required = {"robots/libero/v5_state.py", "robots/libero/v5_runtime.py",
                "robots/libero/v5_collection.py", "robots/libero/v5_seeded_vla_server.py",
                "scripts/probe_v5_multiseed509_original.py"}
    if not required <= source.keys():
        raise ValueError("renderer, executor, judge, seeded server and collector identities required")
    for name in required:
        if Path(source[name]["path"]).resolve() != (source_root / name).resolve():
            raise ValueError("registered file must identify this live source snapshot: " + name)
    identity = plan["seeded_service_identity"]
    if (identity["seed_contract"] != SEED_CONTRACT or identity["embodiment"] != "libero"
            or identity["server_sha256"] != source["robots/libero/v5_seeded_vla_server.py"]["sha256"]):
        raise ValueError("registered service is not the dedicated original seeded service")
    return freeze


class SeededBranchClient:
    """Inject a different real policy-noise seed on every executed chunk."""

    def __init__(self, model, base_seed: int, max_noise_calls: int, expected_identity: dict):
        if (isinstance(base_seed, bool) or not isinstance(base_seed, int) or base_seed < 0
                or isinstance(max_noise_calls, bool) or not isinstance(max_noise_calls, int)
                or max_noise_calls < 1 or base_seed > MAX_SEED-max_noise_calls+1):
            raise ValueError("invalid registered noise seed range")
        self.model, self.base_seed, self.max_noise_calls = model, base_seed, max_noise_calls
        self.calls = []
        actual = model._client.call("vla.seeded_identity", timeout_s=30)
        if actual != expected_identity or actual.get("seed_contract") != SEED_CONTRACT:
            raise ValueError("live service identity differs from dedicated seed registration")

    def predict(self, obs: dict, options: dict | None = None) -> np.ndarray:
        index = len(self.calls)
        if index >= self.max_noise_calls:
            raise RuntimeError("registered policy noise-call budget exhausted")
        options = dict(options or {})
        if options != {"mode": "eval"}:
            raise ValueError("branch model only accepts the unchanged eval-mode client call")
        options["seed"] = self.base_seed + index
        record = {"chunk_index": index, "policy_noise_seed": options["seed"], "status": "requested"}
        self.calls.append(record)
        try:
            actions = np.asarray(self.model.predict(obs, options=options))
            if actions.ndim != 2 or actions.shape[1] != 7 or not len(actions) or not np.isfinite(actions).all():
                raise ValueError("invalid LIBERO policy action chunk")
            record.update(status="returned", returned_actions=len(actions), dtype=actions.dtype.str,
                          action_sha256=hashlib.sha256(actions.tobytes(order="C")).hexdigest())
        except Exception as error:
            record.update(status="instrument_error", error=repr(error))
            raise
        return actions


def capture_public(scene, executor, toolkit) -> dict:
    """Save the same public caches used by the live original collection loop."""
    return {
        "scene": {name: copy.deepcopy(getattr(scene, name)) for name in SCENE_FIELDS},
        "executor": {name: copy.deepcopy(getattr(executor, name)) for name in EXECUTOR_FIELDS},
        "observation": copy.deepcopy(executor.p._last_obs),
        "flags": (executor.p.env.terminated, executor.p.env.truncated, toolkit._solved),
    }


def restore_branch(snapshot, public, *, rpc, scene, executor, toolkit, request, args, choices, card) -> None:
    """Restore verified physics, then require identical public serialized bytes."""
    rpc.call("oracle.restore", args=[snapshot], timeout_s=120)
    executor.p.env.terminated, executor.p.env.truncated, toolkit._solved = public["flags"]
    executor.p.env.last_obs = copy.deepcopy(public["observation"])
    executor.p.set_obs(copy.deepcopy(public["observation"]))
    for name, value in public["scene"].items():
        setattr(scene, name, copy.deepcopy(value))
    for name, value in public["executor"].items():
        setattr(executor, name, copy.deepcopy(value))
    restored = serialize(args.instruction_override, list(scene.entities.values()),
                         executor.p._last_obs_gripper, executor.held, executor.receipts,
                         view_axes=scene.view_axes, choices=choices, card=card,
                         failure_counts=getattr(args, "candidate_failure_counts_v1", False),
                         recovery_status=executor.public_recovery)
    if restored.encode() != request["context"].encode():
        raise RuntimeError("restored measured request bytes differ from branch point")


def executed_steps(traces: list[dict]) -> int:
    return sum(int(trace.get("executed_action_count", trace.get("steps_used", 0))) for trace in traces)


def wilson(successes: int, trials: int) -> list[float] | None:
    if not trials:
        return None
    z = 1.959963984540054
    p = successes / trials
    centre = (p + z*z / (2*trials)) / (1 + z*z/trials)
    half = z * np.sqrt(p*(1-p)/trials + z*z/(4*trials*trials)) / (1 + z*z/trials)
    return [float(centre-half), float(centre+half)]


def collect_four_seed_branches(*, plan, args, request, choices, selected_indices, scene,
                               executor, toolkit, rpc, required_objects, original_object_names,
                               card=None) -> dict:
    """Collect registered expert+two alternatives, restoring before every seed.

    Private grasp hold metrology labels only the executed grasp; it never
    changes the runtime receipt. Its additional diagnostic steps are counted.
    Unexecuted, unmeasured and instrument-error trials stay unknown. The
    ordinary live collection loop must explicitly opt into this callable.
    """
    freeze = validate_plan(plan)
    episode = {name: getattr(args, name) for name in ("suite", "task", "seed")}
    if episode not in plan["episodes"]:
        raise ValueError("live episode was not registered in the explicit manifest")
    if not 1 <= len(selected_indices) <= 3 or len(set(selected_indices)) != len(selected_indices):
        raise ValueError("register the expert plus at most two distinct alternatives")
    if any(not 0 <= index < len(choices) for index in selected_indices):
        raise ValueError("branch candidate index outside request")
    if request["options"] != [candidate.text() for candidate in choices]:
        raise ValueError("candidate order differs from the saved request")
    before = rpc.call("oracle.status", timeout_s=120)
    before["done"] = bool(before["done"] or toolkit.solved())
    snapshot = rpc.call("oracle.snapshot", timeout_s=120)
    public = capture_public(scene, executor, toolkit)
    original_model = executor.p.model
    records = []
    for index in selected_indices:
        candidate = choices[index]
        for seed in plan["policy_noise_base_seeds"]:
            restore_branch(snapshot, public, rpc=rpc, scene=scene, executor=executor,
                           toolkit=toolkit, request=request, args=args, choices=choices, card=card)
            row = {"code": f"C{index}", "action": candidate.text(), "policy_noise_base_seed": seed,
                   "accepted": None, "label_judge": "physics_branch", "executed": False,
                   "executed_steps": 0, "diagnostic_steps": 0, "policy_noise_calls": []}
            client = None
            attempt_started = False
            try:
                if candidate.tool not in PHYSICAL_TOOLS | {"finish", "ask_help"}:
                    row["unknown_reason"] = "candidate_not_physically_registered"
                    continue
                if before["done"] and candidate.tool not in {"finish", "ask_help"}:
                    row["unknown_reason"] = "native_terminal_state_not_executed"
                    continue
                client = SeededBranchClient(original_model, seed, plan["max_noise_calls"],
                                            plan["seeded_service_identity"])
                executor.p.model = client
                reference = None
                measured_grasp = candidate
                if candidate.tool == "card_next" and card:
                    from robots.libero.v5_cards import resolve_card
                    measured_grasp = resolve_card(card, list(scene.entities.values()), executor.held)
                    if measured_grasp is None:
                        row["unknown_reason"] = "card_has_no_unique_measured_binding"
                        continue
                if measured_grasp.tool in {"grasp", "regrasp_restage"}:
                    name = original_object_names[measured_grasp.object]
                    reference = rpc.call("oracle.grasp_reference", kwargs={"name": name}, timeout_s=120)
                attempt_started = True
                receipt = executor.execute(candidate, card=card)
                row["receipt"] = copy.deepcopy(receipt)
                row["executed_steps"] = executed_steps(executor.motion_evidence)
                row["executed"] = bool(receipt.get("executed") and row["executed_steps"] > 0)
                after = rpc.call("oracle.status", timeout_s=120)
                after["done"] = bool(after["done"] or toolkit.solved())
                row.update(before=copy.deepcopy(before), after=copy.deepcopy(after),
                           motion_evidence=copy.deepcopy(executor.motion_evidence),
                           verification_measurements=copy.deepcopy(executor.last_verification_measurements))
                if receipt.get("error"):
                    row["unknown_reason"] = "execution_or_instrument_error"
                elif candidate.tool in PHYSICAL_TOOLS and not row["executed"]:
                    row["unknown_reason"] = "no_physical_execution_evidence"
                else:
                    label_receipt = receipt
                    if reference is not None:
                        metrology = rpc.call("oracle.measure_grasp_hold", kwargs={
                            "name": name, "reference": reference, "duration_s": .5}, timeout_s=120)
                        row["private_grasp_metrology"] = metrology
                        row["diagnostic_steps"] = metrology["diagnostic_actions"]
                        label_receipt = {**receipt, "grasp_verified": metrology["truth"]["success"]}
                    row["accepted"] = accepted_branch(candidate, label_receipt, before, after,
                                                       required_objects=required_objects)
                    if row["accepted"] is None:
                        row["unknown_reason"] = "no_verified_subgoal_label"
            except Exception as error:
                row.update(accepted=None, unknown_reason="instrument_error", instrument_error=repr(error))
            finally:
                if attempt_started:
                    row["motion_evidence"] = copy.deepcopy(executor.motion_evidence)
                    row["executed_steps"] = executed_steps(executor.motion_evidence)
                if client is not None:
                    row["policy_noise_calls"] = copy.deepcopy(client.calls)
                executor.p.model = original_model
                records.append(row)
                restore_branch(snapshot, public, rpc=rpc, scene=scene, executor=executor,
                               toolkit=toolkit, request=request, args=args, choices=choices, card=card)
    by_candidate = {}
    for index in selected_indices:
        trials = [row for row in records if row["code"] == f"C{index}"]
        known = [row for row in trials if row["accepted"] is not None]
        successes = sum(row["accepted"] is True for row in known)
        by_candidate[f"C{index}"] = {"trials": len(trials), "known_trials": len(known),
            "unknown_trials": len(trials)-len(known), "successes": successes,
            "acceptable_branch_rate": successes/len(known) if known else None,
            "wilson_95": wilson(successes, len(known))}
    return {"schema": MANIFEST_SCHEMA, "episode": episode,
            "freeze_sha256": plan["freeze"]["sha256"], "freeze_commit": freeze["commit"],
            "source_sha256": {key: item["sha256"] for key, item in plan["source_files"].items()},
            "seeded_service_identity": plan["seeded_service_identity"],
            "request_sha256": digest(request), "snapshot_sha256": digest(snapshot),
            "request": copy.deepcopy(request), "branches": records, "candidate_statistics": by_candidate,
            "unknown_actions": [f"C{i}" for i in range(len(choices)) if i not in selected_indices],
            "new_training_rows": 0,
            "scope": "four-seed branch evidence; rates describe registered noise samples, not independent scenes"}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--prepare-only", action="store_true", required=True)
    args = parser.parse_args()
    plan = json.loads(args.manifest.read_text())
    freeze = validate_plan(plan)
    result = {"manifest_sha256": file_sha(args.manifest), "freeze_commit": freeze["commit"],
              "episodes": len(plan["episodes"]), "policy_noise_base_seeds": plan["policy_noise_base_seeds"],
              "max_noise_calls": plan["max_noise_calls"], "physical_actions_executed": 0,
              "new_training_rows": 0,
              "entrypoint": "scripts.probe_v5_multiseed509_original.collect_four_seed_branches"}
    with args.output.open("x") as output:
        output.write(json_text(result, indent=2) + "\n")
    print(json_text(result))


if __name__ == "__main__":
    main()
