"""Engineering probe of the private original-task branch-restore protocol."""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path

import numpy as np

from robots.libero.env_server import make_env
from robots.libero.v5_oracle_server import OriginalOracleFacade


def main() -> None:
    """Verify snapshot restoration and predicate stability on one original scene."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    start = time.perf_counter()
    env = make_env(0, 0, "libero_spatial", 3000)
    facade = OriginalOracleFacade(
        env,
        meta={
            "suite": "libero_spatial",
            "task": 0,
            "seed": 0,
            "max_episode_steps": 3000,
        },
    )
    try:
        initial_obs, _ = facade.reset()
        snapshot = facade.snapshot()
        # Reset returns the last step's cached sensors; restoration forces a
        # fresh observation. Compare two fresh observations of the same state.
        obs = facade.restore(snapshot)
        cached_delta = float(
            np.max(
                np.abs(np.asarray(initial_obs["states"]) - np.asarray(obs["states"]))
            )
        )
        print(
            json.dumps(
                {
                    "initial_cached_vs_fresh_max_delta": cached_delta,
                    "initial_cached": np.asarray(initial_obs["states"]).tolist(),
                    "fresh_baseline": np.asarray(obs["states"]).tolist(),
                }
            ),
            flush=True,
        )
        status = facade.goal_status()
        action = np.zeros(7, dtype=np.float32)
        action[0], action[-1] = 0.05, -1
        facade.step(action)
        restored = facade.restore(snapshot)
        after = facade.goal_status()
        if status != after:
            raise AssertionError("goal predicates changed after snapshot restoration")
        if not np.allclose(
            np.asarray(obs["states"]), np.asarray(restored["states"]), atol=1e-6, rtol=0
        ):
            raise AssertionError("proprioception changed after restoration")
        record = {
            "mode": "private-oracle-engineering-probe",
            "passed": True,
            "goal_status": status,
            "restored_predicates_identical": True,
            "restored_proprioception_identical": True,
            "initial_cached_vs_fresh_max_delta": cached_delta,
            "baseline_freshened_without_physics_step": True,
            "snapshot_sha256": hashlib.sha256(
                np.asarray(snapshot["sim_state"]).tobytes()
            ).hexdigest(),
            "wall_s": time.perf_counter() - start,
        }
        args.output.write_text(json.dumps(record, indent=2))
        print(json.dumps(record), flush=True)
    finally:
        facade.close()


if __name__ == "__main__":
    main()
