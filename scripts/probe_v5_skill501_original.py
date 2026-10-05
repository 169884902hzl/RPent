"""Owned original-task first-place and fixture trials with private metrology.

Each trial resets its registered official state. Setup uses real measured
skills; the first tested skill is recorded separately. Private joint and
predicate measurements never change the executor's receipt or stop rule.
"""

import argparse
from collections import Counter
import copy
import hashlib
import inspect
import json
import os
from pathlib import Path
import re
import sys
import time
import types


ORIGINAL_SUITES = {"libero_spatial", "libero_object", "libero_goal", "libero_10", "libero_90"}
PROBE_MODULE = "scripts.probe_v5_skill501_original"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def private_skill_truth(wrapper, spec):
    """Read official original predicates and actual fixture joints, without stepping."""
    env = wrapper.env
    mode = spec["mode"]
    predicate = {"turn_on": "turnon", "turn_off": "turnoff"}.get(mode, mode)
    goal = [predicate, spec["object_symbol"]]
    if spec["kind"] == "place":
        goal.append(spec["target_symbol"])
    state = env.object_states_dict.get(spec["object_symbol"])
    joint_state = None
    joint_names = []
    if spec["kind"] == "articulate" and state is not None:
        if state.object_state_type == "site":
            site = env.object_sites_dict[spec["object_symbol"]]
            joint_names = list(site.joints)
            if not joint_names:
                state = env.object_states_dict[state.parent_name]
                joint_names = list(env.fixtures_dict[state.object_name].joints)
                goal[1] = state.object_name
        else:
            obj = env.fixtures_dict.get(spec["object_symbol"], env.objects_dict.get(spec["object_symbol"]))
            joint_names = list(obj.joints) if obj is not None else []
        # SiteObjectState has no get_joint_state implementation. In particular,
        # drawer sites must read their own joints instead of every parent joint.
        import numpy as np
        joint_state = [np.asarray(env.sim.data.get_joint_qpos(name)).reshape(-1).tolist()
                       for name in joint_names]
    return {"source": "simulation_diagnostic_only", "predicate": goal,
            "satisfied": bool(env._eval_predicate(goal)), "joint_names": joint_names,
            "joint_qpos": joint_state, "sim_time": float(env.sim.data.time)}


def public_observation(executor):
    """Snapshot only data already available to the measured controller."""
    from robots.libero.v5_state import entity_record
    return {"entities": [entity_record(e) for e in executor.scene.entities.values()],
            "robot": {"eef_xyz": list(map(float, executor.p._last_obs_eef_pos)),
                      "gripper_opening": float(executor.p._last_obs_gripper),
                      "held": executor.held}}


def executed_actions(motions):
    """A selected or acknowledged tool is not evidence of physical execution."""
    return sum(int(move.get("executed_action_count", move.get("steps_used", 0)))
               for move in motions)


def make_probe_env(task_id, seed, suite_name, max_episode_steps):
    """Own the private metrology worker; leave the shared oracle implementation intact."""
    from rlinf.envs.libero.libero_env import LiberoEnv
    from rlinf.envs.libero.utils import benchmark
    from robots.libero.env_server import build_env_cfg

    suite = benchmark.get_benchmark(suite_name)()
    trials = len(suite.get_task_init_states(task_id))
    if not 0 <= seed < trials:
        raise ValueError("official initial-state index out of range; no modulo substitution")
    first_id = sum(len(suite.get_task_init_states(task)) for task in range(task_id))
    cfg = build_env_cfg(task_suite_name=suite_name, specific_reset_id=first_id + seed,
                        seed=seed, max_episode_steps=max_episode_steps)
    cfg.init_params.ignore_done = True

    class SkillProbeEnv(LiberoEnv):
        def get_env_fns(self):
            from robots.libero.v5_branch_state import attach_branch_state
            from robots.libero.v5_reset_seed import attach_reset_seed
            from robots.libero.v5_motion_diagnostics import attach_motion_diagnostic
            def create(factory):
                worker = attach_branch_state(attach_motion_diagnostic(attach_reset_seed(factory())))
                worker.v5_skill501_truth = types.MethodType(private_skill_truth, worker)
                return worker
            return [lambda factory=factory: create(factory) for factory in super().get_env_fns()]

    return SkillProbeEnv(cfg=cfg, num_envs=1, seed_offset=0, total_num_processes=1, worker_info=None)


def serve():
    parser = argparse.ArgumentParser()
    parser.add_argument("--serve", action="store_true")
    parser.add_argument("--suite", choices=sorted(ORIGINAL_SUITES), required=True)
    parser.add_argument("--task", type=int, required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--max-episode-steps", type=int, required=True)
    parser.add_argument("--port", type=int, required=True)
    args = parser.parse_args()
    if os.environ.get("LIBERO_TYPE") != "standard":
        parser.error("LIBERO_TYPE=standard required for owned original metrology")
    from robots.libero.v5_oracle_server import OriginalOracleFacade
    from rpent.utils.serialization import to_numpy_tree

    class SkillFacade(OriginalOracleFacade):
        def _register_rpc(self):
            super()._register_rpc()
            self._rpc["oracle.skill501_truth"] = self.skill_truth
            self._readonly_methods.add("oracle.skill501_truth")
        def skill_truth(self, spec):
            return to_numpy_tree(self._env.env.workers[0].env_call(
                "v5_skill501_truth", args=[spec], target="self"))

    env = make_probe_env(args.task, args.seed, args.suite, args.max_episode_steps)
    SkillFacade(env, meta={"suite": args.suite, "task": args.task, "seed": args.seed,
                           "max_episode_steps": args.max_episode_steps}, motion_trace_v1=True,
                original90_diagnostic=args.suite == "libero_90").serve(
                    transport="http", host="127.0.0.1", port=args.port, parent_watch=True)


def bind_action(executor, policy, spec, tool):
    """An oracle may name a target; its motion binding uses public measurements only."""
    from robots.libero.v5_state import Candidate
    entities = list(executor.scene.entities.values())
    instruction = spec.get("subtask_prompt", executor.instruction)
    obj = policy.bind(spec["object_symbol"], entities, instruction, executor.scene.view_axes)
    if obj is None:
        raise LookupError("source entity missing or ambiguous in public measurements")
    target = None
    if spec.get("target_symbol"):
        target = policy.bind(spec["target_symbol"], entities, instruction,
                             executor.scene.view_axes, source_reference=False)
        if target is None:
            raise LookupError("target entity missing or ambiguous in public measurements")
    return Candidate(tool, obj.id, target.id if target else None, spec["mode"])


def execute_stage(executor, policy, rpc, spec, tool, phase):
    """Keep public controller evidence separate from private post-execution labels."""
    spec = {**spec, "kind": spec.get("kind", spec.get("tool"))}
    action = bind_action(executor, policy, spec, tool)
    record = {"phase": phase, "selected": action.text(),
              "public_before": public_observation(executor),
              "held_before": executor.held}
    support_reference = None
    if spec["kind"] == "grasp":
        support_reference = rpc.call("oracle.grasp_reference",
                                     kwargs={"name": spec["object_symbol"]}, timeout_s=120)
    if spec.get("kind") in {"place", "articulate"}:
        record["private_before"] = rpc.call("oracle.skill501_truth", kwargs={"spec": spec}, timeout_s=120)
    start = time.perf_counter()
    receipt = executor.execute(action)
    record.update(receipt=copy.deepcopy(receipt), wall_s=time.perf_counter() - start,
                  held_after=executor.held, motion_evidence=copy.deepcopy(executor.motion_evidence),
                  verification_measurements=copy.deepcopy(executor.last_verification_measurements),
                  public_after=public_observation(executor))
    if spec.get("kind") in {"place", "articulate"}:
        try:
            record["private_after"] = rpc.call("oracle.skill501_truth", kwargs={"spec": spec}, timeout_s=120)
        except Exception as error:
            record["private_diagnostic_error"] = repr(error)
    if support_reference is not None:
        # This metrology happens after the public receipt is fixed. Its truth
        # label never overrides held or verification and never controls setup.
        try:
            record["private_setup_hold"] = rpc.call("oracle.measure_grasp_hold", kwargs={
                "name": spec["object_symbol"], "reference": support_reference,
                "duration_s": .5}, timeout_s=120)
            record["private_true_sustained_grasp"] = record["private_setup_hold"]["truth"]["success"]
            executor.capture()
            executor._refresh(sorted(executor.scene.vocabulary))
            record["public_after_private_hold"] = public_observation(executor)
        except Exception as error:
            record["private_diagnostic_error"] = repr(error)
    record["executed_actions"] = executed_actions(record["motion_evidence"])
    record["physically_executed"] = record["executed_actions"] > 0
    return record


def run_first_attempt(executor, policy, rpc, case, condition):
    """Real setup first; neither attach an object nor retry the tested skill."""
    result = {"setup": [], "first_attempt": None, "status": "initializing"}
    result["initial_snapshot"] = rpc.call("oracle.snapshot", timeout_s=120)
    for spec in case.get("setup", []):
        try:
            stage = execute_stage(executor, policy, rpc, spec, spec["tool"], "setup")
        except LookupError as error:
            result.update(status="setup_public_binding_missing", binding_error=str(error),
                          public_at_stop=public_observation(executor))
            return result
        except Exception as error:
            result.update(status="probe_error", raised_error=repr(error))
            return result
        result["setup"].append(stage)
        if stage.get("private_diagnostic_error"):
            result.update(status="probe_error", raised_error=stage["private_diagnostic_error"])
            return result
        receipt = stage["receipt"]
        if receipt.get("verification") == "execution_error" or receipt.get("error"):
            result["status"] = "setup_execution_error"
            return result
        if spec["tool"] == "grasp" and not (
                receipt.get("grasp_verified") is True and executor.held == receipt.get("object")):
            result["status"] = "setup_grasp_not_publicly_verified"
            return result
    if case["kind"] == "place" and executor.held is None:
        result["status"] = "setup_did_not_produce_verified_held_object"
        return result
    result["before_first_attempt_snapshot"] = rpc.call("oracle.snapshot", timeout_s=120)
    tool = case["kind"] if condition["executor"] == "current" else "vla_subtask"
    try:
        result["first_attempt"] = execute_stage(executor, policy, rpc, case, tool, "first_attempt")
    except LookupError as error:
        result.update(status="first_attempt_public_binding_missing", binding_error=str(error),
                      public_at_stop=public_observation(executor))
        return result
    except Exception as error:
        result.update(status="probe_error", raised_error=repr(error))
        return result
    result["after_first_attempt_snapshot"] = rpc.call("oracle.snapshot", timeout_s=120)
    if result["first_attempt"].get("private_diagnostic_error"):
        result.update(status="probe_error", raised_error=result["first_attempt"]["private_diagnostic_error"])
    else:
        result["status"] = "first_attempt_recorded"
    return result


def run_case(case, condition, base, endpoints, output):
    from robots.libero.robot_spec import _init_runtime
    from robots.libero.toolkit import LiberoToolkit
    from robots.libero.v5_env_client import V5SkillEnvClient
    from robots.libero.v5_oracle_policy import OriginalOraclePolicy
    from robots.libero.v5_runtime import MeasuredScene, V5Executor, category, scene_vocabulary
    from rpent.dashboard.events import NullDashboardEventSink
    from rpent.memory import MemoryManager
    from rpent.utils.daemon import ProcessDaemon, pick_free_port
    from rpent.utils.rpc import wait_for_ready
    from rpent.utils.rpc.http_rpc import HttpRpcClient

    cfg = {**base, **condition.get("overrides", {}), **case["episode"],
           "max_chunks": condition["max_chunks"], "motion_trace_v1": True}
    events = NullDashboardEventSink()
    port = pick_free_port()
    endpoint = f"http://127.0.0.1:{port}"
    daemon = ProcessDaemon(name="skill501_original", cmd=[sys.executable, "-m", PROBE_MODULE, "--serve",
        "--suite", cfg["suite"], "--task", str(cfg["task"]), "--seed", str(cfg["seed"]),
        "--max-episode-steps", str(cfg.get("max_episode_steps", 10000)), "--port", str(port)],
        log_path=str(output / "oracle_env.log"))
    toolkit, daemons = None, []
    try:
        daemon.start()
        rpc = HttpRpcClient(endpoint)
        wait_for_ready(rpc, daemon=daemon, timeout_s=300)
        runtime_args = argparse.Namespace(**case["episode"], libero_type="standard",
            max_episode_steps=cfg.get("max_episode_steps", 10000), env_endpoint=endpoint,
            env_client_class=V5SkillEnvClient, sam3_endpoint=endpoints["sam3"],
            vla_endpoint=endpoints["vla"], molmo_endpoint=None, cuda_device=None,
            planner="typed_choice", collect_flywheel_data=False)
        daemons, runtime = _init_runtime(runtime_args, output, events, None)
        toolkit = LiberoToolkit(runtime_kwargs=runtime, dashboard_events=events,
                               memory=MemoryManager(output / "empty_memory", memory_access="read_only"),
                               state_output_dir=output)
        scene_flags = {name: cfg[name] for name in inspect.signature(MeasuredScene).parameters
                       if name in cfg and name not in {"toolkit", "rpc", "seed"}}
        scene = MeasuredScene(toolkit, HttpRpcClient(endpoints["sam3"]), cfg["seed"], **scene_flags)
        executor_flags = {name: cfg[name] for name in inspect.signature(V5Executor).parameters
                          if name in cfg and name not in {"toolkit", "scene", "max_chunks", "instruction"}}
        executor = V5Executor(toolkit, scene, cfg["max_chunks"], **executor_flags)
        initial = toolkit.execute_tool("view_env_state", {}).result
        executor.instruction = scene.instruction = initial["task_language"]
        vocab = scene_vocabulary(initial["state"]["object_names"], executor.instruction)
        scene.instance_limits = Counter(category(name) for name in initial["state"]["object_names"])
        scene.refresh(vocab)
        policy = OriginalOraclePolicy(rpc)
        return run_first_attempt(executor, policy, rpc, case, condition)
    finally:
        if toolkit is not None:
            toolkit.close()
        for owned in reversed(daemons):
            owned.stop()
        daemon.stop()


def validate_manifest(plan):
    cases = plan["cases"]
    if len({case["name"] for case in cases}) != len(cases):
        raise ValueError("duplicate registered trial")
    for condition in plan["conditions"].values():
        if condition["executor"] not in {"current", "vla_subtask"} or condition["max_chunks"] <= 0:
            raise ValueError("registered executor or budget is invalid")
    for case in cases:
        if (case["episode"]["suite"] not in ORIGINAL_SUITES
                or case["kind"] not in {"articulate", "place"}
                or case["condition"] not in plan["conditions"]):
            raise ValueError("only explicitly registered original skill trials")
        if not re.fullmatch(r"[A-Za-z0-9_-]+", case["name"]):
            raise ValueError("registered case name must be a single neutral directory name")
        if not re.fullmatch(r"[0-9a-f]{64}", case["state_sha256"]):
            raise ValueError("registered official state SHA is required")
        allowed = {"on", "in"} if case["kind"] == "place" else {"open", "close", "turn_on", "turn_off"}
        if case["mode"] not in allowed:
            raise ValueError("skill/mode mismatch")
        if any(step["tool"] not in {"grasp", "articulate"} for step in case.get("setup", [])):
            raise ValueError("setup must use real measured grasp or articulation")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--shard-index", type=int, default=0)
    parser.add_argument("--shards", type=int, default=1)
    args = parser.parse_args()
    if args.shards < 1 or not 0 <= args.shard_index < args.shards:
        parser.error("shard-index must be in [0, shards)")
    plan = json.loads(args.manifest.read_text())
    validate_manifest(plan)
    config = Path(plan["base_config"]["path"])
    if sha(config) != plan["base_config"]["sha256"]:
        raise ValueError("registered original base config changed")
    base = json.loads(config.read_text())
    if base["libero_type"] != "standard" or os.environ.get("LIBERO_TYPE") != "standard":
        raise ValueError("original standard LIBERO only")
    from rpent.utils.daemon import ProcessDaemon, pick_free_port
    from rpent.utils.rpc import wait_for_ready
    from rpent.utils.rpc.http_rpc import HttpRpcClient
    from rlinf.envs.libero.utils import benchmark
    import numpy as np

    args.output.mkdir(parents=True, exist_ok=False)
    daemons, endpoints = [], {}
    try:
        for name, module, extra in (("sam3", "robots.libero.v5_sam3_server", []),
                                  ("vla", "rpent.robots.components.pi05_vla_server", ["--embodiment", "libero"])):
            port = pick_free_port()
            daemon = ProcessDaemon(name="skill501_" + name,
                cmd=[sys.executable, "-m", module, *extra, "--transport", "http", "--host", "127.0.0.1",
                     "--port", str(port), "--parent-watch"], log_path=str(args.output / ("shared_" + name + ".log")))
            daemon.start()
            daemons.append(daemon)
            endpoints[name] = f"http://127.0.0.1:{port}"
        for name, daemon in zip(("sam3", "vla"), daemons):
            wait_for_ready(HttpRpcClient(endpoints[name]), daemon=daemon, timeout_s=300)
        with (args.output / "episodes.jsonl").open("x") as ledger:
            for case in plan["cases"][args.shard_index::args.shards]:
                for field in ("bddl", "init_file"):
                    if sha(case[field]["path"]) != case[field]["sha256"]:
                        raise ValueError("registered original asset changed: " + field)
                suite = benchmark.get_benchmark(case["episode"]["suite"])()
                state = suite.get_task_init_states(case["episode"]["task"])[case["episode"]["seed"]]
                digest = hashlib.sha256(np.asarray(state, dtype="<f8", order="C").tobytes()).hexdigest()
                if digest != case["state_sha256"]:
                    raise ValueError("registered official initial state changed")
                output = args.output / case["name"]
                output.mkdir()
                row = {"case": case, "output_dir": str(output), "new_training_rows": 0}
                started = time.perf_counter()
                try:
                    row.update(run_case(case, plan["conditions"][case["condition"]], base, endpoints, output))
                except Exception as error:
                    row.update(status="probe_error", raised_error=repr(error))
                row["wall_s"] = time.perf_counter() - started
                trace = output / "choices.jsonl"
                stages = [*row.get("setup", []), *([row["first_attempt"]] if row.get("first_attempt") else [])]
                trace.write_text("".join(json.dumps(stage) + "\n" for stage in stages))
                row["choices_sha256"] = sha(trace)
                (output / "private_skill_diagnostic.json").write_text(json.dumps(row, indent=2) + "\n")
                ledger.write(json.dumps(row) + "\n")
                ledger.flush()
                print(json.dumps({"case": case["name"], "status": row["status"], "wall_s": row["wall_s"]}), flush=True)
                if row.get("raised_error"):
                    raise RuntimeError("preserved development probe error; repair before further cases")
    finally:
        for daemon in reversed(daemons):
            daemon.stop()


if __name__ == "__main__":
    serve() if "--serve" in sys.argv else main()
