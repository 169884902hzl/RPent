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


def rpent_pick_then_measure(executor, prompt, max_chunks, obj):
    """Use RPent's public descent/ascent stop, then the visual verifier.

    This diagnostic alternative never uses private contacts to stop the
    policy. The simulator's sustained-hold result is collected afterward.
    """
    primitive = executor.p.pi0_pick(prompt, max_chunks=max_chunks)
    executor._refresh([obj.name])
    verified = executor.verify_grasp_measurement(obj)
    return {"executed": primitive["chunks_used"] > 0,
            "chunks": primitive["chunks_used"], "stop_condition": "grasp_verified",
            "stop": "grasp_verified" if verified else "grasp_not_verified",
            "grasp_verified": verified}, primitive


def rpent_pick_then_stable_measure(executor, prompt, max_chunks, obj):
    """Experimental trial lift and two fresh visual frames, no private truth.

    Ten public hold steps correspond to 0.5s under LIBERO's 20Hz controller.
    A missing main-view measurement gets one wrist-view measurement without
    moving the camera. This stays confined to the registered component probe.
    """
    from robots.libero.v5_state import entity_record

    primitive = executor.p.pi0_pick(prompt, max_chunks=max_chunks)
    measurements = {"version": "trial_lift_lower_two_frames/1", "frames": [],
                    "hold_steps": 10, "registered_control_frequency_hz": 20,
                    "trial_lift_m": .05, "runtime_inputs": "RGB-D measurements and gripper proprioception"}
    receipt = {"executed": primitive["chunks_used"] > 0, "chunks": primitive["chunks_used"],
               "stop_condition": "grasp_verified", "stop": "grasp_not_verified", "grasp_verified": False}
    if executor.p.env.terminated or executor.p.env.truncated:
        measurements["unverified_reason"] = "native_termination_before_trial_lift"
        return receipt, primitive, measurements
    if not executor.grasp_minimum_opening <= executor.p._last_obs_gripper <= .07:
        measurements["unverified_reason"] = "aperture_outside_nonempty_range"
        return receipt, primitive, measurements
    lift = executor.p._last_obs_eef_pos.copy()
    lift[2] += .05
    motion = executor.move(lift, 1, tolerance_m=.02, recoverable=True)
    measurements["trial_lift_motion"] = motion
    if not motion.get("waypoint_reached") or executor.p.env.terminated or executor.p.env.truncated:
        measurements["unverified_reason"] = "trial_lift_not_completed"
        return receipt, primitive, measurements
    previous_frame_step = obj.source_step
    for index in range(2):
        if index:
            executor.p.set_gripper(gripper=1, steps=10)
            if executor.p.env.terminated or executor.p.env.truncated:
                measurements["unverified_reason"] = "native_termination_before_second_frame"
                return receipt, primitive, measurements
        executor._refresh([obj.name])
        after = executor.scene.entities.get(obj.id)
        camera = "agentview"
        if after is None or not after.visible:
            executor.scene.refresh([obj.name], camera_view="wrist")
            after = executor.scene.entities.get(obj.id)
            camera = "wrist"
        opening = float(executor.p._last_obs_gripper)
        valid = bool(after and after.visible and after.source_step > previous_frame_step
                     and executor.grasp_minimum_opening <= opening <= .07
                     and after.lower[2] - obj.lower[2] >= .03)
        measurements["frames"].append({"camera": camera, "before": entity_record(obj),
            "after": entity_record(after) if after else None, "gripper_opening": opening,
            "passes_lower_rise_and_aperture": valid})
        if after is not None:
            previous_frame_step = after.source_step
    verified = all(frame["passes_lower_rise_and_aperture"] for frame in measurements["frames"])
    receipt.update(grasp_verified=verified, stop="grasp_verified" if verified else "grasp_not_verified")
    return receipt, primitive, measurements


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
                            if condition.get("contact_stop") == "rpent_pick":
                                kwargs["trace_callback"] = self.motion_evidence.append
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
                        if plan.get("truth_protocol"):
                            if self._diagnostic_symbol is None:
                                raise ValueError("target has no unique private diagnostic binding")
                            evidence["support_reference"] = self.p.env._client.call(
                                "oracle.grasp_reference", kwargs={"name": self._diagnostic_symbol}, timeout_s=30)
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
                            standoff = condition.get("contact_standoff_m")
                            pose.append(obj.upper[2] + standoff if standoff is not None
                                        else max(float(self._initial_xyz[2]), obj.upper[2] + .20))
                            receipt["diagnostic_approach"] = (
                                "measured_overhead_registered_standoff" if standoff is not None
                                else "measured_overhead_20cm_or_reset_height")
                            if standoff is not None:
                                return super().stage_grasp(obj, pose, receipt, minimum_standoff_m=standoff)
                        return super().stage_grasp(obj, pose, receipt)

                    def vla_act(self, prompt, max_chunks, stop, obj=None, **kwargs):
                        if condition["profile"] == "start_full":
                            prompt = self.instruction if case["original_goal_source"] else plan["frypan_full_prompt"]
                            evidence["full_prompt_origin"] = "original_task" if case["original_goal_source"] else "registered_original_scene_grasp_probe"
                            if condition.get("full_prompt_binding") == "target_first" and case["original_goal_source"]:
                                evidence["original_full_prompt"] = prompt
                                prompt = f"pick up the {obj.name} first, then {prompt}"
                                evidence["full_prompt_origin"] = "original_task_with_selected_measured_category_first"
                        elif condition["profile"] == "high_short":
                            contact_name = condition.get("contact_category_aliases", {}).get(obj.name, obj.name)
                            prompt = f"pick up the {contact_name}"
                        evidence["contact_prompt"] = prompt
                        evidence["contact_max_chunks"] = max_chunks
                        if condition.get("contact_stop") == "rpent_pick":
                            if condition.get("contact_verification") == "stable_lower":
                                result, evidence["rpent_pick_result"], evidence["stable_visual_grasp"] = (
                                    rpent_pick_then_stable_measure(self, prompt, max_chunks, obj))
                                return result
                            result, evidence["rpent_pick_result"] = rpent_pick_then_measure(
                                self, prompt, max_chunks, obj)
                            return result
                        return super().vla_act(prompt, max_chunks, stop, obj, **kwargs)

                    def verify_grasp_measurement(self, before):
                        verified = super().verify_grasp_measurement(before)
                        evidence["verification_samples"].append({
                            "measured_verified": verified, "private_contact": self._contacts()})
                        return verified

                    def execute(self, *argv, **kwargs):
                        receipt = super().execute(*argv, **kwargs)
                        evidence["final_private_contact"] = self._contacts()
                        if plan.get("truth_protocol") and evidence.get("support_reference"):
                            # The measured receipt is already final. This
                            # private post-trial hold never enters a request,
                            # does not stop Pi0.5, and is not a policy action.
                            evidence["sustained_hold"] = self.p.env._client.call(
                                "oracle.measure_grasp_hold", kwargs={"name": self._diagnostic_symbol,
                                "reference": evidence["support_reference"],
                                "duration_s": plan["truth_protocol"]["hold_duration_s"]}, timeout_s=120)
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
                    true_sustained_grasp=(evidence.get("sustained_hold") or {}).get("truth", {}).get("success"),
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
                if evidence.get("raised_error") or receipt.get("verification") == "execution_error":
                    raise RuntimeError("preserved instrument/execution failure; stop before further trials")
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
