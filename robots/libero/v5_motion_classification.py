"""Summarize measured servo progress and private contact evidence."""

import math


def classify_move(move, choice):
    tail = move.get("last_10_steps", [])
    positions = [row["eef_pos"] for row in tail] + [move["final_eef_pos"]]
    displacements = [math.dist(a, b) for a, b in zip(positions, positions[1:])]
    progress = tail[0]["dist_to_target_m"] - move["final_dist_m"] if tail else None
    private = move.get("final_contact_and_joints") or {}
    arm_contacts = [c for c in private.get("contacts", [])
                    if any(any(word in (c.get(key) or "").lower()
                               for word in ("robot", "gripper", "finger"))
                           for key in ("geom1", "geom2"))]
    limits = [j for j in private.get("joints", [])
              if j["limit_margin_rad"] is not None and j["limit_margin_rad"] < .03]
    target = move["target_xyz"]
    inside = [e["id"] for e in choice.get("measurements", []) if e["visible"]
              and all(e["lower"][i] <= target[i] <= e["upper"][i] for i in range(3))]
    mode = choice["receipt"].get("retry_staging", choice["receipt"].get("mode"))
    if move["final_dist_m"] <= .02:
        category = "reached"
    elif inside:
        category = "target_inside_measured_entity"
    elif progress is not None and progress > .005:
        category = "step_budget_exhausted_still_approaching"
    elif arm_contacts or limits:
        category = "stalled_contact_or_joint_limit"
    else:
        category = "stalled_without_observed_contact_or_limit"
    return {"classification": category, "mode": mode,
            "decision": choice["decision"], "selected": choice["selected"],
            "start_eef_pos": move.get("start_eef_pos"), "target_xyz": target,
            "final_eef_pos": move["final_eef_pos"], "final_dist_m": move["final_dist_m"],
            "actions_used": move.get("actions_used"), "steps_used": move["steps_used"],
            "last_10_displacements_m": displacements, "last_10_distance_progress_m": progress,
            "robot_contacts": arm_contacts, "near_joint_limits": limits,
            "target_inside_measured_entities": inside,
            "yaw_in_prefix": any(m.get("name") == "rotate_wrist"
                                 for m in choice.get("motion_evidence", [])),
            "workspace_or_yaw_causality": "requires paired control; not inferred from residual alone"}
