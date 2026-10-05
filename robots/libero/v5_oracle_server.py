# Copyright 2026 Zhilun Hu.
# SPDX-License-Identifier: Apache-2.0
"""Original-task-only oracle RPC, kept separate from planner observations."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
from pathlib import Path

import numpy as np

from robots.libero.v5_env_server import V5EnvFacade, make_v5_env
from rpent.utils.serialization import to_numpy_tree

ORIGINAL_SUITES = {"libero_spatial", "libero_object", "libero_goal", "libero_10"}
WRAPPER_FIELDS = (
    "_elapsed_steps",
    "success_once",
    "fail_once",
    "returns",
    "success_episode_len",
    "prev_step_reward",
)


class OriginalOracleFacade(V5EnvFacade):
    """Offer private completion predicates and branch state restoration."""

    def __init__(self, env, *, meta: dict, native_diagnostic: bool = False, motion_trace_v1: bool = False) -> None:
        if (
            os.environ.get("LIBERO_TYPE") != "standard"
            or meta["suite"] not in ORIGINAL_SUITES
        ):
            raise ValueError("oracle RPC is restricted to the 40 original tasks")
        from libero.libero import get_libero_path
        from libero.libero.envs.bddl_utils import robosuite_parse_problem

        task = env.task_suite.get_task(meta["task"])
        path = (
            Path(get_libero_path("bddl_files")) / task.problem_folder / task.bddl_file
        )
        self._goals = robosuite_parse_problem(str(path))["goal_state"]
        self._bddl_sha = hashlib.sha256(path.read_bytes()).hexdigest()
        self._native_diagnostic = native_diagnostic
        self._native_success_events = []
        super().__init__(env, meta=meta, motion_trace_v1=motion_trace_v1)

    def step(self, action):
        """Record predicates at the exact native-success step, privately."""
        result = super().step(action)
        if self._native_diagnostic and bool(np.asarray(result[2]).any()):
            status = self.goal_status()
            self._native_success_events.append({
                "elapsed_steps": np.asarray(self._env._elapsed_steps).tolist(),
                "raw_termination": True,
                "satisfied_at_native_step": status["satisfied"],
                "all_predicates_at_native_step": status["done"],
            })
        return result

    def _register_rpc(self) -> None:
        super()._register_rpc()
        self._rpc.update(
            {
                "oracle.status": self.goal_status,
                "oracle.snapshot": self.snapshot,
                "oracle.restore": self.restore,
                "oracle.measurement_reference": self.measurement_reference,
                "oracle.controller_contract": self.controller_contract,
                "oracle.grasp_contacts": self.grasp_contacts,
                "oracle.grasp_reference": self.grasp_reference,
                "oracle.measure_grasp_hold": self.measure_grasp_hold,
            }
        )
        self._readonly_methods.update(("oracle.status", "oracle.snapshot", "oracle.measurement_reference", "oracle.controller_contract", "oracle.grasp_contacts", "oracle.grasp_reference"))

    def grasp_reference(self, name: str) -> dict:
        return self._env.env.workers[0].env_call("v5_grasp_reference", args=[name], target="self")

    def measure_grasp_hold(self, name: str, reference: dict, duration_s: float = .5) -> dict:
        """Post-trial private metrology, outside the policy's action budget."""
        return self._env.env.workers[0].env_call("v5_measure_grasp_hold", args=[name, reference, duration_s], target="self")

    def grasp_contacts(self) -> dict:
        """Private reference labels; never available on the PRO facade."""
        return self._env.env.workers[0].env_call("v5_grasp_contacts", target="self")

    def controller_contract(self) -> dict:
        """Return loaded control scales to original-task diagnostics only."""
        return to_numpy_tree(self._env.env.workers[0].env_call("v5_controller_contract", target="self"))

    def measurement_reference(self) -> dict:
        """Keep simulator references out of the normal measured-state facade."""
        return self._env.env.workers[0].env_call("v5_reference_geometry", target="self")

    def goal_status(self) -> dict:
        """Return independent predicate results to the oracle, never the planner."""
        worker = self._env.env.workers[0]
        checks = [
            bool(worker.env_call("_eval_predicate", args=[g])) for g in self._goals
        ]
        storage_open = {
            goal[2]: bool(worker.env_call("v5_storage_open", args=[goal[2]], target="self"))
            for goal in self._goals
            if goal[0] == "in" and len(goal) == 3
            and any(word in goal[2] for word in ("cabinet", "drawer", "microwave"))
        }
        result = {
            "goals": self._goals,
            "satisfied": checks,
            "done": bool(checks and all(checks)),
            "bddl_sha256": self._bddl_sha,
            "storage_open": storage_open,
        }
        if self._native_diagnostic:
            result["native_success_events"] = copy.deepcopy(self._native_success_events)
        return result

    def snapshot(self) -> dict:
        """Capture physics and rollout counters without integrating another step."""
        return to_numpy_tree(
            {
                "sim_state": self._env.env.workers[0].get_sim_state(),
                "actuator_state": self._env.env.workers[0].env_call("v5_actuator_state", target="self"),
                "counters": {
                    key: copy.deepcopy(getattr(self._env, key))
                    for key in WRAPPER_FIELDS
                    if hasattr(self._env, key)
                },
                "task": self._meta,
                "bddl_sha256": self._bddl_sha,
                "native_success_event_count": len(self._native_success_events),
            }
        )

    def restore(self, snapshot: dict) -> dict:
        """Restore a branch point and rebuild observation without a reset rollout."""
        if snapshot["task"] != self._meta or snapshot["bddl_sha256"] != self._bddl_sha:
            raise ValueError("snapshot belongs to another original task")
        worker = self._env.env.workers[0]
        state = np.asarray(snapshot["sim_state"])
        raw = worker.set_init_state(state)
        raw = worker.env_call("v5_restore_actuators", args=[snapshot["actuator_state"]], target="self")
        self._env.current_raw_obs = [raw]
        for key, value in snapshot["counters"].items():
            if key not in WRAPPER_FIELDS:
                raise ValueError(f"unsupported snapshot counter: {key}")
            setattr(self._env, key, copy.deepcopy(value))
        # Diagnostic history follows the physical branch, including its
        # success latch; a tested alternative must not contaminate the rollout.
        self._native_success_events = self._native_success_events[
            :snapshot.get("native_success_event_count", 0)]
        observed = np.asarray(worker.get_sim_state())
        if not np.allclose(observed, state, atol=1e-8, rtol=0):
            raise RuntimeError("physics state changed during branch restoration")
        return self._strip_obs(to_numpy_tree(self._env._wrap_obs([raw])))


def main() -> None:
    """Serve the private original-task oracle in an owned simulation process."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--suite", choices=sorted(ORIGINAL_SUITES), required=True)
    parser.add_argument("--task", type=int, required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--max-episode-steps", type=int, default=3000)
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--transport", choices=("socket", "http"), default="http")
    parser.add_argument("--parent-watch", action="store_true")
    parser.add_argument("--counterfactual-spec", type=Path)
    parser.add_argument("--native-diagnostic", action="store_true")
    parser.add_argument("--deterministic-reset-v1", action="store_true")
    parser.add_argument("--motion-trace-v1", action="store_true")
    args = parser.parse_args()
    if os.environ.get("LIBERO_TYPE") != "standard":
        parser.error("set LIBERO_TYPE=standard before importing the original oracle")
    if not 0 <= args.task < 10:
        parser.error("original gate task index must be 0..9")
    spec = json.loads(args.counterfactual_spec.read_text()) if args.counterfactual_spec else None
    env = make_v5_env(args.task, args.seed, args.suite, args.max_episode_steps, counterfactual_spec=spec, branch_state=True,
                      deterministic_reset_v1=args.deterministic_reset_v1,
                      motion_trace_v1=args.motion_trace_v1)
    facade = OriginalOracleFacade(
        env,
        native_diagnostic=args.native_diagnostic,
        motion_trace_v1=args.motion_trace_v1,
        meta={
            "suite": args.suite,
            "task": args.task,
            "seed": args.seed,
            "max_episode_steps": args.max_episode_steps,
        },
    )
    facade.serve(
        transport=args.transport,
        host=args.host,
        port=args.port,
        parent_watch=args.parent_watch,
    )


if __name__ == "__main__":
    main()
