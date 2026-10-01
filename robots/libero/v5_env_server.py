# Copyright 2026 Zhilun Hu.
# SPDX-License-Identifier: Apache-2.0
"""v5 rollout server: stop chunks at native success or the external budget."""

from __future__ import annotations

import argparse

import numpy as np

from robots.libero.env_server import LiberoEnvFacade, build_env_cfg


def make_v5_env(task_id: int, seed: int, suite_name: str, max_episode_steps: int, *, counterfactual_spec=None):
    """Use the same fixed state and official success, with one budget owner."""
    from rlinf.envs.libero.libero_env import LiberoEnv
    from rlinf.envs.libero.utils import benchmark

    suite = benchmark.get_benchmark(suite_name)()
    first_id = sum(len(suite.get_task_init_states(t)) for t in range(task_id))
    trials = len(suite.get_task_init_states(task_id))
    effective_suite = suite_name
    if counterfactual_spec is not None:
        if not 10 <= seed < 40:
            raise ValueError("counterfactuals are restricted to training init10-39")
        from robots.libero.v5_counterfactual import register_original_goal_variant
        effective_suite = register_original_goal_variant(suite_name, task_id, counterfactual_spec)
    cfg = build_env_cfg(
        task_suite_name=effective_suite,
        specific_reset_id=first_id + seed % trials,
        seed=seed,
        max_episode_steps=max_episode_steps,
    )
    # Robosuite's internal horizon includes reset-settling steps; the RLinf
    # wrapper already enforces the registered action budget after reset.
    cfg.init_params.ignore_done = True
    return LiberoEnv(
        cfg=cfg, num_envs=1, seed_offset=0, total_num_processes=1, worker_info=None
    )


class V5EnvFacade(LiberoEnvFacade):
    """Do not execute trailing VLA actions after term/trunc within a chunk."""

    def chunk_step(self, actions, *, return_all_frames: bool = False):
        observations, rewards, terminations, truncations, infos = [], [], [], [], []
        for action in np.asarray(actions):
            observation, reward, term, trunc, info = self.step(action)
            observations.append(observation)
            rewards.append(reward)
            terminations.append(term)
            truncations.append(trunc)
            infos.append(info)
            if np.asarray(term).any() or np.asarray(trunc).any():
                break
        if not observations:
            raise ValueError("empty VLA action chunk")
        return (
            observations if return_all_frames else observations[-1],
            np.stack(rewards),
            np.stack(terminations),
            np.stack(truncations),
            infos,
        )


def main() -> None:
    """Serve an owned v5 simulator without introducing oracle RPC methods."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--suite", required=True)
    parser.add_argument("--task", type=int, required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--max-episode-steps", type=int, default=3000)
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--parent-watch", action="store_true")
    args = parser.parse_args()
    env = make_v5_env(args.task, args.seed, args.suite, args.max_episode_steps)
    V5EnvFacade(
        env,
        meta={
            "suite": args.suite,
            "task": args.task,
            "seed": args.seed,
            "max_episode_steps": args.max_episode_steps,
        },
    ).serve(
        transport="http",
        host=args.host,
        port=args.port,
        parent_watch=args.parent_watch,
    )


if __name__ == "__main__":
    main()
