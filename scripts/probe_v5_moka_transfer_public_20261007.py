"""Original moka sentence through the measured SOURCE571 placement path.

Only the public selected moka and stove bind the action. Original task status
is recorded before and after the action and never controls its termination.
"""

import copy


def execute_original_subtask(executor, case, condition, obj, receipt, evidence):
    from robots.libero import v5_subtasks
    from robots.libero.v5_runtime import V5Executor
    from robots.libero.v5_state import Candidate, entity_record

    if not case.get("original_goal_source") or not case.get("instruction"):
        raise ValueError("Original moka transfer needs its complete original instruction")
    stoves = [entity for entity in executor.scene.entities.values()
              if entity.name == "stove" and entity.visible]
    if len(stoves) != 1:
        executor.scene.refresh(["stove"])
        stoves = [entity for entity in executor.scene.entities.values()
                  if entity.name == "stove" and entity.visible]
    if len(stoves) != 1:
        receipt.update(executed=False, place_verified=None, verification="unmeasured",
                       failure_reason="original_transfer_public_stove_binding_missing_or_ambiguous")
        return
    target = stoves[0]
    action = Candidate("vla_subtask", obj.id, target.id, "on")
    prompt = case["instruction"]

    def private_status():
        try:
            return executor.p.env._client.call("oracle.status", timeout_s=30)
        except Exception:
            evidence["error_stage"] = "private_metrology"
            raise

    evidence["private_original_task_status_before"] = private_status()
    evidence.update(contact_prompt=prompt, contact_max_chunks=condition["max_chunks"],
                    full_prompt_origin="original_BDDL_complete_task_sentence",
                    public_transfer_binding={"object": entity_record(obj),
                                             "target": entity_record(target), "mode": "on"})
    original_prompt = v5_subtasks.subtask_prompt

    def exact_original_prompt(selected, entities, view_axes):
        # Keep the runtime's measured-instance binding check before using the
        # unmodified public task sentence.
        original_prompt(selected, entities, view_axes)
        return prompt

    v5_subtasks.subtask_prompt = exact_original_prompt
    try:
        # SOURCE571 executes all five controls in each VLA chunk. Native task
        # status is a private diagnostic latch and cannot stop the macro.
        with executor.p.env.complete_skill():
            V5Executor.execute_subtask(executor, action, receipt)
    finally:
        v5_subtasks.subtask_prompt = original_prompt
    receipt.update(tool="vla_subtask", object=obj.id, target=target.id, mode="on",
                   execution_kind="complete_original_subtask_with_public_placement",
                   original_public_instruction=prompt)
    evidence["public_placement_verdict"] = receipt.get("place_verified")
    evidence["public_placement_measurements"] = copy.deepcopy(executor.last_verification_measurements)
    evidence["public_receipt_before_private_metrology"] = copy.deepcopy(receipt)
    evidence["private_original_task_status_after"] = private_status()


def main():
    from scripts import probe_v5_grasp449_20261005 as probe

    probe.execute_original_subtask = execute_original_subtask
    probe.main()


if __name__ == "__main__":
    main()
