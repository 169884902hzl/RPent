# Copyright 2026 Zhilun Hu.
# SPDX-License-Identifier: Apache-2.0
"""Compare measured grasp approaches before contact on five original states."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np

from harness_v5_eval import run_episode
from robots.libero.v5_runtime import V5Executor
from robots.libero.v5_state import fixture_actions


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sam3-endpoint", required=True)
    parser.add_argument("--vla-endpoint", required=True)
    parser.add_argument("--choice-package", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    summaries = []
    # Separate new original environments preserve the same init across paths.
    for seed in range(5):
        for profile in ("diagonal", "clearance"):
            out = args.output / f"object4_init{seed}_{profile}"
            probe = {"seed": seed, "profile": profile, "servo_calls": [],
                     "contact_executed": False, "approach_reached": False}

            class ApproachProbe(V5Executor):
                def __init__(self, *argv, **kwargs):
                    super().__init__(*argv, **kwargs)
                    self._approach_started = False
                    original_servo = self.p.move_to

                    def servo(xyz, **options):
                        initial = self.p._last_obs_eef_pos.copy()
                        result = original_servo(xyz, **options)
                        probe["servo_calls"].append({
                            "initial_eef_xyz": initial.tolist(), "source": "proprioception",
                            "target_xyz": np.asarray(xyz).tolist(), "result": result,
                        })
                        (out / "approach_probe.json").write_text(json.dumps(probe, indent=2) + "\n")
                        return result

                    self.p.move_to = servo

                def move(self, xyz, gripper):
                    if not self._approach_started:
                        self._approach_started = True
                        if profile == "clearance":
                            visible = [e for e in self.scene.entities.values()
                                       if e.visible and not fixture_actions(e.name)
                                       and not e.name.startswith("area ")]
                            height = max([self.p._last_obs_eef_pos[2], xyz[2]]
                                         + [e.upper[2] + .10 for e in visible])
                            lift = self.p._last_obs_eef_pos.copy()
                            lift[2] = height
                            super().move(lift, gripper)
                            super().move([xyz[0], xyz[1], height], gripper)
                    return super().move(xyz, gripper)

                def vla_act(self, *argv, **kwargs):
                    probe["approach_reached"] = True
                    # This component probe never executes contact or produces labels.
                    raise RuntimeError("component_probe_stopped_before_contact")

            import robots.libero.v5_runtime as runtime
            runtime.V5Executor = ApproachProbe
            episode_args = argparse.Namespace(
                suite="libero_object", task=4, seed=seed, libero_type="standard",
                provider="oracle", choice_endpoint=None, choice_package=args.choice_package,
                sam3_endpoint=args.sam3_endpoint, vla_endpoint=args.vla_endpoint,
                done_gated=False, max_decisions=1, max_chunks=80, max_episode_steps=10000,
                smoke_object="bowl", smoke_target="plate", output_dir=out,
            )
            try:
                run_episode(episode_args)
            finally:
                runtime.V5Executor = V5Executor
                (out / "approach_probe.json").write_text(json.dumps(probe, indent=2) + "\n")
            probe["choices_sha256"] = hashlib.sha256((out / "choices.jsonl").read_bytes()).hexdigest()
            summaries.append(probe)
            summary = {
                "purpose": "servo-only development diagnosis; not episode scores or training",
                "task": "original libero_object/4", "init_indices": list(range(5)),
                "contact_executed": False, "source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                "probes": summaries,
            }
            (args.output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
            print(json.dumps(probe), flush=True)


if __name__ == "__main__":
    main()
