# Copyright 2026 Zhilun Hu.
# SPDX-License-Identifier: Apache-2.0
"""Explicit general guidance and evaluation-only RPent prompt delivery."""

from pathlib import Path

GENERAL_RULES = """Follow the current instruction, including revisions, using measured entities and receipts. Resolve objects and destinations by their attributes and relations. Do not assume unseen geometry or completed actions. Cache stationary destinations before grasping; refine moved objects from close-up depth. Approach handles or rims for open containers, sides for bottles, and tops for boxes. Preserve the grip while carrying. Centre the object over the destination, lower, release, retreat, and check two stable measurements. If grasping fails, inspect the latest evidence, remeasure, and change the approach. If placement fails, regrasp and adjust it. Never repeat a failed action without changing the cause. A receipt that reports execution is not proof of success. Nobody can provide help during this episode. Keep trying until the environment reports success or the available budget ends."""


def manual_text(kind: str, root: Path, *, variables=None) -> tuple[str | None, list[Path]]:
    """Deliver RPent files verbatim; general text contains no task references."""
    if kind == "none":
        return None, []
    if kind == "general":
        return GENERAL_RULES, []
    if kind != "rpent":
        raise ValueError("unknown manual condition")
    from robots.libero.prompts.evaluate import system_prompt
    from rpent.prompt.utils import format_prompt
    variables = {"output_dir":"evaluation_output","recipe_tag":"current_episode",
                 "reference_tag":"current_reference","memory_dir":"memory","task":"0",
                 **(variables or {}), "memory_empty": (variables or {}).get("memory_empty", True)}
    original = format_prompt(system_prompt(variables), variables=variables)
    files = [root/'robots/libero/prompts/evaluate.py',
             root/'robots/libero/guides/strict_hybrid_guide.md',
             root/'robots/libero/guides/pro_hybrid_guide.md',
             root/'robots/libero/guides/env_calibration.md']
    return original+'\n\n'+'\n\n'.join('FILE '+str(p.relative_to(root))+'\n'+p.read_text() for p in files[1:]), files
