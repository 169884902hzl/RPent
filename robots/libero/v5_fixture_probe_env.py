# Copyright 2026 Zhilun Hu.
# SPDX-License-Identifier: Apache-2.0
"""Complete fixed original fixture diagnostic chunks, retaining raw native done.

This independent server covers only the registered Goal0 and Long3/9 init0-2
probe. It changes no shared runtime, evaluator, controller or public receipt.
Private predicates remain read-only labels. Outside its finite action scope,
the normal native-success stop rule applies.
"""

import argparse
import os

import numpy as np

from robots.libero.v5_oracle_server import OriginalOracleFacade


class FixtureProbeFacade(OriginalOracleFacade):
    def __init__(self, *args, meta, **kwargs):
        if ((meta["suite"], meta["task"]) not in {
                ("libero_goal", 0), ("libero_10", 3), ("libero_10", 9)}
                or meta["seed"] not in range(3) or meta["max_episode_steps"] != 10000):
            raise ValueError("fixture probe is restricted to registered original Goal0/Long3/9 init0-2")
        self._fixture_chunk_scope = None
        self._fixture_phases = []
        super().__init__(*args, meta=meta, **kwargs)

    def _register_rpc(self):
        super()._register_rpc()
        self._rpc.update({
            "oracle.skill501_truth": self.skill_truth,
            "diagnostic.fixture_chunk_start": self.fixture_chunk_start,
            "diagnostic.fixture_chunk_end": self.fixture_chunk_end,
        })
        self._readonly_methods.add("oracle.skill501_truth")

    def skill_truth(self, spec):
        from rpent.utils.serialization import to_numpy_tree
        return to_numpy_tree(self._env.env.workers[0].env_call(
            "v5_skill501_truth", args=[spec], target="self"))

    def fixture_chunk_start(self, phase, max_chunks):
        valid = (phase == "first_attempt" and self._fixture_phases in ([], ["setup"])) or (
            phase == "setup" and not self._fixture_phases)
        if self._fixture_chunk_scope is not None or not valid or max_chunks != 160:
            raise ValueError("registered finite fixture setup/first scope order or budget changed")
        self._fixture_chunk_scope = {
            "phase": phase, "max_chunks": max_chunks, "actions_per_chunk": 5,
            "max_controls": max_chunks * 5, "chunks_requested": 0,
            "requested_controls": 0, "executed_controls": 0,
            "raw_native_success_controls": 0, "external_truncation": False,
            "native_success_stops_chunk": False,
            "private_joint_or_predicate_used_for_control": False,
        }
        return dict(self._fixture_chunk_scope)

    def fixture_chunk_end(self):
        if self._fixture_chunk_scope is None:
            raise ValueError("no finite fixture diagnostic scope to end")
        finished = dict(self._fixture_chunk_scope)
        self._fixture_phases.append(finished["phase"])
        self._fixture_chunk_scope = None
        return finished

    def chunk_step(self, actions, *, return_all_frames=False):
        scope = self._fixture_chunk_scope
        if scope is None:
            return super().chunk_step(actions, return_all_frames=return_all_frames)
        actions = np.asarray(actions)
        if len(actions) != 5 or scope["chunks_requested"] >= scope["max_chunks"]:
            raise ValueError("registered finite diagnostic chunk length/budget exceeded")
        if scope["external_truncation"]:
            raise RuntimeError("fixture chunk requested after external truncation")
        scope["chunks_requested"] += 1
        scope["requested_controls"] += len(actions)
        observations, rewards, terminations, truncations, infos = [], [], [], [], []
        for action in actions:
            observation, reward, term, trunc, info = self.step(action)
            observations.append(observation)
            rewards.append(reward)
            terminations.append(term)
            truncations.append(trunc)
            infos.append(info)
            scope["executed_controls"] += 1
            scope["raw_native_success_controls"] += bool(np.asarray(term).any())
            if np.asarray(trunc).any():
                scope["external_truncation"] = True
                break
        return (observations if return_all_frames else observations[-1],
                np.stack(rewards), np.stack(terminations), np.stack(truncations), infos)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--serve", action="store_true", required=True)
    parser.add_argument("--suite", choices=("libero_goal", "libero_10"), required=True)
    parser.add_argument("--task", type=int, required=True)
    parser.add_argument("--seed", type=int, choices=range(3), required=True)
    parser.add_argument("--max-episode-steps", type=int, choices=(10000,), required=True)
    parser.add_argument("--port", type=int, required=True)
    args = parser.parse_args()
    if os.environ.get("LIBERO_TYPE") != "standard":
        parser.error("LIBERO_TYPE=standard required for original fixture diagnostics")
    if (args.suite, args.task) not in {("libero_goal", 0), ("libero_10", 3), ("libero_10", 9)}:
        parser.error("only registered original Goal0/Long3/9")
    from scripts.probe_v5_skill501_original import make_probe_env
    env = make_probe_env(args.task, args.seed, args.suite, args.max_episode_steps)
    FixtureProbeFacade(env, meta={"suite": args.suite, "task": args.task,
        "seed": args.seed, "max_episode_steps": args.max_episode_steps}, motion_trace_v1=True).serve(
        transport="http", host="127.0.0.1", port=args.port, parent_watch=True)


if __name__ == "__main__":
    main()
