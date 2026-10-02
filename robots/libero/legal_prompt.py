# Copyright 2026 Zhilun Hu.
# SPDX-License-Identifier: Apache-2.0
"""A1-L deterministic paragraph filtering with original source line evidence."""

import ast
import hashlib
from pathlib import Path
import re

from robots.libero.v5_manual import GENERAL_RULES
from rpent.utils.templates import substitute_text

# Apply these independently of outcomes, including when the reference is absent.
FILTER_RULES = {
    "protocol_rule_sha256": "d844fe44df67d023116cfc586d2951460821472ff5a09ced2b2a68043cb90a45",
    "exclude_constants": ["PROVEN_LEVERS", "KEY_HYPERPARAMETERS", "PERCEPTION_ALGORITHM"],
    "paragraph_patterns": [
        r"libero_(?:spatial|object|goal|10)(?:_(?:task|swap))?\b",
        r"\b(?:task\s*#?\s*\d+|t\d+)\b",
        r"seed[ _-]*0|seed-zero|seed[ _-]*\d+",
        r"recipe|solved\s+reference|task-specific|reference_tag|PROVEN\s+LEVERS",
        r"memory|WORKFLOW\s+step|localization\s+sweep",
        r"see\s+Rule|Rule\s+\d+\w?\s*[—:]",
        r"override at the very top|Stop immediately after",
    ],
    "extra_reason": "memory workflow and dangling rule references replaced with independently written generic guidance",
}


def filtered_prompt(variables=None, *, source: Path | None = None):
    """Return retained original paragraphs, general rules, and full line mapping."""
    source = source or Path(__file__).with_name("prompts") / "evaluate.py"
    payload = source.read_bytes()
    tree = ast.parse(payload.decode())
    # These are the non-workflow sections selected by the original no-memory arm.
    sections = {"ROLE_AND_EVALUATION", "RUNTIME", "GOAL", "RULES", "LOCALIZATION",
                "PERCEPTION_ALGORITHM", "KEY_HYPERPARAMETERS", "OUTPUT_DISCIPLINE",
                "PROVEN_LEVERS"}
    retained, mapping = [], []
    patterns = [re.compile(pattern, re.I) for pattern in FILTER_RULES["paragraph_patterns"]]
    for node in tree.body:
        if not isinstance(node, ast.Assign) or not isinstance(node.value, ast.Constant) or not isinstance(node.value.value, str):
            continue
        name = node.targets[0].id if isinstance(node.targets[0], ast.Name) else ""
        value = node.value.value
        kept = []
        for match in re.finditer(r"\S[\s\S]*?(?=\n\s*\n|\Z)", value):
            text = match[0]
            reasons = [pattern.pattern for pattern in patterns if pattern.search(text)]
            if name not in sections:
                reasons = ["original memory/profile/workflow replaced by independently written legal workflow"]
            if name in FILTER_RULES["exclude_constants"]:
                reasons = ["entire " + name + " constant: test exploration or its derived parameter guidance"]
            start = node.value.lineno + value[:match.start()].count("\n")
            mapping.append({"constant": name, "start_line": start,
                            "end_line": start + text.count("\n"),
                            "action": "delete" if reasons else "keep",
                            "reasons": reasons,
                            "text_sha256": hashlib.sha256(text.encode()).hexdigest()})
            if not reasons:
                kept.append(text)
        if kept and name in sections:
            retained.append(name + "\n" + "\n\n".join(kept))
    workflow = ("Use the current instruction and measured observations. Read MEMORY.md for "
                "original-task category cards, object skill statistics, and recovery lessons. "
                "Choose a relevant task type by its semantic steps, then bind categories to the "
                "current measured scene. Cards give guidance, not completed-state evidence; "
                "current instructions and receipts take priority. Continue within the same episode.")
    prompt = substitute_text("\n\n".join(retained), variables or {}, strict=True)
    prompt += "\n\nGENERAL RULES\n" + GENERAL_RULES + "\n\nLEGAL MEMORY WORKFLOW\n" + workflow + "\n"
    evidence = {"configuration": "A1-L modified RPent", "source": str(source),
                "source_sha256": hashlib.sha256(payload).hexdigest(),
                "rules": FILTER_RULES, "paragraph_line_mapping": mapping,
                "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
                "original_prompt_verbatim": False, "PROVEN_LEVERS_retained": False,
                "independent_general_rules_sha256": hashlib.sha256(GENERAL_RULES.encode()).hexdigest()}
    return prompt, evidence
