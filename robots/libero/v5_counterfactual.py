# Copyright 2026 Zhilun Hu.
# SPDX-License-Identifier: Apache-2.0
"""Training-only counterfactual goals in an unchanged original scene."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path


def replace_section(text: str, name: str, replacement: str) -> str:
    """Replace one BDDL section, retaining every other scene byte."""
    match = re.search(r"\(:" + re.escape(name) + r"\b", text, re.IGNORECASE)
    if match is None:
        raise ValueError(f"original BDDL lacks {name}")
    depth = 0
    for end in range(match.start(), len(text)):
        depth += (text[end] == "(") - (text[end] == ")")
        if depth == 0:
            return text[:match.start()] + replacement + text[end + 1:]
    raise ValueError("unbalanced original BDDL")


def counterfactual_bddl(text: str, goal: list[str], instruction: str) -> str:
    """Change language and goal only; coordinates remain private label inputs."""
    if len(goal) != 3 or goal[0].lower() not in ("on", "in"):
        raise ValueError("registered counterfactuals use on/in only")
    if not all(re.fullmatch(r"[A-Za-z0-9_]+", token) for token in goal):
        raise ValueError("invalid private predicate symbol")
    if not instruction or re.search(r"[();]", instruction):
        raise ValueError("language is plain original-scene text")
    changed = replace_section(text, "goal", "(:goal (And (" + " ".join(goal) + ")))")
    return replace_section(changed, "language", "(:language " + instruction.rstrip(".") + ")")


def register_original_goal_variant(suite_name: str, task_id: int, spec: dict) -> str:
    """Use LIBERO's benchmark registry; no installed package is modified."""
    from libero.libero import benchmark, get_libero_path

    if suite_name not in ("libero_spatial", "libero_object", "libero_goal", "libero_10"):
        raise ValueError("counterfactual scenes must be original tasks")
    if (spec["suite"], spec["task"]) != (suite_name, task_id):
        raise ValueError("counterfactual belongs to another original scene")
    base = benchmark.get_benchmark(suite_name)
    original = base().get_task(task_id)
    original_path = Path(get_libero_path("bddl_files")) / original.problem_folder / original.bddl_file
    if hashlib.sha256(original_path.read_bytes()).hexdigest() != spec["original_bddl_sha256"]:
        raise ValueError("original scene changed since counterfactual registration")
    variant_path = Path(spec["variant_bddl"])
    if not variant_path.is_absolute() or hashlib.sha256(variant_path.read_bytes()).hexdigest() != spec["variant_bddl_sha256"]:
        raise ValueError("registered counterfactual BDDL changed")
    if counterfactual_bddl(original_path.read_text(), spec["goal"], spec["instruction"]) != variant_path.read_text():
        raise ValueError("counterfactual changed more than registered goal/language")

    def initialize(self, *args, **kwargs):
        base.__init__(self, *args, **kwargs)
        task = self.tasks[task_id]
        self.tasks[task_id] = task._replace(bddl_file=str(variant_path), language=spec["instruction"])

    name = "v5cf_" + suite_name + "_" + spec["variant_bddl_sha256"][:12]
    cls = type(name, (base,), {"__init__": initialize})
    benchmark.register_benchmark(cls)
    return name.lower()
