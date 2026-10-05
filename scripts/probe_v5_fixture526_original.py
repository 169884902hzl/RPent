"""Fixed original fixture comparisons with explicit before/action/setup labels.

Reuse the physical skill501 runner. The only contact override is the registered
original-style prompt in its macro arm. Private requested/opposite predicates
are read at action boundaries, never used to route, retry or stop a skill.
"""

from contextlib import contextmanager
import copy

from scripts import probe_v5_skill501_original as base_probe


def endpoint_transition(before, after):
    if not isinstance(before, bool) or not isinstance(after, bool):
        return "unknown"
    if before:
        return "already_satisfied_preserved" if after else "already_satisfied_destroyed"
    return "new_requested_endpoint" if after else "requested_endpoint_not_reached"


def labels(rpc, case):
    opposite = {"open": "close", "close": "open"}[case["mode"]]
    return {name: rpc.call("oracle.skill501_truth", kwargs={"spec": {
        "kind": "articulate", "object_symbol": case["object_symbol"], "mode": mode}}, timeout_s=120)
        for name, mode in (("requested", case["mode"]), ("opposite", opposite))}


@contextmanager
def registered_prompt(executor, prompt):
    original = executor.vla_act
    calls = []

    def contact(actual, max_chunks, stop, *args, **kwargs):
        calls.append({"harness_generated_prompt": actual, "effective_prompt": prompt,
                      "max_chunks": max_chunks, "stop": stop,
                      "origin": "registered_original_style_same_requested_skill"})
        return original(prompt, max_chunks, stop, *args, **kwargs)

    executor.vla_act = contact
    try:
        yield calls
    finally:
        executor.vla_act = original


@contextmanager
def diagnostic_hooks():
    original_stage, original_case = base_probe.execute_stage, base_probe.run_case
    original_module = base_probe.PROBE_MODULE
    active = {}

    def stage(executor, policy, rpc, spec, tool, phase, **kwargs):
        case = active["case"]
        before = labels(rpc, case)
        scope = rpc.call("diagnostic.fixture_chunk_start", kwargs={
            "phase": phase, "max_chunks": active["condition"]["max_chunks"]}, timeout_s=120)
        try:
            if phase == "first_attempt" and active["condition"]["executor"] == "vla_subtask":
                with registered_prompt(executor, case["original_style_contact_prompt"]) as contacts:
                    record = original_stage(executor, policy, rpc, spec, tool, phase, **kwargs)
                record["registered_contact_prompts"] = contacts
            else:
                record = original_stage(executor, policy, rpc, spec, tool, phase, **kwargs)
        finally:
            completed = rpc.call("diagnostic.fixture_chunk_end", timeout_s=120)
        record["diagnostic_chunk_scope"] = {"before": scope, "after": completed}
        after = labels(rpc, case)
        record["private_requested_opposite_before"] = before
        record["private_requested_opposite_after"] = after
        record["requested_endpoint_transition"] = endpoint_transition(
            before["requested"]["satisfied"], after["requested"]["satisfied"])
        record["private_labels_used_for_control"] = False
        return record

    def run_case(case, condition, base, endpoints, output):
        active.update(case=case, condition=condition)
        result = original_case(case, condition, base, endpoints, output)
        first = result.get("first_attempt")
        if first:
            before = first["private_requested_opposite_before"]
            after = first["private_requested_opposite_after"]
            result.update(
                requested_endpoint_transition=first["requested_endpoint_transition"],
                first_attempt_from_opposite_endpoint=(before["requested"]["satisfied"] is False
                    and before["opposite"]["satisfied"] is True),
                newly_achieved_requested_endpoint=(before["requested"]["satisfied"] is False
                    and before["opposite"]["satisfied"] is True and after["requested"]["satisfied"] is True),
                initial_requested_opposite=copy.deepcopy((result["setup"][0] if result["setup"] else first)[
                    "private_requested_opposite_before"]),
                setup_completed_requested_direction=(not result["setup"] or (
                    before["requested"]["satisfied"] is False and before["opposite"]["satisfied"] is True)),
                qualification_authorized=False)
        return result

    base_probe.execute_stage, base_probe.run_case = stage, run_case
    base_probe.PROBE_MODULE = "robots.libero.v5_fixture_probe_env"
    try:
        yield
    finally:
        base_probe.execute_stage, base_probe.run_case = original_stage, original_case
        base_probe.PROBE_MODULE = original_module


def main():
    with diagnostic_hooks():
        base_probe.main()


if __name__ == "__main__":
    main()
