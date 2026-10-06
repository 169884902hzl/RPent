"""Owned original microwave public-parent selector; fixed shared probe unchanged."""

import hashlib
from pathlib import Path
import re


VERSION = "original-microwave-public-parent/1-dev"


def registered_public_microwave_instruction(spec):
    if spec.get("object_category") != "microwave":
        return None
    if spec.get("kind", spec.get("tool")) != "articulate" or spec.get("mode") not in ("open", "close"):
        raise ValueError("public microwave selector is only for registered open/close articulation")
    prompt = spec.get("subtask_prompt", f"{spec['mode']} the microwave")
    if not isinstance(prompt, str) or re.fullmatch(spec["mode"] + r" the microwave", prompt) is None:
        raise ValueError("registered original microwave prompt contradicts public category/mode")
    return prompt


def bind_public_microwave(executor, policy, spec, tool):
    from robots.libero.v5_state import Candidate

    prompt = registered_public_microwave_instruction(spec)
    if prompt is None or tool != "articulate" or spec.get("target_symbol"):
        raise ValueError("this selection adapter only binds registered microwave articulation")
    step = executor.toolkit._state.latest_step
    parents = [entity for entity in executor.scene.entities.values()
               if entity.name == "microwave" and entity.part_of is None
               and entity.visible and entity.source_step == step]
    if len(parents) != 1:
        raise LookupError("current public microwave parent missing or ambiguous")
    parent = parents[0]
    policy.last_binding = {
        "version": VERSION, "basis": "unique_current_visible_measured_microwave_parent",
        "source_entity": parent.id, "source_step": parent.source_step,
        "public_condition_instruction": prompt,
        "door_or_handle_required_for_selector": False,
        "private_symbol_or_geometry_used_for_selector": False,
    }
    return Candidate(tool, parent.id, mode=spec["mode"])


def public_fixture_capture(executor):
    state = executor.toolkit._state
    step = state.latest_step
    views = {}
    for camera in ("agentview", "wrist"):
        files = {}
        for label, name in (("rgb", f"{camera}_high.png"),
                            ("world_rgbd", f"{camera}_world_high.npz"),
                            ("camera_metadata", f"{camera}_metadata.json")):
            path = Path(state.artifact_path(name, step=step))
            files[label] = ({"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
                            if path.is_file() else {"path": str(path), "missing": True})
        views[camera] = {"source": "perception", "source_step": step, "files": files}
    return {"source": "perception", "source_step": step, "views": views,
            "fusion_version": "rgbd_dual_view/1", "new_captures": 0, "new_robot_actions": 0}


def install_owned_adapter(probe):
    original_bind = probe.bind_action
    original_instruction = probe.registered_drawer_instruction
    original_execute = probe.execute_stage

    def instruction(spec):
        microwave = registered_public_microwave_instruction(spec)
        return microwave if microwave is not None else original_instruction(spec)

    def bind(executor, policy, spec, tool, *, public_drawer_subtask=False):
        if spec.get("object_category") == "microwave" and tool == "articulate":
            return bind_public_microwave(executor, policy, spec, tool)
        return original_bind(executor, policy, spec, tool,
                             public_drawer_subtask=public_drawer_subtask)

    def execute(executor, policy, rpc, spec, tool, phase, **kwargs):
        if spec.get("object_category") != "microwave" or tool != "articulate":
            return original_execute(executor, policy, rpc, spec, tool, phase, **kwargs)
        before = public_fixture_capture(executor)
        result = original_execute(executor, policy, rpc, spec, tool, phase, **kwargs)
        after = public_fixture_capture(executor)
        result["public_microwave_adapter"] = {
            "version": VERSION, "method": "current160_no_prehandle_unique_public_parent",
            "recipe_scope": "joint method selection, not isolated causal attribution or qualification",
            "before_rgbd": before, "after_rgbd": after,
            "strict_verifier": "SOURCE571 measured_fixture_endpoint/2-dev unchanged",
            "verdict": result.get("receipt", {}).get("articulate_verified"),
        }
        return result

    probe.bind_action, probe.registered_drawer_instruction, probe.execute_stage = bind, instruction, execute


def main():
    from scripts import probe_v5_skill501_original as probe
    install_owned_adapter(probe)
    probe.main()


if __name__ == "__main__":
    main()
