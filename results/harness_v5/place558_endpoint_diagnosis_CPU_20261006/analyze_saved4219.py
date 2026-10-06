"""Read saved 4219 placement evidence; replay only its pure visual verifier."""

import __future__
import ast
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
from types import SimpleNamespace


REMOTE_ROOT = "/public/home/sunyihan/rpent_libero_eval"
REPORT_REL = "results/harness_v5/place557_monitor_CPU_20261006/20261006T145504Z/job4219/report.json"
REPORT_SHA = "3aa5f85715f4a5ee0732d80f8666c063a3440ad83b250e9a5a83d8873c277247"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")


def verifier_functions(directory):
    """Use exactly copied SOURCE553 pure functions; do not import live runtime."""
    namespace = {"math": math, "Entity": SimpleNamespace}
    wanted = {
        "v5_state.py": {"place_verified"},
        "v5_verification.py": {"strict_place_verified", "strict_place_verified_v2",
                               "strict_place_verified_v3", "strict_place_verified_v4",
                               "strict_place_verified_v5", "strict_place_verified_v6"},
    }
    for filename, names in wanted.items():
        tree = ast.parse((directory / "preparation" / filename).read_text())
        nodes = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in names]
        assert {node.name for node in nodes} == names
        exec(compile(ast.Module(body=nodes, type_ignores=[]), filename, "exec",
                     flags=__future__.annotations.compiler_flag), namespace)
    return namespace["strict_place_verified_v6"]


def verification_flags(value):
    first, second, target = (value.get(key) for key in ("first", "second", "target"))
    fresh = bool(first and second and first["visible"] and second["visible"])
    result = {"two_visible_frames": fresh,
              "distinct_source_step": bool(first and second and first["source_step"] != second["source_step"]),
              "opening_ge_7cm": value["opening"] >= .07,
              "interval_ge_300ms": value["interval_s"] >= .3,
              "target_cache_geometry": target.get("geometry"),
              "target_source_step": target.get("source_step")}
    if not first or not second:
        return result
    lo, hi = target["lower"], target["upper"]
    overlaps = []
    for entity in (first, second):
        area = math.prod(max(entity["upper"][i] - entity["lower"][i], 1e-6) for i in (0, 1))
        overlap = math.prod(max(0, min(entity["upper"][i], hi[i]) - max(entity["lower"][i], lo[i])) for i in (0, 1))
        overlaps.append(overlap / area)
    mode = value["relation"]
    result.update(
        centre_stability_m=math.dist(first["xyz"], second["xyz"]),
        centre_stability_le_2cm=math.dist(first["xyz"], second["xyz"]) <= .02,
        eef_object_distance_m=math.dist(value["eef_xyz"], second["xyz"]),
        eef_withdrawal_ge_5cm=math.dist(value["eef_xyz"], second["xyz"]) >= .05,
        centres_inside_target_xy=all(lo[i] <= entity["xyz"][i] <= hi[i] for entity in (first, second) for i in (0, 1)),
        vertical_centres_in_target=all(lo[2] <= entity["xyz"][2] <= hi[2] if mode == "in" else entity["xyz"][2] > hi[2] for entity in (first, second)),
        footprint_overlap=overlaps,
        minimum_footprint_overlap=.90 if mode == "on" else .85,
        footprint_gate=all(overlap >= (.90 if mode == "on" else .85) for overlap in overlaps),
        object_bottom_minus_target_top_m=[entity["lower"][2] - hi[2] for entity in (first, second)],
        on_support_gap_le_1cm=all(abs(entity["lower"][2] - hi[2]) <= .01 for entity in (first, second)),
        in_bottom_above_target_lower_minus_1cm=all(entity["lower"][2] >= lo[2] - .01 for entity in (first, second)),
        visible_surface_heights_m=[entity["upper"][2] - entity["lower"][2] for entity in (first, second)],
    )
    return result


def main():
    directory = Path(__file__).resolve().parent
    root = directory.parents[2]
    report_path = root / REPORT_REL
    assert sha(report_path) == REPORT_SHA
    report = json.loads(report_path.read_text())
    verifier = verifier_functions(directory)
    runtime_path = directory / "preparation/v5_runtime.py"
    assert sha(runtime_path) == "bc5001949752ba737e941d16f1244c153d61a6713879bf84d0dca4f969314dd5"
    sources = [{"path": report["source"]["snapshot"] + "/robots/libero/" + name,
                "captured_copy": REMOTE_ROOT + "/" + str((directory / "preparation" / name).relative_to(root)),
                "sha256": sha(directory / "preparation" / name)}
               for name in ("v5_state.py", "v5_verification.py", "v5_runtime.py")]
    records, fn_categories, null_categories, physical_categories = [], Counter(), Counter(), Counter()
    for ref in report["ledgers"]:
        path = root / ref["path"].removeprefix(REMOTE_ROOT + "/")
        assert sha(path) == ref["sha256"]
        for line_number, line in enumerate(path.read_text().splitlines(), 1):
            row = json.loads(line)
            first = row.get("first_attempt") or {}
            motions = first.get("motion_evidence", [])
            if sum(m.get("executed_action_count", m.get("steps_used", 0)) for m in motions) == 0:
                continue
            value = first["verification_measurements"]
            arguments = [SimpleNamespace(**value[key]) if value[key] else None for key in ("first", "second", "target")]
            recomputed = verifier(*arguments, value["opening"], tuple(value["eef_xyz"]), value["interval_s"], relation=value["relation"])
            saved = first["receipt"]["place_verified"]
            assert saved is recomputed, row["case"]["name"]
            private_before = first["private_before"]["satisfied"]
            private_after = first["private_after"]["satisfied"]
            flags = verification_flags(value)
            categories = []
            fn_category = None
            if private_after is True and saved is False:
                if not flags["opening_ge_7cm"]:
                    fn_category = "endpoint_empty_gripper_closed_release_history_not_checked"
                elif not flags["vertical_centres_in_target"]:
                    fn_category = "centre_outside_cached_drawer_shell_z_range"
                elif not flags["footprint_gate"]:
                    fn_category = "measured_AABB_footprint_below_required_overlap"
                else:
                    fn_category = "other_saved_rejection"
                fn_categories[fn_category] += 1
                categories.append("FN:" + fn_category)
            if saved is None:
                null_category = "two_frame_object_occluded_cached_same_step" if not flags["two_visible_frames"] else "other_unknown"
                null_categories[null_category] += 1
                categories.append("null:" + null_category)
            last_setup = row["setup"][-1]
            setup_truth = last_setup.get("private_hold_truth_v2", {}).get("success")
            if private_after is False:
                if setup_truth is not True:
                    physical_category = "setup_not_true_sustained_hold"
                elif row["case"]["condition"] == "current160":
                    physical_category = "servo_waypoints_reached_bowl_returned_to_table_carry_loss_not_resolved"
                else:
                    physical_category = "true_hold_VLA800_endpoint_bowl_below_target_no_support"
                physical_categories[physical_category] += 1
                categories.append("physical_failure:" + physical_category)
            moves = [{key: motion.get(key) for key in ("name", "target_xyz", "final_eef_pos",
                                                      "final_dist_m", "steps_used", "gripper_command")}
                     for motion in motions if motion.get("name") == "move_to"]
            policy = [motion for motion in motions if motion.get("name") == "vla_act_chunk"]
            record = {
                "case": row["case"]["name"], "episode": row["case"]["episode"],
                "method": row["case"]["condition"], "mode": row["case"]["mode"],
                "raw_state_sha256": row["case"]["state_sha256"],
                "captured_ledger": ref["path"], "ledger_sha256": ref["sha256"], "line": line_number,
                "private_before_label": private_before, "private_after_label": private_after,
                "setup_all_current_support_v2_label": setup_truth,
                "runtime_verdict_saved": saved, "runtime_verdict_recomputed": recomputed,
                "runtime_verification_saved": first["receipt"].get("verification"),
                "saved_verification_reason": first["receipt"].get("verification_reason"),
                "public_verification_measurements": value, "rejection_flags": flags,
                "public_receipt_measurements": first["receipt"].get("measurement"),
                "public_robot_before": first["public_before"]["robot"],
                "public_robot_after": first["public_after"]["robot"],
                "held_after_metadata": first.get("held_after"),
                "policy_chunks": len(policy),
                "policy_controls_requested": sum(m.get("requested_action_count", 0) for m in policy),
                "policy_controls_executed": sum(m.get("executed_action_count", 0) for m in policy),
                "policy_prompt": policy[0].get("instruction") if policy else None,
                "compact_servo_waypoints": moves,
                "maximum_servo_final_residual_m": max((motion["final_dist_m"] for motion in moves), default=None),
                "categories": categories,
                "scope": "saved evidence only; private labels used for stratification, not controlling actions or rejudging results",
            }
            records.append(record)
    assert len(records) == 31
    assert sum(fn_categories.values()) == 9
    assert sum(null_categories.values()) == 5
    assert sum(physical_categories.values()) == 7
    result = {
        "job_id": 4219, "source": report["source"], "source_files": sources,
        "source_report": {"path": REMOTE_ROOT + "/" + REPORT_REL, "sha256": REPORT_SHA},
        "input_manifest": report["manifests"], "captured_raw_refs": report["ledgers"],
        "pure_frozen_verifier_recomputed": 31, "exact_saved_verdict_matches": 31,
        "physical_endpoint_failure_categories": dict(physical_categories),
        "runtime_FN_categories": dict(fn_categories), "runtime_null_categories": dict(null_categories),
        "records": records,
        "code_findings": [
            {"file": sources[2]["path"], "lines": [3005, 3006],
             "finding": "execute_subtask writes unknown verdict without placement_unknown_reason; ordinary place writes it at 2826-2828"},
            {"file": sources[0]["path"], "lines": [535, 545],
             "finding": "base verifier uses endpoint gripper opening as release condition, not recorded release history"},
            {"file": sources[1]["path"], "lines": [30, 49],
             "finding": "strict on=.90/in=.85 AABB footprint condition rejects 5 native-true stable/released measurements"},
        ],
        "next_development_hypotheses": [
            "Record visible held object after each carrying waypoint; 2 true-setup current failures reach servo targets but end with bowl on table, exact carry-loss time is not measurable from these records.",
            "Keep setup hold quality separate from placement denominator; 4/7 endpoint failures began without sustained hold by v2 private diagnostic label.",
            "For missing post-placement bowl measurement, reacquire both views or report explicit missing-evidence reason; do not certify using stale cached bowl.",
            "For full-task VLA, release verification should retain observed opening/held history; final empty-hand closure alone is insufficient evidence of placement failure.",
            "Measure support contact/containment geometry and centre placement accuracy instead of lowering overlap or shell-z thresholds on these visited selection states.",
        ],
        "source_or_runtime_modified": False, "qualification_authorized": False,
        "new_physical_trials": 0, "new_training_rows": 0,
    }
    write_json(directory / "diagnosis.json", result)
    lines = ["# 4219 放置端点与公共验证器独立诊断", "",
             "只读40个已保存选择回合；31个已执行首次动作的冻结 strict_place/6 CPU复算与原判定31/31一致。没有物理重放、改判或准入。", "",
             "7个on物理端点失败：4个来自准备抓持v2真值为false；真准备后的失败只有3个（current t10 init0/3、vla t25 init1）。两个current真准备失败的servo均到达既定waypoint，最终碗却测在桌面；当前公共记录无法定位掉落发生在哪一段，不能归成servo未达。vla真准备失败执行了800controls，最终碗低于目标柜顶且xy偏离。", "",
             "9次公共FN的互斥原因：AABB footprint门5（on3/in2）、缓存drawer壳z范围不符2、完整VLA结束后空手夹爪关闭2。5个null均为被遮挡物体的同一步缓存两帧；4个私有真、1个私有假。", "",
             "| case | 原私有端点 | 原公共判定 | 证据类别 |",
             "|---|---|---|---|"]
    for record in records:
        if record["categories"]:
            lines.append(f"| {record['case']} | {record['private_after_label']} | {record['runtime_verdict_saved']} | {'; '.join(record['categories'])} |")
    lines += ["", "两例空手关闭FN的EEF距目标碗55–58cm，碗实测稳定在柜顶；末端开度只有1.44/2.70cm，held元数据仍未清。问题是缺释放/持物历史，不建议把开度阈值直接放宽。", "",
              "三个on footprint FN overlap约0.690–0.780，两个in约0.796–0.799；中心、稳定、开夹、撤离均通过。on的下沿与柜顶差约0.6–0.9cm。应检查放置中心与可见表面AABB的支持几何，不能凭私有成功直接降低阈值。两个in z拒绝均用source_step=0的drawer可见壳界，未证明内腔体积；完整逐例范围与薄片测量保存在diagnosis.json。", "",
              "execute_subtask (SOURCE553 v5_runtime.py:3005)没有写placement_unknown_reason，普通place (:2826)会写；因此五个null的原日志缺具体缺测原因。这里新增独立诊断解释，不覆盖原回执。", "",
              "源码SHA与原report/raw路径逐项写入manifest；runtime和已完成作业未动。根因能被记录直接证明的部分与下一轮开发假设分开。", ""]
    (directory / "summary.md").write_text("\n".join(lines))
    relative = str(directory.relative_to(root))
    files = [{"path": REMOTE_ROOT + "/" + relative + "/" + filename,
              "sha256": sha(directory / filename), "size_bytes": (directory / filename).stat().st_size}
             for filename in ("analyze_saved4219.py", "diagnosis.json", "summary.md")]
    write_json(directory / "manifest.json", {"job_id": 4219, "files": files,
                                              "source_files": sources, "source_report": result["source_report"],
                                              "captured_raw_refs": report["ledgers"],
                                              "runtime_modified": False, "new_physical_trials": 0,
                                              "new_training_rows": 0, "qualification_authorized": False})
    print(json.dumps({"directory": str(directory), "diagnosis_sha256": sha(directory / "diagnosis.json"),
                      "manifest_sha256": sha(directory / "manifest.json"), "FN": dict(fn_categories),
                      "null": dict(null_categories), "physical_failures": dict(physical_categories)}))


if __name__ == "__main__":
    main()
