"""Original-only passive action labels. No label is returned to the planner."""
import argparse
import json
import os
from pathlib import Path

from robots.libero.v5_env_server import make_v5_env
from robots.libero.v5_oracle_server import OriginalOracleFacade, ORIGINAL_SUITES
from robots.libero.v5_oracle_policy import _kind
from robots.libero.v5_runtime import category
from robots.libero.v5_grasp_truth import grasp_trace_summary_v2


def match_source(measurement, objects):
    if measurement is None:
        return None, {"reason": "no_public_source_measurement"}
    kind = category(measurement["name"])
    candidates = []
    for symbol, item in objects.items():
        if _kind(symbol) == kind:
            distance = sum((float(x) - float(y)) ** 2 for x, y in zip(measurement["xyz"], item["xyz"])) ** .5
            candidates.append((distance, symbol))
    candidates.sort()
    if not candidates or candidates[0][0] > .10:
        return None, {"reason": "no_nearby_category_match", "matches": candidates}
    if len(candidates) > 1 and candidates[1][0] - candidates[0][0] < .04:
        return None, {"reason": "private_label_binding_ambiguous", "matches": candidates}
    return candidates[0][1], {"reason": "private_nearest_category_match", "matches": candidates,
                              "used_for_action_selection": False}


def matching_goals(goals, action, symbol, target):
    mode = {"turn_on": "turnon", "turn_off": "turnoff"}.get(action.get("mode"), action.get("mode"))
    matches = []
    for index, goal in enumerate(goals):
        if len(goal) < 2 or goal[0] != mode or symbol != goal[1]:
            continue
        if len(goal) == 2 and target is None:
            matches.append(index)
        elif len(goal) == 3 and target is not None:
            text = target["name"].lower()
            kind = next((k for k in ("cabinet", "drawer", "microwave", "stove", "rack") if k in text), category(text))
            if _kind(goal[2]) != kind:
                continue
            # Never silently score another named furniture compartment.
            if any(word in text and word not in goal[2] for word in ("top", "bottom", "middle")):
                continue
            matches.append(index)
    return matches


class PassiveLabels(OriginalOracleFacade):
    def __init__(self, env, *, meta, label_path):
        self.label_path = Path(label_path)
        self.label_path.parent.mkdir(parents=True, exist_ok=True)
        self.active = None
        self.references = {}
        super().__init__(env, meta=meta)

    def _register_rpc(self):
        super()._register_rpc()
        self._rpc.update({"diagnostic.action_begin": self.begin, "diagnostic.action_end": self.end})

    def begin(self, sequence, action, source, target):
        objects = self.grasp_contacts()["objects"]
        symbol, binding = match_source(source, objects)
        before = self.goal_status()
        self.active = {"sequence": sequence, "action": action, "source": source, "target": target,
                       "symbol": symbol, "binding": binding, "before": before, "samples": []}
        if symbol and action["tool"] in ("grasp", "regrasp_restage"):
            if symbol not in self.references:
                self.references[symbol] = self.grasp_reference(symbol)
            self.active["samples"].append(self.grasp_reference(symbol))
        return {"logged": True}  # Private values stay entirely in the sidecar.

    def step(self, action):
        result = super().step(action)
        current = self.active
        if current and current["symbol"] and current["action"]["tool"] in ("grasp", "regrasp_restage"):
            current["samples"].append(self.grasp_reference(current["symbol"]))
        return result

    def end(self):
        item, self.active = self.active, None
        if item is None:
            raise ValueError("no registered pre-action label window")
        after = self.goal_status()
        action = item["action"]
        label, reason, evidence = None, "no_registered_physical_label_for_tool", None
        if item["symbol"] and action["tool"] in ("grasp", "regrasp_restage"):
            evidence = grasp_trace_summary_v2(self.references[item["symbol"]], item["samples"])
            label = evidence["true_sustained_grasp_at_end"]
            reason = "exclusive_gripper_support_3cm_clearance_sustained_0.5s_passive_history"
        elif item["symbol"] and action["tool"] in ("place", "adjust_place", "articulate", "vla_subtask"):
            matches = matching_goals(after["goals"], action, item["symbol"], item["target"])
            if len(matches) == 1:
                label = bool(after["satisfied"][matches[0]])
                reason = "unique_selected_original_predicate_after_action"
            else:
                reason = "no_unique_selected_original_predicate"
            evidence = {"matching_goal_indices": matches, "status": after}
        elif action["tool"] == "finish":
            label, reason = after["done"], "official_original_all_goal_predicates"
        row = {**item, "after": after, "simulation_truth": label, "label_rule": reason,
               "private_evidence": evidence, "judge": "simulation_diagnostic_only",
               "diagnostic_control_steps": 0, "may_train": False,
               "private_values_returned_to_planner": False}
        with self.label_path.open("a") as handle:
            handle.write(json.dumps(row) + "\n")
        return {"logged": True}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--suite", choices=sorted(ORIGINAL_SUITES), required=True)
    p.add_argument("--task", type=int, required=True)
    p.add_argument("--seed", type=int, required=True)
    p.add_argument("--max-episode-steps", type=int, required=True)
    p.add_argument("--port", type=int, required=True)
    p.add_argument("--parent-watch", action="store_true")
    p.add_argument("--deterministic-reset-v1", action="store_true")
    p.add_argument("--motion-trace-v1", action="store_true")
    p.add_argument("--private-label-path", type=Path, required=True)
    a = p.parse_args()
    if os.environ.get("LIBERO_TYPE") != "standard" or not 0 <= a.task < 10:
        p.error("only the 40 original tasks are allowed")
    env = make_v5_env(a.task, a.seed, a.suite, a.max_episode_steps, branch_state=True,
                      deterministic_reset_v1=a.deterministic_reset_v1, motion_trace_v1=a.motion_trace_v1)
    PassiveLabels(env, meta={"suite": a.suite, "task": a.task, "seed": a.seed,
                            "max_episode_steps": a.max_episode_steps}, label_path=a.private_label_path).serve(
                                transport="http", host="127.0.0.1", port=a.port, parent_watch=a.parent_watch)


if __name__ == "__main__":
    main()
