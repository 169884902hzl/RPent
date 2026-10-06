# Copyright 2026 Zhilun Hu.
# SPDX-License-Identifier: Apache-2.0
"""Measured entities, bounded choices and receipts for LIBERO harness v5."""

from __future__ import annotations

import json
import math
import random
import re
from dataclasses import asdict, dataclass
from typing import Any, Sequence

VERSION = "libero-harness/5-dev"
MAX_PROMPT_TOKENS = 3072
CHOICE_INSTRUCTION = (
    "Choose the next action for the instruction from measured entities and "
    "receipts. Finish only when completion has evidence; ask_help if needed."
)
STAGING = ("direct", "above_10cm", "yaw_90")
RECEIPT_COMPACT_VERSION = "exact-evidence-dedup/5-utf8-receipts"
CANDIDATE_FAILURE_ENCODING_VERSION = "candidate-failures/2-default-zero"
RECEIPT_DEFAULT_KEYS = (
    "receipt_version", "executed", "chunks", "stop_condition",
    "subtask_version", "verification_scope",
    "object", "target", "mode", "verification", "effect", "reason",
    "articulate_verified", "place_verified", "grasp_verified",
)


@dataclass(frozen=True)
class Entity:
    """An instance measured from an RGB-D mask, in world metres."""

    id: str
    name: str
    xyz: tuple[float, float, float]
    lower: tuple[float, float, float]
    upper: tuple[float, float, float]
    visible: bool = True
    source_step: int = 0
    part_of: str | None = None
    geometry: str | None = None

    def __post_init__(self) -> None:
        values = (*self.xyz, *self.lower, *self.upper)
        if not all(math.isfinite(x) for x in values):
            raise ValueError("nonfinite perception measurement")
        if any(lo > hi for lo, hi in zip(self.lower, self.upper)):
            raise ValueError("invalid measured bounds")


@dataclass(frozen=True)
class Candidate:
    """A finite skill choice; numerical motion is resolved by the executor."""

    tool: str
    object: str | None = None
    target: str | None = None
    mode: str | None = None

    def text(self) -> str:
        args = [x for x in (self.object, self.target, self.mode) if x is not None]
        return f"{self.tool}({','.join(args)})"

    @classmethod
    def from_text(cls, text: str) -> Candidate:
        """Parse the finite public choice spelling, without executable code."""
        match = re.fullmatch(r"([a-z_]+)\(([^()]*)\)", text)
        if match is None:
            raise ValueError(f"invalid candidate: {text}")
        tool, body = match.groups()
        args = body.split(",") if body else []
        if tool in ("place", "adjust_place") and len(args) == 3:
            return cls(tool, *args)
        if tool in ("grasp", "articulate") and len(args) == 2:
            return cls(tool, args[0], mode=args[1])
        if tool == "vla_subtask":
            if len(args) == 3 and args[2] in ("on", "in"):
                return cls(tool, *args)
            if len(args) == 2 and args[1] in ("open", "close", "turn_on", "turn_off"):
                return cls(tool, args[0], mode=args[1])
        if tool == "regrasp_restage" and len(args) == 1:
            return cls(tool, args[0])
        if tool == "rpent_step" and len(args) == 1 and re.fullmatch(r"[1-9]\d*", args[0]):
            return cls(tool, mode=args[0])
        if tool in ("finish", "ask_help", "release", "retreat", "reperceive", "card_next", "wrist_scan", "clear_view") and not args:
            return cls(tool)
        raise ValueError(f"unsupported candidate: {text}")


def relations(
    entities: list[Entity],
    threshold: float = 0.02,
    right_axis: tuple = (1, 0, 0),
    front_axis: tuple = (0, -1, 0),
) -> list[str]:
    """Derive relations only from measured centres and surface bounds."""
    result = []
    for a in entities:
        for b in entities:
            if a.id == b.id or not (a.visible and b.visible):
                continue
            delta = [a.xyz[i] - b.xyz[i] for i in range(3)]
            if sum(delta[i] * right_axis[i] for i in range(3)) < -threshold:
                result.append(f"rel {a.id} left_of {b.id}")
            if sum(delta[i] * front_axis[i] for i in range(3)) > threshold:
                result.append(f"rel {a.id} in_front_of {b.id}")
            inside_xy = all(b.lower[i] <= a.xyz[i] <= b.upper[i] for i in (0, 1))
            # Visible-surface quantiles can straddle a contact surface.
            overlapping_xy = all(min(a.upper[i], b.upper[i]) > max(a.lower[i], b.lower[i]) for i in (0, 1))
            if overlapping_xy and abs(a.lower[2] - b.upper[2]) <= threshold:
                result.append(f"rel {a.id} on {b.id}")
            if inside_xy and b.lower[2] <= a.xyz[2] <= b.upper[2]:
                result.append(f"rel {a.id} in {b.id}")
            if math.dist(a.xyz, b.xyz) <= threshold:
                result.append(f"rel {a.id} near {b.id}")
    return result


def fixture_actions(name: str) -> tuple[str, ...]:
    if name.endswith("surface"):
        return ()
    if any(word in name for word in ("drawer", "cabinet", "microwave")):
        return ("open", "close")
    if any(word in name for word in ("stove", "switch", "faucet")):
        return ("turn_on", "turn_off")
    return ()


def candidates(
    entities: list[Entity],
    instruction: str,
    eef_xyz: tuple[float, ...],
    held: str | None,
    receipts: list[dict],
    rng: random.Random,
    card: dict | None = None,
    *,
    adjust_place: bool = False,
    persist_attempts: bool = False,
    finish_rejections: int = 0,
    recovery_status: dict | None = None,
    execution_error_cooldown: bool = False,
    use_cached_measurements: bool = False,
    gripper_opening: float | None = None,
    measurement_progress_blocking: bool = True,
    vla_subtasks: Sequence[Candidate] = (),
) -> list[Candidate]:
    """Enumerate at most 24 skills from perception, with no goal access."""
    visible = [e for e in entities if e.visible or (
        use_cached_measurements and e.geometry and e.geometry.startswith("cached_perception"))]
    macros = list(dict.fromkeys(vla_subtasks))[:6]
    for action in macros:
        if action.tool != "vla_subtask" or Candidate.from_text(action.text()) != action:
            raise ValueError(f"invalid VLA subtask candidate: {action.text()}")
    macro_entities = {eid for c in macros for eid in (c.object, c.target) if eid is not None}
    macro_action_entities = {c.object if c.target is None or held is None else c.target for c in macros}
    visible.sort(
        key=lambda e: (
            e.id not in macro_action_entities,
            e.id not in macro_entities,
            not (e.name.lower() in instruction.lower() or e.name.startswith("area ")),
            math.dist(e.xyz, eef_xyz),
            e.id,
        )
    )
    selected = visible[:8]
    control = [
        Candidate(x) for x in ("reperceive", "retreat", "release", "finish", "ask_help")
        if x != "release" or held is not None or (gripper_opening is not None and gripper_opening < .075)
        if x != "finish" or not persist_attempts or finish_rejections < 2
        if x != "reperceive" or not recovery_status or not recovery_status["reperceive_cooldown"]
    ]
    recovering = recovery_status is not None and (
        recovery_status["no_progress_steps"] >= 2
        or bool(receipts and receipts[-1].get("tool") == "ask_help" and not receipts[-1].get("executed"))
    )
    if recovering:
        control.extend((Candidate("wrist_scan"), Candidate("clear_view")))
        if held is None:
            graspable = next((e for e in selected if not fixture_actions(e.name)
                             and not e.name.startswith("area ") and not e.name.endswith("surface")), None)
            if graspable is not None:
                control.append(Candidate("regrasp_restage", graspable.id))
    recovery_receipt = next((r for r in reversed(receipts) if r.get("tool") not in
                            ("ask_help", "finish", "reperceive", "retreat")), {}) if persist_attempts else (receipts[-1] if receipts else {})
    if recovery_receipt.get("tool") in ("grasp", "regrasp_restage"):
        if recovery_receipt.get("grasp_verified") is False:
            obj = recovery_receipt.get("object")
            if any(e.id == obj and e.visible for e in entities):
                if Candidate("regrasp_restage", obj) not in control:
                    control.append(Candidate("regrasp_restage", obj))
    motions = []
    # Round-robin staging retains object coverage when there are >6 objects.
    if held is None:
        for mode in STAGING:
            for e in selected:
                actions = fixture_actions(e.name)
                if actions:
                    if mode == STAGING[0]:
                        motions.extend(
                            Candidate("articulate", e.id, mode=a) for a in actions
                        )
                else:
                    if e.name != "table" and not e.name.startswith("area ") and not e.name.endswith("surface"):
                        motions.append(Candidate("grasp", e.id, mode=mode))
    else:
        motions.extend(
            Candidate("place", held, e.id, mode)
            for e in selected
            if e.id != held
            if e.geometry not in ("measured_front_band", "measured_front_surface")
            for mode in ("on", "in")
            if mode == "on" or not e.name.endswith("surface")
        )
        motions.extend(
            Candidate("articulate", e.id, mode=a)
            for e in selected
            for a in fixture_actions(e.name)
        )
    # Keep the source/target's split skill next to its macro before filling the
    # remaining slots by the existing instruction and measured-distance order.
    priority = []
    for macro in macros:
        priority.append(macro)
        if macro.target is not None:
            split = (Candidate("grasp", macro.object, mode="direct") if held is None
                     else Candidate("place", macro.object, macro.target, macro.mode))
        else:
            split = Candidate("articulate", macro.object, mode=macro.mode)
        if split in motions:
            priority.append(split)
    motions = list(dict.fromkeys(priority + motions))
    control = upgrade_controls(control, entities, held, receipts, card=card, adjust_place=adjust_place)
    result = motions[: 24 - len(control)] + control
    rng.shuffle(result)
    if execution_error_cooldown:
        result = [c for c in result if not execution_error_blocked(c, receipts)]
    if measurement_progress_blocking and recovery_status:
        result = [c for c in result if not measurement_progress_blocked(c, recovery_status)]
    return result


def measurement_progress_blocked(action: Candidate, recovery_status: dict | None) -> bool:
    """Apply the same scene-change gate to ordinary and resolved card actions."""
    return bool(recovery_status and (
        action.text() in recovery_status.get("blocked_actions", ())
        or action.text() in recovery_status.get("attempt_limit_actions", ())))


def execution_error_blocked(action: Candidate, receipts: list[dict]) -> bool:
    """Suppress the matching execution error for the next three decisions.

    A measured physical failure remains eligible for contact-policy retries.
    Candidate filtering does not add any field to the serialized state.
    """
    return any(
        receipt.get("verification") == "execution_error"
        and (receipt.get("card_action") == action.text() or all(
            receipt.get(key) == getattr(action, key)
            for key in ("tool", "object", "target", "mode")))
        for receipt in receipts[-3:]
    )


def upgrade_controls(base, entities, held, receipts, *, card=None, adjust_place=False):
    """Add format controls to a recorded/live base list with the same 24 cap.

    No label access: make room by dropping the last ordinary motion. A replay
    row that loses its physically acceptable option must be excluded.
    """
    result = list(base)
    extra = []
    if card is not None and Candidate("card_next") not in result:
        extra.append(Candidate("card_next"))
    if adjust_place:
        last = next((r for r in reversed(receipts) if r.get("tool") in ("place", "adjust_place")), None)
        ids = {e.id for e in entities if e.visible}
        if last and (last.get("place_verified") is False or last.get("error")
                     or last.get("verification_reason") == "interior_containment_not_measured"):
            if held in (None, last.get("object")) and last.get("object") in ids and last.get("target") in ids:
                recovery = Candidate("adjust_place", last["object"], last["target"], last.get("mode", "on"))
                if recovery not in result:
                    extra.append(recovery)
    for new in extra:
        if len(result) == 24:
            index = next((i for i in reversed(range(len(result)))
                          if result[i].tool in ("grasp", "place", "articulate")), None)
            if index is None:
                raise ValueError("candidate cap cannot admit a recovery control")
            result.pop(index)
        result.append(new)
    return result


def compact_receipt(receipt: dict) -> dict:
    """Remove exact duplicate evidence only from the model-visible receipt.

    The executor keeps the complete receipt for audit and offline labels.
    Furniture displacement uses the same entity's measurement.dxyz_cm and its
    verified value uses articulation_verified when identical. Furniture state
    and before/after use the same object's articulation_state when identical.
    Thus omitted duplicate values remain available under their canonical keys;
    furniture IDs and independent or conflicting evidence are retained.
    """
    compact = dict(receipt)
    if "stop" in compact and compact.get("stop_condition") == compact["stop"]:
        del compact["stop"]
    measured = receipt.get("measurement")
    if not isinstance(measured, dict) or not isinstance(measured.get("furniture"), dict):
        return compact
    measured = dict(measured)
    displacement = measured.get("dxyz_cm", {})
    endpoint = receipt.get("articulation_state", {})
    furniture = {}
    for eid, original in measured["furniture"].items():
        if not isinstance(original, dict):
            furniture[eid] = original
            continue
        evidence = dict(original)
        if ("dxyz_cm" in evidence and eid in displacement
                and evidence["dxyz_cm"] == displacement[eid]):
            del evidence["dxyz_cm"]
        if ("verified" in evidence and "articulate_verified" in receipt
                and evidence["verified"] == receipt["articulate_verified"]):
            del evidence["verified"]
        if eid == receipt.get("object") and isinstance(endpoint, dict):
            for key in ("state", "before", "after"):
                if key in evidence and key in endpoint and evidence[key] == endpoint[key]:
                    del evidence[key]
        furniture[eid] = evidence
    measured["furniture"] = furniture
    compact["measurement"] = measured
    return compact


def receipt_lines(receipts: list[dict]) -> list[str]:
    """Write the last three receipts with explicit shared metadata defaults.

    The first receipt's defaults apply to all three receipts; each receipt's
    own fields override them. No new top-level state row is introduced.
    Only fields present and exactly equal in every saved receipt are shared;
    the tool and full measurement payload always remain in each row. Shared
    object/mode/outcome values are explicit defaults, never inferred labels.
    expand_receipt_metadata restores each compact JSON exactly.
    """
    recent = [compact_receipt(r) for r in receipts[-3:]]
    defaults = {}
    if len(recent) >= 2:
        defaults = {key: recent[0][key] for key in RECEIPT_DEFAULT_KEYS
                    if all(key in row for row in recent)
                    and all(row[key] == recent[0][key] for row in recent[1:])}
    lines = []
    for index, row in enumerate(recent):
        compact = {k: v for k, v in row.items() if k not in defaults}
        if defaults and index == 0:
            compact["defaults"] = defaults
        lines.append("receipt " + json.dumps(compact, ensure_ascii=False,
                                            sort_keys=True, separators=(",", ":")))
    return lines


def expand_receipt_metadata(receipts: list[dict]) -> list[dict]:
    """Restore inherited metadata without mutating any encoded receipt.

    An explicit per-receipt value wins over the first receipt's defaults, so
    independent or conflicting metadata never becomes the shared value.
    """
    if not receipts:
        return []
    defaults = receipts[0].get("defaults", {})
    return [{**defaults, **{k: v for k, v in row.items() if k != "defaults"}}
            for row in receipts]


def serialize(
    instruction: str,
    entities: list[Entity],
    gripper_opening: float,
    held: str | None,
    receipts: list[dict],
    card: dict | None = None,
    view_axes: tuple[tuple, tuple] | None = None,
    *,
    choices: list[Candidate] | None = None,
    failure_counts: bool = False,
    recovery_status: dict | None = None,
) -> str:
    """Write planner state without simulator identifiers or goal predicates."""
    lines = [f"instruction {json.dumps(instruction, ensure_ascii=True)}"]
    for e in entities:
        xyz = json.dumps([round(x * 100, 2) for x in e.xyz], separators=(",", ":"))
        size = json.dumps(
            [round((hi - lo) * 100, 2) for lo, hi in zip(e.lower, e.upper)],
            separators=(",", ":"),
        )
        lines.append(
            f"e {e.id} name={json.dumps(e.name)} xyz_cm={xyz} size_cm={size} "
            f"visible={int(e.visible)} src={measurement_source(e)}"
            + (f" part_of={e.part_of} geometry={e.geometry}" if e.part_of else "")
        )
    if view_axes is None:
        relation_rows = relations(entities)
    else:
        right, front = view_axes
        lines.append(
            f"rel frame=agentview_planar right_world={list(right)} "
            f"front_world={list(front)} threshold_cm=2"
        )
        relation_rows = relations(entities, right_axis=right, front_axis=front)
    grouped: dict[tuple[str, str], list[str]] = {}
    for row in relation_rows:
        _, source, predicate, target = row.split()
        grouped.setdefault((source, predicate), []).append(target)
    lines.extend(
        f"rel {source} {predicate} {','.join(targets)}"
        for (source, predicate), targets in grouped.items()
    )
    lines.append(f"robot gripper_opening={gripper_opening:.4f} held={held or 'none'}")
    if recovery_status is not None:
        lines.append(f"recovery no_progress_steps={recovery_status['no_progress_steps']} "
                     f"reperceive_cooldown={recovery_status['reperceive_cooldown']}")
    lines.extend(receipt_lines(receipts))
    if failure_counts:
        # Every offered action still has a failure count. State the zero
        # default once rather than repeating the same evidence alongside
        # each action already present in the request's choice list.
        lines.append("candidate failures=count:type default=0:none")
        for action in choices or []:
            count, kind = recent_failures(action, receipts)
            recorded = (recovery_status or {}).get("action_failures", {}).get(action.text())
            if recorded and recorded["count"] > count:
                count, kind = recorded["count"], recorded["kind"]
            if (count, kind) != (0, "none"):
                lines.append(f"candidate {action.text()} failures={count}:{kind}")
        for key in (recovery_status or {}).get("blocked_actions", ()):
            recorded = recovery_status["action_failures"][key]
            lines.append(f"blocked {key} failures={recorded['count']}:{recorded['kind']} until=measured_change")
    if card is not None:
        lines.append(
            f"card step={card['step']}/{card['total']} next={json.dumps(card['next'])}"
        )
    return "\n".join(lines)


def recent_failures(action: Candidate, receipts: list[dict]) -> tuple[int, str]:
    """Count matching failed attempts in the last ten executed decisions."""
    count, kind = 0, "none"
    for receipt in receipts[-10:]:
        if receipt.get("card_action") != action.text() and any(
            receipt.get(key) != getattr(action, key)
            for key in ("tool", "object", "target", "mode")
        ):
            continue
        if receipt.get("error") or receipt.get("verification") == "execution_error":
            count += 1
            kind = "execution_error"
        elif receipt.get("executed") is False and receipt.get("stop") == "execution_interrupted":
            count += 1
            kind = "execution_interrupted"
        elif receipt.get("verification") == "failed" or any(
            receipt.get(key) is False for key in ("grasp_verified", "place_verified", "articulate_verified")
        ):
            count += 1
            kind = receipt.get("failure_reason") or "verification_failed"
        elif receipt.get("effect") == "no_effect":
            count += 1
            kind = "no_effect"
        elif receipt.get("verification") == "verified":
            count, kind = 0, "none"
    return count, kind


def prepare_request(
    tokenizer: Any, prepare_prompts: Any, context: str, choices: list[Candidate]
) -> tuple[dict, int]:
    """Admit the complete letter-readout prompt; never truncate state or choices."""
    if not 1 <= len(choices) <= 24:
        raise ValueError("v5 requires 1..24 choices")
    options = [c.text() for c in choices]
    keys = [f"C{i}" for i in range(len(options))]
    definition = {
        "action": {
            "type": "enum",
            "description": CHOICE_INSTRUCTION,
            "choices": keys,
            "choice_descriptions": dict(zip(keys, options)),
        }
    }
    prepared = prepare_prompts(tokenizer, context, definition, MAX_PROMPT_TOKENS)
    tokens = len(prepared.full_ids[0])
    if tokens > MAX_PROMPT_TOKENS:
        raise ValueError(
            f"complete request has {tokens} tokens > {MAX_PROMPT_TOKENS}"
        )
    return {
        "context": context,
        "instruction": CHOICE_INSTRUCTION,
        "options": options,
    }, tokens


def grasp_verified(before: Entity, after: Entity | None, opening: float,
                   *, minimum_opening: float = .005) -> bool:
    """Require gripper aperture and a measured 3 cm rise after the 5 cm trial."""
    return bool(
        after
        and after.visible
        and minimum_opening <= opening <= 0.07
        and after.xyz[2] - before.xyz[2] >= 0.03
    )


def place_verified(
    first: Entity | None,
    second: Entity | None,
    target: Entity,
    opening: float,
    eef_xyz: tuple[float, ...],
    interval_s: float,
    *,
    relation: str = "on",
) -> bool:
    """Require two stable measurements, release and withdrawal."""
    if first is None or second is None or not (first.visible and second.visible):
        return False
    if relation not in ("on", "in"):
        raise ValueError(f"unsupported placement relation: {relation}")
    vertical = all(
        target.lower[2] <= e.xyz[2] <= target.upper[2]
        if relation == "in" else e.xyz[2] > target.upper[2]
        for e in (first, second)
    )
    return bool(
        interval_s >= 0.3
        and opening >= 0.07
        and math.dist(first.xyz, second.xyz) <= 0.02
        and math.dist(eef_xyz, second.xyz) >= 0.05
        and all(
            target.lower[i] <= e.xyz[i] <= target.upper[i]
            for e in (first, second)
            for i in (0, 1)
        )
        and vertical
    )


def entity_record(e: Entity) -> dict:
    """Expose measurement provenance for offline audits, separately from text."""
    return {**asdict(e), "src": measurement_source(e), "extent": (
        e.geometry if e.geometry else "measured_anchor_region" if e.name.startswith("area ") else "visible_surface")}


def measurement_source(e: Entity) -> str:
    if not e.visible or (e.geometry and e.geometry.startswith("cached_perception")):
        return "perception_cached_shape_prior" if e.geometry and "shape_prior" in e.geometry else "perception_cached"
    return "perception_shape_prior" if e.geometry and "shape_prior" in e.geometry else "perception"
