"""Full public instruction contact skill, alongside measured split skills."""

from robots.libero.v5_state import Candidate

DESCRIPTION = (
    "skill vla_task() executes the current instruction with the contact policy "
    "until environment termination or its action budget; split skills remain available."
)


def add_full_task_choice(choices, rng):
    """Keep the shared 24-choice cap while admitting the full-task skill."""
    result = list(choices)
    action = Candidate("vla_task")
    if action in result:
        return result
    if len(result) == 24:
        index = next((i for i in reversed(range(len(result)))
                      if result[i].tool in ("vla_subtask", "grasp", "place", "articulate")), None)
        if index is None:
            raise ValueError("full task diagnostic cannot fit the candidate cap")
        result.pop(index)
    result.append(action)
    rng.shuffle(result)
    return result


def execute_full_task(executor, receipt):
    """Use only the public instruction and native interruption signal."""
    if not (getattr(executor, "vla_task_v1", False)
            or getattr(executor, "vla_task_diagnostic_v1", False)):
        raise ValueError("full task skill is disabled")
    instruction = executor.instruction
    if not isinstance(instruction, str) or not instruction.strip():
        raise ValueError("full task diagnostic needs the public instruction")
    result = executor.vla_act(instruction, executor.max_chunks, "chunk_budget")
    executor.capture()
    executor.scene.refresh(sorted(executor.scene.vocabulary))
    receipt.update(**result, verification="unmeasured",
                   contact_prompt=instruction, contact_max_chunks=executor.max_chunks,
                   skill_version="full-public-instruction/2-native-receipt")
