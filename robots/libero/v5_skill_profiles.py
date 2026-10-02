# Copyright 2026 Zhilun Hu.
# SPDX-License-Identifier: Apache-2.0
"""Explicit executor parameters, separated by general and RPent provenance."""

import hashlib
import json
from pathlib import Path


def load_profiles(kind: str, root: Path) -> dict | None:
    """Load only the selected profile; general settings never open RPent guides."""
    if kind == "none":
        return None
    if kind == "general":
        return {"kind": kind, "common": {"approach_height_m": .06,
                "restage_height_m": .10, "carry_step_clip_m": .025},
                "source": "generic shape-based measured approach rules",
                "training_allowed": True}
    if kind != "rpent":
        raise ValueError("unknown skill profile")
    path = root / "docs/harness_v5/rpent_skill_profiles.json"
    document = json.loads(path.read_text())
    for profile in document["profiles"]:
        source = root / profile["source"]
        if hashlib.sha256(source.read_bytes()).hexdigest() != profile["source_sha256"]:
            raise ValueError("RPent skill profile source changed")
    return {"kind": kind, "common": {"approach_height_m": .175,
            "restage_height_m": .175, "carry_step_clip_m": .025},
            "profiles": document["profiles"], "path": str(path),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "training_allowed": False,
            "unapplied": ["scene-specific absolute coordinates and suite/task selectors",
                          "drawer short push: source does not specify a general displacement",
                          "moka body-versus-handle grasp: conflicting source retained; measured handle used"]}


def parameters_for(package: dict | None, name: str) -> dict:
    """Select parameters by measured category, never by task or suite number."""
    if package is None:
        return {}
    result = dict(package["common"])
    result["kind"] = package["kind"]
    if package["kind"] == "general":
        result.update(rim_fraction=.7, side_offset_m=.03)
        return result
    group = ("moka_pot" if "moka" in name else "cup_bowl"
             if any(w in name for w in ("mug", "cup", "bowl", "ramekin")) else
             "tall_bottle" if "bottle" in name else "can" if "can" in name else "box")
    source_profiles = [p for p in package["profiles"] if p["category"] in ("all", group)]
    result["source_lines"] = [{"source": p["source"], "lines": p["lines"],
                               "sha256": p["source_sha256"]} for p in source_profiles]
    for profile in source_profiles:
        for key in ("rim_grasp_world_y_offset_m", "carry_step_clip_m", "carry_lift_m"):
            if key in profile:
                value = profile[key]
                result[key] = sum(value) / len(value) if isinstance(value, list) else value
    return result
