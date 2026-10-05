"""Paired original-task first grasps; private contacts never enter requests."""

import argparse
from collections import Counter
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import sys
import time

import numpy as np


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def contact_binding(obj, reference, category):
    """Bind diagnostic labels after selection; abstain on ambiguous matches."""
    distances = sorted((float(np.linalg.norm(np.asarray(body["xyz"]) - obj.xyz)), name)
                       for name, body in reference["objects"].items()
                       if category(name) == obj.name)
    if not distances or distances[0][0] > .10:
        return None
    if len(distances) > 1 and distances[1][0] - distances[0][0] < .02:
        return None
    return distances[0][1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--shard-index", type=int, required=True)
    parser.add_argument("--shards", type=int, default=2)
    args = parser.parse_args()
    plan = json.loads(args.manifest.read_text())
    from harness_v5_eval import run_episode
    import robots.libero.v5_runtime as runtime
    from robots.libero.v5_runtime import V5Executor, category
    from rpent.utils.daemon import ProcessDaemon, pick_free_port
    from rpent.utils.rpc import wait_for_ready
    from rpent.utils.rpc.http_rpc import HttpRpcClient

    args.output.mkdir(parents=True, exist_ok=False)
    endpoints, daemons, rows = {}, [], []
    try:
        for name, module, extra in (
            ("sam3", "robots.libero.v5_sam3_server", []),
            ("vla", "rpent.robots.components.pi05_vla_server", ["--embodiment", "libero"]),
        ):
            port = pick_free_port()
            daemon = ProcessDaemon(name="grasp449_" + name,
                cmd=[sys.executable, "-m", module, *extra, "--transport", "http",
                     "--host", "127.0.0.1", "--port", str(port), "--parent-watch"],
                log_path=str(args.output / ("shared_" + name + ".log")))
            daemon.start()
            daemons.append(daemon)
            endpoints[name] = f"http://127.0.0.1:{port}"
        for name, daemon in zip(("sam3", "vla"), daemons):
            wait_for_ready(HttpRpcClient(endpoints[name]), daemon=daemon, timeout_s=300)
        base_file = Path(plan["base_config"]["path"])
        if sha(base_file) != plan["base_config"]["sha256"]:
            raise ValueError("registered original config changed")
        base = json.loads(base_file.read_text())
        assert base["libero_type"] == "standard"
        with (args.output / "episodes.jsonl").open("x") as ledger:
            for case in plan["cases"][args.shard_index::args.shards]:
                evidence = {"case": case, "contact_samples": [], "verification_samples": []}
                condition = plan["conditions"][case["condition"]]

                class ProbeExecutor(V5Executor):
                    def __init__(self, *argv, **kwargs):
                        super().__init__(*argv, **kwargs)
                        self._diagnostic_symbol = None
                        self._initial_xyz = self.p._last_obs_eef_pos.copy()
                        self._initial_quat = self.p.env.raw_obs()["robot0_eef_quat"]
                        chunk = self.p._vlm_chunk

                        def sampled_chunk(*argv, **kwargs):
                            result = chunk(*argv, **kwargs)
                            evidence["contact_samples"].append(self._contacts())
                            return result

                        self.p._vlm_chunk = sampled_chunk

                    def _contacts(self):
                        ref = self.p.env._client.call("oracle.grasp_contacts", timeout_s=30)
                        name = self._diagnostic_symbol
                        body = ref["objects"].get(name) if name else None
                        initial = (evidence.get("initial_private_reference") or {}).get("objects", {}).get(name)
                        rise = body["xyz"][2] - initial["xyz"][2] if body and initial else None
                        return {**ref, "selected_symbol": name,
                                "target_dual_contact": body["dual_finger_contact"] if body else None,
                                "private_z_rise_m": rise,
                                "contact_and_lift_3cm": bool(body["dual_finger_contact"] and rise >= .03)
                                if body and rise is not None else None}

                    def _execute(self, action, receipt, card):
                        obj = self.scene.entities[action.object]
                        ref = self._contacts()
                        self._diagnostic_symbol = contact_binding(obj, ref, category)
                        evidence["initial_private_reference"] = ref
                        evidence["selected_public_entity"] = obj.id
                        evidence["initial_eef_xyz"] = self._initial_xyz.tolist()
                        evidence["initial_eef_quat"] = np.asarray(self._initial_quat).tolist()
                        if case["condition"] == "current_restage":
                            action = replace(action, tool="regrasp_restage", mode=None)
                            receipt.update(tool=action.tool)
                            receipt.pop("mode", None)
                        return super()._execute(action, receipt, card)

                    def stage_grasp(self, obj, pose, receipt):
                        profile = condition["profile"]
                        if profile == "start_full":
                            # A first-grasp probe starts at the exact reset pose.
                            # No simulator restore or ground-truth pose is used.
                            residual = float(np.linalg.norm(self.p._last_obs_eef_pos - self._initial_xyz))
                            if residual > .012:
                                raise RuntimeError("first-grasp probe left its registered initial pose")
                            receipt["diagnostic_approach"] = "reset_pose_proprioception"
                            return True
                        if profile == "high_short":
                            pose = [(obj.lower[i] + obj.upper[i]) / 2 for i in (0, 1)]
                            pose.append(max(float(self._initial_xyz[2]), obj.upper[2] + .20))
                            receipt["diagnostic_approach"] = "measured_overhead_20cm_or_reset_height"
                        return super().stage_grasp(obj, pose, receipt)

                    def vla_act(self, prompt, max_chunks, stop, obj=None, **kwargs):
                        if condition["profile"] == "start_full":
                            prompt = self.instruction if case["original_goal_source"] else plan["frypan_full_prompt"]
                            evidence["full_prompt_origin"] = "original_task" if case["original_goal_source"] else "registered_original_scene_grasp_probe"
                        elif condition["profile"] == "high_short":
                            prompt = f"pick up the {obj.name}"
                        evidence["contact_prompt"] = prompt
                        evidence["contact_max_chunks"] = max_chunks
                        return super().vla_act(prompt, max_chunks, stop, obj, **kwargs)

                    def verify_grasp_measurement(self, before):
                        verified = super().verify_grasp_measurement(before)
                        evidence["verification_samples"].append({
                            "measured_verified": verified, "private_contact": self._contacts()})
                        return verified

                    def execute(self, *argv, **kwargs):
                        receipt = super().execute(*argv, **kwargs)
                        evidence["final_private_contact"] = self._contacts()
                        return receipt

                cfg = {**base, **case["episode"], **condition["overrides"],
                       "provider": "oracle", "libero_type": "standard", "max_decisions": 1,
                       "max_chunks": condition["max_chunks"], "max_episode_steps": 10000,
                       "grasp_probe_category": case["category"], "grasp_probe_mode": condition["mode"],
                       "deterministic_reset_v1": True, "motion_trace_v1": True,
                       "done_gated": False, "persist_attempts_v1": True,
                       "sam3_endpoint": endpoints["sam3"], "vla_endpoint": endpoints["vla"],
                       "choice_package": Path(plan["choice_package"]),
                       "output_dir": args.output / case["name"]}
                cfg.pop("init_state_sha256", None)
                started = time.perf_counter()
                runtime.V5Executor = ProbeExecutor
                try:
                    result = run_episode(argparse.Namespace(**cfg))
                except Exception as error:
                    path = cfg["output_dir"] / "result.json"
                    result = json.loads(path.read_text()) if path.exists() else {
                        "status": "startup_error", "error": repr(error)}
                    evidence["raised_error"] = repr(error)
                finally:
                    runtime.V5Executor = V5Executor
                trace = cfg["output_dir"] / "choices.jsonl"
                decisions = list(map(json.loads, trace.read_text().splitlines())) if trace.exists() else []
                receipt = decisions[0]["receipt"] if decisions else {}
                evidence.update(result=result, output_dir=str(cfg["output_dir"]),
                    wall_s=time.perf_counter() - started, first_receipt=receipt,
                    grasp_attempted=receipt.get("tool") in ("grasp", "regrasp_restage"),
                    visual_verified=receipt.get("grasp_verified") is True,
                    private_contact_at_final=(evidence.get("final_private_contact") or {}).get("target_dual_contact"),
                    private_contact_and_lift=(evidence.get("final_private_contact") or {}).get("contact_and_lift_3cm"),
                    choices_sha256=sha(trace) if trace.exists() else None,
                    chunks=receipt.get("chunks", 0),
                    executed_vla_actions=sum(m.get("executed_action_count", 0)
                                             for row in decisions for m in row.get("motion_evidence", [])))
                (cfg["output_dir"] / "private_grasp_diagnostic.json").write_text(
                    json.dumps(evidence, indent=2) + "\n")
                ledger.write(json.dumps(evidence) + "\n")
                ledger.flush()
                rows.append(evidence)
                print(json.dumps({"case": case["name"], "grasp_attempted": evidence["grasp_attempted"],
                                  "visual_verified": evidence["visual_verified"],
                                  "private_contact": evidence["private_contact_at_final"],
                                  "chunks": evidence["chunks"], "error": evidence.get("raised_error")}), flush=True)
    finally:
        for daemon in reversed(daemons):
            daemon.stop()
        (args.output / "summary.json").write_text(json.dumps({
            "manifest_sha256": sha(args.manifest), "script_sha256": sha(__file__),
            "completed": len(rows), "planned": len(plan["cases"][args.shard_index::args.shards]),
            "new_training_rows": 0,
            "scope": "paired original-task first grasps; contacts are private diagnostic evidence",
            "termination_counts": dict(Counter(r["result"].get("termination_category") for r in rows)),
        }, indent=2) + "\n")
    if any(r.get("raised_error") or r["first_receipt"].get("verification") == "execution_error" for r in rows):
        raise RuntimeError("preserved diagnostic failures require repair before the full cohort")


if __name__ == "__main__":
    main()
