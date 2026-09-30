"""Original-task-only oracle RPC, kept separate from planner observations."""

from __future__ import annotations

import argparse
import copy
import hashlib
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

    def __init__(self, env, *, meta: dict) -> None:
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
        super().__init__(env, meta=meta)

    def _register_rpc(self) -> None:
        super()._register_rpc()
        self._rpc.update(
            {
                "oracle.status": self.goal_status,
                "oracle.snapshot": self.snapshot,
                "oracle.restore": self.restore,
            }
        )
        self._readonly_methods.update(("oracle.status", "oracle.snapshot"))

    def goal_status(self) -> dict:
        """Return independent predicate results to the oracle, never the planner."""
        worker = self._env.env.workers[0]
        checks = [
            bool(worker.env_call("_eval_predicate", args=[g])) for g in self._goals
        ]
        return {
            "goals": self._goals,
            "satisfied": checks,
            "done": bool(checks and all(checks)),
            "bddl_sha256": self._bddl_sha,
        }

    def snapshot(self) -> dict:
        """Capture physics and rollout counters without integrating another step."""
        return to_numpy_tree(
            {
                "sim_state": self._env.env.workers[0].get_sim_state(),
                "counters": {
                    key: copy.deepcopy(getattr(self._env, key))
                    for key in WRAPPER_FIELDS
                    if hasattr(self._env, key)
                },
                "task": self._meta,
                "bddl_sha256": self._bddl_sha,
            }
        )

    def restore(self, snapshot: dict) -> dict:
        """Restore a branch point and rebuild observation without a reset rollout."""
        if snapshot["task"] != self._meta or snapshot["bddl_sha256"] != self._bddl_sha:
            raise ValueError("snapshot belongs to another original task")
        worker = self._env.env.workers[0]
        state = np.asarray(snapshot["sim_state"])
        raw = worker.set_init_state(state)
        self._env.current_raw_obs = [raw]
        for key, value in snapshot["counters"].items():
            if key not in WRAPPER_FIELDS:
                raise ValueError(f"unsupported snapshot counter: {key}")
            setattr(self._env, key, copy.deepcopy(value))
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
    args = parser.parse_args()
    if os.environ.get("LIBERO_TYPE") != "standard":
        parser.error("set LIBERO_TYPE=standard before importing the original oracle")
    if not 0 <= args.task < 10:
        parser.error("original gate task index must be 0..9")
    env = make_v5_env(args.task, args.seed, args.suite, args.max_episode_steps)
    facade = OriginalOracleFacade(
        env,
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
