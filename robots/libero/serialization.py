"""Canonical typed-choice request serialization for LIBERO.

The evaluator and LIBERO training exporter must use this module.  The wire
contract is deliberately explicit so a training row cannot silently drift
from the request that is sent during evaluation.
"""

from __future__ import annotations

import json
from collections import OrderedDict
from typing import Any, Iterable


SERIALIZER_VERSION = "libero-typed-choice-v1"
COORDINATE_CONVENTION = OrderedDict(
    (
        ("frame", "world"),
        ("unit", "m"),
        ("axis_order", ["x", "y", "z"]),
        ("relation_threshold_m", 0.02),
    )
)
FIELD_ORDER = (
    "instruction",
    "eef_xyz",
    "gripper_qpos",
    "objects_and_regions",
    "available_observations",
    "visual_locations",
    "measured_relative_relations",
    "inferred_held_object",
    "last_tool_receipt",
)
HEADER_ORDER = ("serializer", "coordinate_convention")


def _compact_receipt(receipt: dict[str, Any] | None) -> dict[str, Any] | None:
    if receipt is None:
        return None
    raw_result = receipt.get("log", {}).get("result", {})
    compact: OrderedDict[str, Any] = OrderedDict()
    for key in ("name", "found", "world_xyz", "error", "terminated", "truncated", "final_dist_m"):
        if receipt.get(key) is not None:
            compact[key] = receipt[key]
    for key in ("name", "success", "final_dist_m", "terminated", "truncated"):
        if raw_result.get(key) is not None:
            compact[key] = raw_result[key]
    return dict(compact)


def _compact_locations(locations: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    result: OrderedDict[str, dict[str, Any]] = OrderedDict()
    for name in sorted(locations):
        location = locations[name]
        xyz = location.get("world_xyz")
        result[name] = {
            "xyz_m": [round(float(value), 3) for value in xyz]
            if isinstance(xyz, (list, tuple)) and len(xyz) == 3
            else None
        }
    return dict(result)


def _compact_relations(relations: Iterable[dict[str, Any]]) -> list[str]:
    """Use a bounded relation signature while retaining every measured pair."""
    compact = []
    for relation in relations:
        labels = ",".join(str(value) for value in relation.get("relation", ()))
        distance = relation.get("distance_m")
        distance_text = f"{float(distance):.3f}" if distance is not None else "?"
        compact.append(
            f"{relation.get('from')}>{relation.get('to')}:{labels}:{distance_text}m"
        )
    return compact


def _compact_candidates(candidates: Iterable[dict[str, Any]]) -> list[str]:
    """Keep candidate serialization stable without adding hidden state.

    The short positional signature is intentional: the full candidate list is
    also supplied as the typed-choice options, while this copy keeps the
    canonical state under the 2048-token local Qwen contract.
    """
    fields = ("tool", "object", "region", "height", "yaw")
    return [
        "|".join(str(candidate[key]) for key in fields if key in candidate)
        for candidate in candidates
    ]


def request_body(
    state: dict[str, Any],
    locations: dict[str, dict[str, Any]],
    relations: list[dict[str, Any]],
    held: str | None,
    receipt: dict[str, Any] | None,
    candidates: Iterable[dict[str, Any]] | None = None,
) -> OrderedDict[str, Any]:
    """Build the canonical request body used by eval and training export."""
    state_fields: OrderedDict[str, Any] = OrderedDict(
        (
            ("instruction", state.get("task_language")),
            ("eef_xyz", state.get("state", {}).get("robot0_eef_pos")),
            ("gripper_qpos", state.get("state", {}).get("robot0_gripper_qpos")),
            ("objects_and_regions", state.get("state", {}).get("object_names", [])),
            (
                "available_observations",
                [
                    "agentview_rgb",
                    "agentview_depth",
                    "agentview_camera_geometry",
                    "wrist_rgb",
                    "wrist_depth",
                ],
            ),
            ("visual_locations", _compact_locations(locations)),
            ("measured_relative_relations", _compact_relations(relations)),
            ("inferred_held_object", held),
            ("last_tool_receipt", _compact_receipt(receipt)),
        )
    )
    if tuple(state_fields) != FIELD_ORDER:
        raise AssertionError(
            f"serializer field order drift: {tuple(state_fields)} != {FIELD_ORDER}"
        )
    body: OrderedDict[str, Any] = OrderedDict(
        (
            (
                "header",
                OrderedDict(
                    (
                        ("serializer", SERIALIZER_VERSION),
                        ("coordinate_convention", COORDINATE_CONVENTION),
                    )
                ),
            ),
            ("fields", [{"name": key, "value": value} for key, value in state_fields.items()]),
        )
    )
    if candidates is not None:
        body["candidates"] = _compact_candidates(candidates)
    return body


def serialize_request(*args: Any, **kwargs: Any) -> str:
    """Return deterministic JSON consumed by the choice model."""
    return json.dumps(
        request_body(*args, **kwargs),
        ensure_ascii=False,
        separators=(",", ":"),
    )


def contract_view(value: str | dict[str, Any]) -> dict[str, Any]:
    """Extract only the fields checked before training starts."""
    body = json.loads(value) if isinstance(value, str) else value
    header = body.get("header")
    fields = body.get("fields")
    if not isinstance(header, dict) or not isinstance(fields, list):
        raise ValueError("request is missing canonical header or fields")
    if tuple(header) != HEADER_ORDER:
        raise ValueError(f"request header order mismatch: {tuple(header)}")
    names = [entry.get("name") for entry in fields]
    if names != list(FIELD_ORDER):
        raise ValueError(f"request field order mismatch: {names}")
    convention = header.get("coordinate_convention")
    if convention != COORDINATE_CONVENTION:
        raise ValueError("coordinate convention mismatch")
    return {
        "serializer": header.get("serializer"),
        "field_order": names,
        "coordinate_convention": convention,
    }


def assert_training_eval_compatible(
    evaluation_request: str | dict[str, Any],
    training_row: str | dict[str, Any],
) -> None:
    """Fail closed when a training row differs from an eval request contract."""
    eval_body = json.loads(evaluation_request) if isinstance(evaluation_request, str) else evaluation_request
    train_body = json.loads(training_row) if isinstance(training_row, str) else training_row
    # Training exporters may wrap the canonical request under ``request``.
    train_body = train_body.get("request", train_body)
    eval_contract = contract_view(eval_body)
    train_contract = contract_view(train_body)
    if eval_contract != train_contract:
        raise ValueError(
            "training/evaluation serialization mismatch: "
            f"eval={eval_contract} train={train_contract}"
        )


def training_row(
    state: dict[str, Any],
    locations: dict[str, dict[str, Any]],
    relations: list[dict[str, Any]],
    held: str | None,
    receipt: dict[str, Any] | None,
    candidates: Iterable[dict[str, Any]],
    **labels: Any,
) -> dict[str, Any]:
    """Create a training row while preserving the canonical request verbatim."""
    body = request_body(state, locations, relations, held, receipt, candidates)
    row: OrderedDict[str, Any] = OrderedDict(
        (
            ("request", body),
            ("context", json.dumps(body, ensure_ascii=False, separators=(",", ":"))),
            ("candidates", body["candidates"]),
        )
    )
    row.update(labels)
    return dict(row)
