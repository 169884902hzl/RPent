"""Exercise repeated view recovery on an original scene, without training labels."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

from robots.libero.v5_oracle_policy import OriginalOraclePolicy
from robots.libero.v5_runtime import V5Executor


def main() -> None:
    """Use the existing episode runner with an explicitly scripted retreat probe."""
    import v5_batch_eval

    output = Path(sys.argv[sys.argv.index("--output-dir") + 1])
    movements = []
    original_retreat = V5Executor.retreat

    def choose(self, entities, choices, *args, **kwargs):
        self.last_binding = {"scope": "original_repeated_retreat_diagnostic"}
        return next(c for c in choices if c.tool == "retreat")

    def retreat(self):
        # Exercise an actual return from a nearby contact-height waypoint;
        # calling retreat repeatedly while already at the anchor is a no-op.
        staged = self.view_retreat_pose.copy()
        staged[0] += .035 if len(movements) % 2 == 0 else -.035
        staged[2] -= .03
        self.move(staged, 0)
        before = self.p._last_obs_eef_pos.copy()
        opening = float(self.p._last_obs_gripper)
        original_retreat(self)
        movements.append({
            "target": self.view_retreat_pose.tolist(),
            "before": before.tolist(),
            "after": self.p._last_obs_eef_pos.tolist(),
            "gripper_before": opening,
            "gripper_after": float(self.p._last_obs_gripper),
            "return_distance_m": float(np.linalg.norm(self.p._last_obs_eef_pos - before)),
            "motion": self.motion_evidence[-1],
        })

    OriginalOraclePolicy.choose = choose
    V5Executor.retreat = retreat
    v5_batch_eval.main()
    ledger = [json.loads(line) for line in (output / "episodes.jsonl").read_text().splitlines()]
    traces = [json.loads(line) for line in
              (Path(ledger[0]["output_dir"]) / "choices.jsonl").read_text().splitlines()]
    errors = [row["receipt"]["error"] for row in traces if row["receipt"].get("error")]
    passed = (len(ledger) == 1 and len(movements) == 4 and not errors
              and all(np.linalg.norm(np.subtract(m["after"], m["target"])) <= .02 for m in movements)
              and all(m["target"] == movements[0]["target"] for m in movements)
              and all(m["return_distance_m"] >= .025 for m in movements)
              and all(abs(m["gripper_after"] - m["gripper_before"]) <= .01 for m in movements))
    report = {"purpose": "original-only engineering probe; not a model score or training data",
              "passed": passed, "movements": movements, "errors": errors,
              "expected_decisions": 4, "result": ledger[0]["result"]}
    (output / "retreat_audit.json").write_text(json.dumps(report, indent=2) + "\n")
    if not passed:
        raise RuntimeError("repeated view retreat did not preserve the fixed measured target")


if __name__ == "__main__":
    main()
