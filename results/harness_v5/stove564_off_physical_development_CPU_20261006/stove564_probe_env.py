"""Original Goal7 fixed-budget server with private post-chunk scoring only."""

import argparse
import os
from pathlib import Path
import time

from robots.libero.v5_stove_probe_env import StoveProbeFacade
from scripts.probe_v5_skill501_original import diagnostic_json


class ScoredStoveProbeFacade(StoveProbeFacade):
    """Write labels outside the unchanged public chunk return contract."""

    def __init__(self, *args, meta, label_path, cell, **kwargs):
        path = Path(label_path)
        if not path.is_absolute() or meta["seed"] not in range(5):
            raise ValueError("off20 requires an absolute ledger and original init0-4")
        path.parent.mkdir(parents=True, exist_ok=True)
        self._label_path = path
        self._label_stream = path.open("x")
        self._label_cell = cell
        super().__init__(*args, meta=meta, **kwargs)

    def _write_private_score(self, scope, timing):
        """Read only after controls, never return labels to the controller."""
        row = {"cell": self._label_cell, "phase": scope["phase"],
               "chunk_index": scope["chunks_requested"], "timing": timing,
               "actual_controls": scope["executed_controls"],
               "controller_access": False, "affects_actions_or_stop": False,
               "scoring_wall_s": None}
        started = time.perf_counter()
        try:
            truth = {mode: self.skill_truth({"kind": "articulate", "mode": mode,
                     "object_symbol": "flat_stove_1"}) for mode in ("turn_on", "turn_off")}
            row.update(requested_predicates=truth, joint_names=truth["turn_off"]["joint_names"],
                       joint_qpos=truth["turn_off"]["joint_qpos"],
                       turn_on_satisfied=truth["turn_on"]["satisfied"],
                       turn_off_satisfied=truth["turn_off"]["satisfied"],
                       sim_time=truth["turn_off"]["sim_time"], status="scored")
        except Exception as error:
            row.update(status="private_scoring_error", error=repr(error))
            # A scoring service fault is retained and makes the completed cell
            # invalid in the driver. It must not change the contact schedule.
        finally:
            row["scoring_wall_s"] = time.perf_counter() - started
            self._label_stream.write(diagnostic_json(row) + "\n")
            self._label_stream.flush()

    def stove_chunk_start(self, phase, max_chunks):
        result = super().stove_chunk_start(phase, max_chunks)
        self._write_private_score(dict(self._stove_chunk_scope), "before_phase")
        return result

    def chunk_step(self, actions, *, return_all_frames=False):
        result = super().chunk_step(actions, return_all_frames=return_all_frames)
        if self._stove_chunk_scope is not None:
            self._write_private_score(dict(self._stove_chunk_scope), "after_executed_chunk")
        return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--serve", action="store_true", required=True)
    parser.add_argument("--suite", choices=("libero_goal",), required=True)
    parser.add_argument("--task", type=int, choices=(7,), required=True)
    parser.add_argument("--seed", type=int, choices=range(5), required=True)
    parser.add_argument("--max-episode-steps", type=int, choices=(10000,), required=True)
    parser.add_argument("--port", type=int, required=True)
    args = parser.parse_args()
    if os.environ.get("LIBERO_TYPE") != "standard":
        parser.error("LIBERO_TYPE=standard is required")
    label_path, cell = os.environ.get("STOVE564_LABEL_LEDGER"), os.environ.get("STOVE564_CELL")
    if not label_path or not cell:
        parser.error("explicit STOVE564_LABEL_LEDGER and STOVE564_CELL are required")
    from scripts.probe_v5_skill501_original import make_probe_env

    env = make_probe_env(args.task, args.seed, args.suite, args.max_episode_steps)
    facade = ScoredStoveProbeFacade(env, meta={"suite": args.suite, "task": args.task,
        "seed": args.seed, "max_episode_steps": args.max_episode_steps},
        label_path=label_path, cell=cell, motion_trace_v1=True)
    try:
        facade.serve(transport="http", host="127.0.0.1", port=args.port, parent_watch=True)
    finally:
        facade._label_stream.close()


if __name__ == "__main__":
    main()
