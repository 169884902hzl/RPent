# Copyright 2026 Zhilun Hu.
# SPDX-License-Identifier: Apache-2.0
"""Explicit executor parameters, separated by general and RPent provenance."""

import hashlib
import json
import math
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
        learned = package.get("original_skill_evidence", {}).get(name)
        if learned is not None:
            result["original_skill_evidence"] = learned
            height = learned.get("verified_staging_height_median_above_measured_top")
            if isinstance(height, (int, float)) and math.isfinite(height) and height > 0:
                result["approach_height_m"] = height
                result["restage_height_m"] = max(result["restage_height_m"], height)
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


def attach_legal_memory(package: dict | None, manifest_path: Path, root: Path) -> dict:
    """Use only explicitly hashed original skill summaries and failure lessons."""
    if package is not None and package["kind"] != "general":
        raise ValueError("legal memory cannot import RPent skill parameters")
    manifest = json.loads(manifest_path.read_text())
    if manifest.get("origin") != "original_oracle" or manifest.get("PRO_inputs_used") is not False or manifest.get("RPent_cards_in_training"):
        raise ValueError("legal memory requires original-only provenance")
    documents = {}
    hashes = {}
    for name in ("object_skill_cards.json", "failure_lessons.json"):
        descriptor = manifest["files"][name]
        payload = Path(descriptor["path"]).read_bytes()
        if hashlib.sha256(payload).hexdigest() != descriptor["sha256"]:
            raise ValueError("legal memory file changed")
        documents[name] = json.loads(payload)
        hashes[name] = descriptor["sha256"]
    package = dict(package or load_profiles("general", root))
    package["original_skill_evidence"] = {
        p["category"]: p for p in documents["object_skill_cards.json"]["profiles"]
    }
    package["failure_lessons"] = documents["failure_lessons.json"]["rules"]
    package["legal_memory"] = {"manifest_sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
                               "files": hashes, "origin": "original_oracle"}
    return package
