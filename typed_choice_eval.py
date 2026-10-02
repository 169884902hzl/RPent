"""No-memory typed-choice evaluation over RPent's LIBERO toolkit.

The planner sees only view_env_state and segment/back_project results. The
toolkit owns simulator access, action execution, success checks, and video.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from robots.libero.serialization import serialize_request


def candidates(
    names: list[str], locations: dict, held: str | None,
    receipt: dict | None = None,
) -> list[dict]:
    """Enumerate tool arguments from visible names, never from BDDL goals."""
    names = sorted(set(names))
    # Perception already refreshes every visible object before each choice.
    # Re-offering read-only tools here lets a choice consume the budget without
    # changing the robot state or adding information.
    out = []
    if held is None:
        out += [{"tool": "pi0_pick", "object": name} for name in names]
    if held is not None:
        move_result = (receipt or {}).get("log", {}).get("result", {})
        arrived = (
            move_result.get("name") == "move_to"
            and float(move_result.get("final_dist_m", 1.0)) <= 0.015
        )
        if not arrived:
            out += [
                {"tool": "move_to", "object": held, "region": region, "height": height}
                for region in names
                if region != held and locations.get(region, {}).get("world_xyz") is not None
                for height in ("above", "drop")
            ]
        # Releasing without a measured destination is not a parameterized
        # placement and would discard the held object. Keep it out until at
        # least one observable region has a back-projected location.
        if any(loc.get("world_xyz") is not None for loc in locations.values()):
            out.append({"tool": "release", "object": held})
            out += [
                {"tool": "rotate_wrist", "object": held, "yaw": yaw}
                for yaw in (-1.57, 0.0, 1.57)
            ]
    out.append({"tool": "finish"})
    return out


def relative_relations(locations: dict) -> list[dict]:
    """Describe pairwise geometry using only measured back-projection points."""
    names = sorted(
        name for name, location in locations.items()
        if location.get("world_xyz") is not None
    )
    relations = []
    for left_index, first in enumerate(names):
        a = locations[first]["world_xyz"]
        for second in names[left_index + 1:]:
            b = locations[second]["world_xyz"]
            dx, dy, dz = (float(b[i]) - float(a[i]) for i in range(3))
            distance = (dx * dx + dy * dy + dz * dz) ** 0.5
            labels = []
            if abs(dx) >= 0.02:
                labels.append("right" if dx > 0 else "left")
            if abs(dy) >= 0.02:
                labels.append("front" if dy > 0 else "behind")
            if abs(dz) >= 0.02:
                labels.append("above" if dz > 0 else "below")
            relations.append({
                "from": first,
                "to": second,
                "relation": labels or ["near_same_height"],
                "distance_m": round(distance, 4),
            })
    return relations


def state_text(
    state: dict,
    locations: dict,
    relations: list[dict],
    held: str | None,
    receipt: dict | None,
    candidates: list[dict] | None = None,
) -> str:
    return serialize_request(
        state, locations, relations, held, receipt, candidates=candidates
    )


def human_name(name: str) -> str:
    """Convert an observation identifier to a text prompt for RPent tools."""
    return re.sub(r"\s+\d+$", "", name.replace("_", " ")).strip()


class ChoiceScorer:
    def __init__(self, provider: str, endpoint: str | None, *, memory_text: str | None = None,
                 goal_done_diagnostic: bool = False):
        self.provider = provider
        self.endpoint = endpoint
        self.memory_text = memory_text
        self.goal_done_diagnostic = goal_done_diagnostic
        if goal_done_diagnostic and provider not in ("systemone", "jev"):
            raise ValueError("goal_done diagnosis requires System One or official Jev")
        self.jev = None
        if provider == "jev" and endpoint is None:
            # Existing private client reads its own credential file. No key is
            # copied into RPent, the request log, or any result artifact.
            sys.path.insert(0, "/home/agilex/cobot_magic/mojuco")
            from jev_harness.providers import TypeSafeClient

            self.jev = TypeSafeClient()
        elif not endpoint:
            raise ValueError("local Qwen scoring needs --choice-endpoint")

    def score(self, context: str, instruction: str, options: list[str]) -> dict:
        if self.provider == "systemone" or (self.goal_done_diagnostic and self.endpoint):
            from robots.libero.v5_systemone import score
            return score(self.endpoint, context, instruction, options,
                         goal_done=self.goal_done_diagnostic)
        if self.provider == 'qwen27':
            from v5_qwen27_guided_choice import score
            return score(self.endpoint,context,instruction,options,memory_text=self.memory_text)
        if len(options) > 26:
            raise ValueError("choice stage exceeds C0..C25")
        if self.jev is not None:
            keys = [f"C{i}" for i in range(len(options))]
            from robots.libero.v5_systemone import questions
            question = questions(instruction, options, goal_done=self.goal_done_diagnostic)
            inference_started = time.perf_counter()
            reply = self.jev.ask(context, {}, question)
            inference_elapsed = time.perf_counter() - inference_started
            probabilities = reply["raw"]["answers"]["action"]["probabilities"]
            selected = int(reply["selected"]["action"][1:])
            result = {"selected": selected, "probabilities": probabilities,
                    "model": reply["provider"].get("actual_model"),
                    "model_inference_s": inference_elapsed, "http_round_trip_s": inference_elapsed}
            if self.goal_done_diagnostic:
                from robots.libero.v5_systemone import parse_answer
                result.update(parse_answer({**reply["raw"], "model": result["model"]},
                    len(options), goal_done=True, http_s=inference_elapsed))
            return result
        payload = json.dumps({"context": context, "instruction": instruction,
                              "options": options}, ensure_ascii=False).encode()
        request = Request(self.endpoint.rstrip("/") + "/score", data=payload,
                          headers={"Content-Type": "application/json"}, method="POST")
        try:
            with urlopen(request, timeout=180) as response:
                result = json.load(response)
        except HTTPError as error:
            detail = error.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"choice service HTTP {error.code}: {detail}") from error
        if "error" in result:
            raise RuntimeError(result["error"])
        return result


def choose(scorer: ChoiceScorer, context: str, actions: list[dict]) -> tuple[dict, list[dict]]:
    remaining = actions
    stages = []
    for field in ("tool", "object", "region", "height", "yaw"):
        values = sorted({str(a[field]) for a in remaining if field in a})
        if len(values) <= 1:
            continue
        if len(values) > 26:
            raise ValueError(f"{field}: {len(values)} options exceed choice alphabet")
        descriptions = [f"{field}={value}" for value in values]
        answer = scorer.score(
            context,
            f"Select the next tool and its arguments for the instruction using measured observations and the last receipt. Current field: {field}.",
            descriptions,
        )
        if answer.get("model_inference_s") is None:
            raise ValueError("choice service did not report model_inference_s")
        index = int(answer["selected"])
        if not 0 <= index < len(values):
            raise ValueError(f"invalid {field} choice index: {index}")
        selected = values[index]
        remaining = [a for a in remaining if str(a.get(field)) == selected]
        stages.append({"field": field, "options": values, "selected": selected,
                       "probabilities": answer["probabilities"],
                       "model": answer.get("model"),
                       "model_inference_s": answer.get("model_inference_s")})
        if len(remaining) == 1:
            break
    if len(remaining) != 1:
        raise ValueError(f"ambiguous choice: {remaining}")
    return remaining[0], stages


def execute(toolkit, action: dict, locations: dict, state: dict) -> dict:
    tool = action["tool"]
    if tool == "segment":
        return toolkit.execute_tool(tool, {"prompt": human_name(action["object"])}).result
    if tool == "back_project":
        box = locations[action["object"]]["box"]
        row = round((box[1] + box[3]) / 2)
        col = round((box[0] + box[2]) / 2)
        return toolkit.execute_tool(tool, {"row": row, "col": col}).result
    if tool == "pi0_pick":
        return toolkit.execute_tool(
            tool, {"prompt": f"pick up the {human_name(action['object'])}"}
        ).result
    if tool == "move_to":
        xyz = list(locations[action["region"]]["world_xyz"])
        xyz[2] += 0.20 if action["height"] == "above" else 0.10
        current = state["state"]["robot0_eef_pos"]
        # RPent documents a 30 cm XY limit for one OSC move_to call.
        start = list(current)
        for _ in range(5):
            distance = ((xyz[0] - start[0]) ** 2 + (xyz[1] - start[1]) ** 2) ** 0.5
            if distance <= 0.27:
                break
            fraction = min(0.5, 0.25 / distance)
            mid = [start[0] + (xyz[0] - start[0]) * fraction,
                   start[1] + (xyz[1] - start[1]) * fraction,
                   max(start[2], xyz[2], 0.20)]
            result = toolkit.execute_tool(tool, {"xyz": mid, "gripper": 1}).result
            if result.get("error") or result.get("terminated") or result.get("truncated"):
                return result
            start = result["state"]["robot0_eef_pos"]
        return toolkit.execute_tool(tool, {"xyz": xyz, "gripper": 1}).result
    if tool == "rotate_wrist":
        return toolkit.execute_tool(tool, {"target_yaw": action["yaw"]}).result
    if tool == "release":
        return toolkit.execute_tool(tool, {}).result
    return toolkit.execute_tool("finish", {"status": "success", "summary": "Planner finished"}).result


def perceive(toolkit, names: list[str]) -> tuple[dict, list[dict]]:
    """Refresh all visible object measurements through RPent perception tools."""
    locations = {}
    for name in sorted(set(names)):
        segmented = toolkit.execute_tool(
            "segment", {"prompt": human_name(name)}
        ).result
        entry = {
            "segment": {
                key: value for key, value in segmented.items()
                if key not in ("_image_bytes", "_image_cam_bytes", "_image_wrist_bytes")
            },
            "world_xyz": None,
            "box": segmented.get("box"),
            "score": segmented.get("score"),
            "source_step": segmented.get("step"),
        }
        box = segmented.get("box")
        if isinstance(box, (list, tuple)) and len(box) == 4:
            row = round((float(box[1]) + float(box[3])) / 2)
            col = round((float(box[0]) + float(box[2])) / 2)
            projected = toolkit.execute_tool(
                "back_project", {"row": row, "col": col}
            ).result
            entry["back_project"] = {
                key: value for key, value in projected.items()
                if key not in ("_image_bytes", "_image_cam_bytes", "_image_wrist_bytes")
            }
            entry["world_xyz"] = projected.get("world_xyz")
            entry["projection_pixel"] = [row, col]
        locations[name] = entry
    return locations, relative_relations(locations)


def run_episode(args: argparse.Namespace) -> dict:
    from robots.libero.robot_spec import _init_runtime
    from robots.libero.toolkit import LiberoToolkit
    from rpent.dashboard.events import NullDashboardEventSink
    from rpent.memory import MemoryManager

    output = Path(args.output_dir)
    output.mkdir(parents=True, exist_ok=True)
    events = NullDashboardEventSink()
    runtime_args = argparse.Namespace(
        suite=args.suite, task=args.task, seed=args.seed,
        max_episode_steps=args.max_episode_steps, libero_type="pro",
        env_endpoint=args.env_endpoint, vla_endpoint=args.vla_endpoint,
        sam3_endpoint=args.sam3_endpoint, molmo_endpoint=None,
        cuda_device=None, planner="typed_choice", collect_flywheel_data=False,
    )
    daemons, runtime = _init_runtime(runtime_args, output, events, None)
    toolkit = None
    trace = output / "choices.jsonl"
    try:
        # The required manager points at a nonexistent, per-run directory.
        # No memory APIs are called and no RPent corpus is loaded.
        toolkit = LiberoToolkit(
            runtime_kwargs=runtime, dashboard_events=events,
            memory=MemoryManager(output / "empty_memory", memory_access="read_only"),
            state_output_dir=output,
        )
        toolkit.primitives.record_frame(toolkit.primitives._last_obs)
        scorer = ChoiceScorer(args.provider, args.choice_endpoint)
        locations: dict = {}
        relations: list[dict] = []
        held = None
        receipt = None
        segment_attempted: set[str] = set()
        pi0_pick_calls = 0
        pi0_pick_segmented_before = 0
        with trace.open("w") as log:
            decisions = 0
            for decision in range(args.max_decisions):
                decisions += 1
                decision_started = time.perf_counter()
                observe_started = time.perf_counter()
                state = toolkit.execute_tool("view_env_state", {}).result
                observe_elapsed = time.perf_counter() - observe_started
                if state["terminated"] or state["truncated"]:
                    break
                names = state["state"]["object_names"]
                perception_started = time.perf_counter()
                locations, relations = perceive(toolkit, names)
                segment_attempted.update(names)
                perception_elapsed = time.perf_counter() - perception_started
                actions = candidates(names, locations, held, receipt)
                context = state_text(
                    state, locations, relations, held, receipt, candidates=actions
                )
                choice_started = time.perf_counter()
                action, stages = choose(scorer, context, actions)
                choice_elapsed = time.perf_counter() - choice_started
                model_inference_elapsed = sum(
                    float(stage["model_inference_s"])
                    for stage in stages if stage.get("model_inference_s") is not None
                )
                was_segmented_before_pick = (
                    action["tool"] == "pi0_pick"
                    and action.get("object") in segment_attempted
                )
                if action["tool"] == "pi0_pick":
                    pi0_pick_calls += 1
                    pi0_pick_segmented_before += int(was_segmented_before_pick)
                action_started = time.perf_counter()
                result = execute(toolkit, action, locations, state)
                action_elapsed = time.perf_counter() - action_started
                receipt = {key: val for key, val in result.items()
                           if key not in ("_image_bytes", "_image_cam_bytes", "_image_wrist_bytes")}
                if action["tool"] == "segment":
                    locations[action["object"]] = {
                        "world_xyz": result.get("world_xyz"),
                        "box": result.get("box"),
                        "score": result.get("score"),
                        "source_step": result.get("step"),
                    }
                if action["tool"] == "pi0_pick" and result.get("log", {}).get("result", {}).get("success"):
                    held = action["object"]
                if action["tool"] == "release":
                    held = None
                post_perception_started = time.perf_counter()
                post_state = toolkit.execute_tool("view_env_state", {}).result
                if not post_state["terminated"] and not post_state["truncated"]:
                    locations, relations = perceive(
                        toolkit, post_state["state"]["object_names"]
                    )
                post_perception_elapsed = time.perf_counter() - post_perception_started
                total_elapsed = time.perf_counter() - decision_started
                record = {"decision": decision, "state": context, "candidates": actions,
                          "action": action, "stages": stages, "receipt": receipt,
                          "official_success": toolkit.solved(),
                          "perception": locations,
                          "measured_relative_relations": relations,
                          "pi0_pick_segmented_before": was_segmented_before_pick,
                          "timing_s": {
                              "observe": round(observe_elapsed, 4),
                              "pre_action_perception": round(perception_elapsed, 4),
                              "choice": round(choice_elapsed, 4),
                              "model_inference": round(model_inference_elapsed, 4),
                              "action": round(action_elapsed, 4),
                              "post_action_perception": round(post_perception_elapsed, 4),
                              "decision_total": round(total_elapsed, 4),
                          }}
                log.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
                log.flush()
                if action["tool"] == "finish" or toolkit.solved() or result.get("truncated"):
                    break
        return {"suite": args.suite, "task": args.task, "seed": args.seed,
                "provider": args.provider, "official_success": toolkit.solved(),
                "decisions": decisions, "max_decisions": args.max_decisions,
                "pi0_pick_calls": pi0_pick_calls,
                "pi0_pick_segmented_before_count": pi0_pick_segmented_before,
                "pi0_pick_segmented_before_all": (
                    pi0_pick_calls == 0 or pi0_pick_segmented_before == pi0_pick_calls
                ),
                "trace": str(trace),
                "video": str(output / "episode.mp4")}
    finally:
        if toolkit is not None:
            toolkit.close()
        for daemon in reversed(daemons):
            daemon.stop()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--suite", choices=("libero_spatial_swap", "libero_object_swap"), required=True)
    parser.add_argument("--task", type=int, required=True)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--provider", choices=("dagger2323", "qwen4b", "jev"), required=True)
    parser.add_argument("--choice-endpoint")
    parser.add_argument("--env-endpoint")
    parser.add_argument("--vla-endpoint")
    parser.add_argument("--sam3-endpoint")
    parser.add_argument("--max-episode-steps", type=int, default=10000)
    parser.add_argument("--max-decisions", type=int, default=15)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()
    result = run_episode(args)
    path = Path(args.output_dir) / "result.json"
    path.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result))


if __name__ == "__main__":
    main()
