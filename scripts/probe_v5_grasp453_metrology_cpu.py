"""Check private grasp geometry and the unheld negative control on CPU."""

import argparse
import hashlib
import json
from pathlib import Path
import time


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--measure-empty-aperture", action="store_true")
    args = parser.parse_args()
    plan = json.loads(args.manifest.read_text())
    assert plan["truth_protocol"]["runtime_truth_allowed"] is False
    import numpy as np
    from libero.libero import get_libero_path
    from libero.libero.envs.env_wrapper import ControlEnv
    from rlinf.envs.libero.utils import benchmark
    from robots.libero.v5_branch_state import attach_branch_state
    from robots.libero.v5_reset_seed import attach_reset_seed
    from robots.libero.v5_runtime import category

    cases = {}
    for case in plan["cases"]:
        cases.setdefault(case["group"], case)
    rows = []
    args.output.mkdir(parents=True, exist_ok=False)
    for group, case in cases.items():
        ep = case["episode"]
        if ep["suite"] not in ("libero_spatial", "libero_object", "libero_goal", "libero_10"):
            raise ValueError("metrology controls are original-task only")
        started = time.perf_counter()
        suite = benchmark.get_benchmark(ep["suite"])()
        task = suite.get_task(ep["task"])
        bddl = Path(get_libero_path("bddl_files")) / task.problem_folder / task.bddl_file
        # OffScreenRenderEnv unconditionally enables a GL renderer, even
        # when camera observations are disabled. Metrology needs physics
        # only; use its ControlEnv base and the exact same private methods.
        env = ControlEnv(bddl_file_name=str(bddl), use_camera_obs=False,
                         has_renderer=False, has_offscreen_renderer=False,
                         horizon=10015, ignore_done=True)
        attach_reset_seed(env)
        attach_branch_state(env)
        try:
            env.seed(ep["seed"])
            env.reset()
            env.set_init_state(suite.get_task_init_states(ep["task"])[ep["seed"]])
            action = np.zeros(7)
            action[-1] = -1
            for _ in range(15):
                env.step(action)
            contacts = env.v5_grasp_contacts()
            names = [name for name in contacts["objects"] if category(name) == case["category"]]
            if len(names) != 1:
                raise ValueError(f"negative control has no unique object: {group}: {names}")
            name = names[0]
            reference = env.v5_grasp_reference(name)
            hold = env.v5_measure_grasp_hold(name, reference,
                                            plan["truth_protocol"]["hold_duration_s"])
            row = {"group": group, "episode": ep, "target": name,
                   "reference": reference, "hold": hold, "wall_s": time.perf_counter() - started}
            if args.measure_empty_aperture:
                # Public robot joint sensors use exactly this float32 width
                # conversion in LiberoPrimitives.set_obs. No private target
                # position or contact controls the closure actions.
                widths = []
                action = np.zeros(7)
                action[-1] = 1
                for _ in range(30):
                    obs, _, _, _ = env.step(action)
                    qpos = np.asarray(obs["robot0_gripper_qpos"], dtype=np.float32)
                    widths.append(float(abs(qpos[0]) + abs(qpos[1])))
                row["empty_aperture"] = {
                    "source": "robot_joint_proprioception", "additional_closure_steps": 30,
                    "width_samples_m": widths, "settled_last10_max_m": max(widths[-10:]),
                    "settled_last10_min_m": min(widths[-10:]),
                    "success_rule_unchanged": True}
            rows.append(row)
            (args.output / (group + ".json")).write_text(json.dumps(row, indent=2) + "\n")
            if hold["truth"]["success"] or hold["truth"]["duration_s"] < .5 - 1e-8:
                raise RuntimeError("unheld control or physical hold clock failed")
            print(json.dumps({"group": group, "negative_control_passed": True,
                              "samples": hold["truth"]["samples"],
                              "duration_s": hold["truth"]["duration_s"]}), flush=True)
        finally:
            env.close()
    report = {"scope": "CPU reset/unheld metrology controls; no policy grasp or task score",
              "manifest_sha256": sha(args.manifest), "script_sha256": sha(Path(__file__)),
              "control_env_physics_only": True, "worker_rpc_checked": False,
              "classes": len(rows), "all_unheld_negative_controls_passed": len(rows) == len(cases),
              "new_training_rows": 0, "rows": rows}
    if args.measure_empty_aperture:
        report["empty_aperture_settled_max_m"] = max(
            row["empty_aperture"]["settled_last10_max_m"] for row in rows)
    path = args.output / "report.json"
    path.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"report": str(path), "sha256": sha(path)}))


if __name__ == "__main__":
    main()
