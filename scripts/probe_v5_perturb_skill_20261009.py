"""Run original-only perturbed skill probes with the existing private runner."""

import hashlib
import json
import os
from pathlib import Path
import sys
import types


def reset_controllers(wrapper):
    for robot in wrapper.env.robots:
        for controller in robot.part_controllers.values():
            controller.update(force=True)
            controller.reset_goal()
    wrapper._update_observables(force=True)
    return wrapper.env._get_observations()


def serve():
    """Restore registered bytes before the first public camera observation."""
    import numpy as np
    from rpent.utils.serialization import to_numpy_tree
    from robots.libero import v5_branch_state, v5_oracle_server
    from scripts import probe_v5_skill501_original as runner

    original_attach = v5_branch_state.attach_branch_state
    original_facade = v5_oracle_server.OriginalOracleFacade

    def attach(wrapper):
        wrapper = original_attach(wrapper)
        wrapper.v5_perturb_reset_controllers = types.MethodType(reset_controllers, wrapper)
        return wrapper

    class LayoutFacade(original_facade):
        def _register_rpc(self):
            super()._register_rpc()
            self._rpc["diagnostic.perturb_registered_reset"] = lambda: self._perturb_reset
            self._readonly_methods.add("diagnostic.perturb_registered_reset")

        def reset(self):
            observation, info = super().reset()
            ref = json.loads(os.environ["V5_PERTURB_REGISTERED_STATE"])
            path = Path(ref["path"])
            if not path.is_absolute() or hashlib.sha256(path.read_bytes()).hexdigest() != ref["sha256"]:
                raise ValueError("registered perturbation reset file changed")
            registered = json.loads(path.read_text())
            if registered["status"] != "prepared" or registered["PRO_files_read"]:
                raise ValueError("only prepared original layouts may run")
            if any(registered["episode"][k] != self._meta[k] for k in ("suite", "task", "seed")):
                raise ValueError("registered layout episode differs from this server")
            if registered["bddl"]["sha256"] != self._bddl_sha:
                raise ValueError("original BDDL asset changed")
            state = np.asarray(registered["rawstate"], dtype="<f8", order="C")
            if hashlib.sha256(state.tobytes()).hexdigest() != registered["state_sha256"]:
                raise ValueError("registered reset bytes changed")
            worker = self._env.env.workers[0]
            worker.set_init_state(state)
            raw = worker.env_call("v5_perturb_reset_controllers", target="self")
            self._env.current_raw_obs = [raw]
            restored = np.asarray(worker.get_sim_state(), dtype="<f8", order="C")
            error = float(np.max(np.abs(restored-state)))
            if error > 1e-8:
                raise ValueError("registered reset does not restore exactly")
            self._perturb_reset = {"registered_state": ref, "state_sha256": registered["state_sha256"],
                "layout_seed": registered["layout_seed"], "restore_max_absolute_error": error,
                "before_first_public_perception": True, "private_coordinates_in_policy_input": False}
            return self._strip_obs(to_numpy_tree(self._env._wrap_obs([raw]))), info

    v5_branch_state.attach_branch_state = attach
    v5_oracle_server.OriginalOracleFacade = LayoutFacade
    try:
        runner.serve()
    finally:
        v5_branch_state.attach_branch_state = original_attach
        v5_oracle_server.OriginalOracleFacade = original_facade


def main():
    from scripts import probe_v5_skill501_original as runner
    from scripts import v5_probe_preflight as preflight

    original_run = runner.run_case
    original_registered = runner.run_registered_skill
    original_validate = preflight.validate_registered_states
    runner.PROBE_MODULE = "scripts.probe_v5_perturb_skill_20261009"

    def validate(cases):
        import numpy as np
        for case in cases:
            ref = case["registered_layout_state"]
            path = Path(ref["path"])
            if not path.is_absolute() or hashlib.sha256(path.read_bytes()).hexdigest() != ref["sha256"]:
                raise ValueError("registered perturbation state changed")
            raw = json.loads(path.read_text())
            state = np.asarray(raw["rawstate"], dtype="<f8", order="C")
            if (raw["episode"] != case["episode"] or raw["status"] != "prepared"
                    or hashlib.sha256(state.tobytes()).hexdigest() != case["state_sha256"]):
                raise ValueError("invalid registered perturbation state")
        return {"perturbed_state_hashes_checked": len(cases), "official_state_substitution": False}

    def run(case, *args):
        os.environ["V5_PERTURB_REGISTERED_STATE"] = json.dumps(case["registered_layout_state"])
        try:
            return original_run(case, *args)
        finally:
            os.environ.pop("V5_PERTURB_REGISTERED_STATE", None)

    def registered(executor, policy, rpc, case, condition):
        evidence = rpc.call("diagnostic.perturb_registered_reset", timeout_s=120)
        executor.skill_budget_v1 = True
        executor.task_completion_receipts_v1 = True
        if case.get("changed_goal"):
            # This is a declared original-vocabulary counterfactual instruction,
            # not a simulator goal predicate supplied to the controller.
            executor.instruction = executor.scene.instruction = case["subtask_prompt"]
        result = original_registered(executor, policy, rpc, case, condition)
        result["private_registered_reset_evidence"] = evidence
        return result

    runner.run_case, runner.run_registered_skill = run, registered
    preflight.validate_registered_states = validate
    try:
        runner.main()
    finally:
        runner.run_case, runner.run_registered_skill = original_run, original_registered
        preflight.validate_registered_states = original_validate


if __name__ == "__main__":
    serve() if "--serve" in sys.argv else main()
