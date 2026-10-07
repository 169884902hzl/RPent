# Copyright 2026 Zhilun Hu.
# SPDX-License-Identifier: Apache-2.0
"""Reject training layouts against explicit, permanent confirmation metadata.

Settled geometry is private generation/audit metadata, never a model input.
This check belongs before a generated layout is admitted to training.
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path


TRAINING_LAYOUT_SEEDS = range(680100, 690000)
MINIMUM_MOKA_XY_DISTANCE_M = .05


def parameter_hash(parameters):
    return hashlib.sha256(json.dumps(parameters, sort_keys=True, separators=(",", ":"),
                                     allow_nan=False).encode()).hexdigest()


def xy(value):
    if (not isinstance(value, (list, tuple)) or len(value) != 2
            or not all(math.isfinite(float(v)) for v in value)):
        raise ValueError("settled moka position must contain two finite metre coordinates")
    return tuple(float(v) for v in value)


def check_training_layout(layout, registry):
    """Check seeds, parameters, identities and distance to every confirmation."""
    if (registry["schema"] != "libero_confirmation_exclusions/1"
            or registry["training_allowed"] is not False
            or registry["minimum_moka_xy_distance_m"] != MINIMUM_MOKA_XY_DISTANCE_M):
        raise ValueError("permanent confirmation exclusion contract changed")
    records = registry["records"]
    if not records or any(r["permanent_training_exclusion"] is not True for r in records):
        raise ValueError("all registered confirmation states must remain excluded")
    seed = layout["layout_seed"]
    if type(seed) is not int or seed not in TRAINING_LAYOUT_SEEDS:
        raise ValueError("training layout seed is outside the separately registered range")
    parameters = parameter_hash(layout["layout_parameters"])
    position = xy(layout["settled_moka_xy_m"])
    distances = []
    for record in records:
        if (seed == record["layout_seed"]
                or parameters == parameter_hash(record["layout_parameters"])
                or layout["state_sha256"] == record["state_sha256"]
                or layout["geometry_fingerprint"] == record["geometry_fingerprint"]):
            raise ValueError("training layout reuses a permanent confirmation identity")
        # A rule declaration without settled geometry cannot establish distance.
        distance = math.dist(position, xy(record["settled_moka_xy_m"]))
        if distance < MINIMUM_MOKA_XY_DISTANCE_M:
            raise ValueError("training moka position is less than 5 cm from confirmation "
                             + record["case_name"])
        distances.append(distance)
    return {"confirmation_records_checked": len(records), "layout_seed": seed,
            "minimum_moka_xy_distance_m": min(distances), "training_allowed": True,
            "geometry_is_private_audit_metadata": True}


def check_registered_training_layout(layout, registry_reference):
    """Read only the caller's explicit, hash-pinned confirmation registry."""
    path = Path(registry_reference["path"])
    if not path.is_absolute():
        raise ValueError("confirmation registry must be an explicit absolute file")
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != registry_reference["sha256"]:
        raise ValueError("permanent confirmation registry changed")
    result = check_training_layout(layout, json.loads(raw))
    return {**result, "confirmation_registry": registry_reference}


def check_registered_training_original_state(state, registry_reference):
    """Exclude original confirmation init states before training collection.

    Layout perturbations use ``check_registered_training_layout`` separately;
    their unperturbed generation bases are not confirmation states themselves.
    The caller supplies the explicit original-state registration, not a pool
    of unreserved candidate states.
    """
    path = Path(registry_reference["path"])
    if not path.is_absolute():
        raise ValueError("confirmation registry must be an explicit absolute file")
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != registry_reference["sha256"]:
        raise ValueError("permanent confirmation registry changed")
    registry = json.loads(raw)
    if (registry["schema"] != "libero_official_confirmation_exclusions/1"
            or registry["training_allowed"] is not False):
        raise ValueError("original confirmation exclusion contract changed")
    records = registry["records"]
    if not records or any(r["permanent_training_exclusion"] is not True for r in records):
        raise ValueError("all registered confirmation states must remain excluded")
    episode = state["episode"]
    identity = tuple(episode[key] for key in ("suite", "task", "seed"))
    digest = state["state_sha256"]
    if not digest:
        raise ValueError("original training state must have a state SHA")
    for record in records:
        confirmed = record["episode"]
        if (identity == tuple(confirmed[key] for key in ("suite", "task", "seed"))
                or digest == record["state_sha256"]):
            raise ValueError("training state reuses a permanent original confirmation")
    return {"confirmation_records_checked": len(records), "training_allowed": True,
            "confirmation_registry": registry_reference}
