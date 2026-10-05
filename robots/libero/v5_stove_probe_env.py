# Copyright 2026 Zhilun Hu.
# SPDX-License-Identifier: Apache-2.0
"""Independent original stove metrology: finish a fixed contact action chunk.

The original Goal7 native goal is turnon. Its raw native termination cannot
truncate a separately registered turnoff contact test. This owned server only
permits on/off diagnostic scopes, each bounded to 160 five-action chunks; it
keeps every raw native-success flag and still stops at external truncation.
The normal V5EnvFacade and all evaluation termination rules are unchanged.
"""

import argparse
import os

import numpy as np

from robots.libero.v5_oracle_server import OriginalOracleFacade


class StoveProbeFacade(OriginalOracleFacade):
    def __init__(self, *args, meta, **kwargs):
        if (meta["suite"] != "libero_goal" or meta["task"] != 7
                or meta["seed"] not in range(10) or meta["max_episode_steps"] != 10000):
            raise ValueError("owned full-chunk metrology is restricted to registered original Goal7 init0-9")
        self._stove_chunk_scope = None
        self._next_stove_phase = "on"
        super().__init__(*args, meta=meta, **kwargs)

    def _register_rpc(self):
        super()._register_rpc()
        self._rpc.update({
            "oracle.skill501_truth": self.skill_truth,
            "diagnostic.stove_chunk_start": self.stove_chunk_start,
            "diagnostic.stove_chunk_end": self.stove_chunk_end,
        })
        self._readonly_methods.add("oracle.skill501_truth")

    def skill_truth(self, spec):
        from rpent.utils.serialization import to_numpy_tree
        return to_numpy_tree(self._env.env.workers[0].env_call(
            "v5_skill501_truth", args=[spec], target="self"))

    def stove_chunk_start(self, phase, max_chunks):
        if self._stove_chunk_scope is not None or phase != self._next_stove_phase or max_chunks != 160:
            raise ValueError("fixed diagnostic on/off scope order or chunk budget changed")
        self._stove_chunk_scope = {
            "phase": phase, "max_chunks": max_chunks, "actions_per_chunk": 5,
            "max_controls": max_chunks * 5, "chunks_requested": 0,
            "requested_controls": 0, "executed_controls": 0,
            "raw_native_success_controls": 0, "external_truncation": False,
            "native_success_stops_chunk": False,
            "private_joint_or_predicate_used_for_control": False,
        }
        return dict(self._stove_chunk_scope)

    def stove_chunk_end(self):
        if self._stove_chunk_scope is None:
            raise ValueError("no registered diagnostic scope to end")
        finished = dict(self._stove_chunk_scope)
        self._next_stove_phase = "off" if finished["phase"] == "on" else None
        self._stove_chunk_scope = None
        return finished

    def chunk_step(self, actions, *, return_all_frames=False):
        scope = self._stove_chunk_scope
        if scope is None:
            return super().chunk_step(actions, return_all_frames=return_all_frames)
        actions = np.asarray(actions)
        if len(actions) != scope["actions_per_chunk"] or scope["chunks_requested"] >= scope["max_chunks"]:
            raise ValueError("registered finite diagnostic chunk length/budget exceeded")
        if scope["external_truncation"]:
            raise RuntimeError("diagnostic chunk requested after external truncation")
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
    parser.add_argument("--suite", choices=("libero_goal",), required=True)
    parser.add_argument("--task", type=int, choices=(7,), required=True)
    parser.add_argument("--seed", type=int, choices=range(10), required=True)
    parser.add_argument("--max-episode-steps", type=int, choices=(10000,), required=True)
    parser.add_argument("--port", type=int, required=True)
    args = parser.parse_args()
    if os.environ.get("LIBERO_TYPE") != "standard":
        parser.error("LIBERO_TYPE=standard required for original-only full-chunk metrology")
    from scripts.probe_v5_skill501_original import make_probe_env
    env = make_probe_env(args.task, args.seed, args.suite, args.max_episode_steps)
    StoveProbeFacade(env, meta={"suite": args.suite, "task": args.task,
        "seed": args.seed, "max_episode_steps": args.max_episode_steps}, motion_trace_v1=True).serve(
        transport="http", host="127.0.0.1", port=args.port, parent_watch=True)


if __name__ == "__main__":
    main()
