"""Compare three registered drawer methods from complete explicit 4235 records."""

from collections import Counter, defaultdict
import hashlib
import importlib.util
import json
import math
from pathlib import Path


REMOTE_ROOT = "/public/home/sunyihan/rpent_libero_eval"
METHODS = ("native_original160", "stage_original160", "stage_reordered160")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")


def wilson(k, n):
    if not n:
        return None
    z = 1.959963984540054
    den = 1 + z * z / n
    centre = (k / n + z * z / (2 * n)) / den
    half = z * math.sqrt(k / n * (1 - k / n) / n + z * z / (4 * n * n)) / den
    return [max(0, centre - half), min(1, centre + half)]


def main():
    directory = Path(__file__).resolve().parent
    root = directory.parents[4]
    report_path = directory / "report.json"
    assert sha(report_path) == "f3392d5a78e9dcf7623e8601c33ff4ce37908aa4a545a62afbbf29490a838fd0"
    report = json.loads(report_path.read_text())
    assert report["complete"] and report["overall"]["recorded"] == 15
    helper_path = root / "results/harness_v5/skill549_live_CPU_20261006/20261006T142400Z/audit_completed_records.py"
    assert sha(helper_path) == "b29487fba4ef8ed265d05f877ac2f44bdd59d0ad50e177a710efa7def9a5709a"
    spec = importlib.util.spec_from_file_location("controls549", helper_path)
    helper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helper)
    rows, groups, pairs, public_refs = [], defaultdict(Counter), defaultdict(dict), []

    def public_file(ref, *, case, phase, role, source_step=None):
        if isinstance(ref, dict) and ref.get("path") and ref.get("sha256"):
            public_refs.append({"path": ref["path"], "sha256": ref["sha256"],
                                "case": case, "phase": phase, "role": role,
                                "source_step": ref.get("source_step", source_step),
                                "source": "recorded perception file"})

    def geometry(value, *, case, phase):
        if not isinstance(value, dict):
            return None
        for role in ("frame", "moving"):
            public_file(value.get(role), case=case, phase=phase, role=role,
                        source_step=value.get("source_step"))
        return {key: value.get(key) for key in ("frame", "moving", "basis", "anchor_parent",
                                               "anchor_part", "source_step", "source",
                                               "point_counts", "fusion_version", "views",
                                               "point_counts_by_camera", "reason")}

    def handle(value, *, case, phase):
        if not isinstance(value, dict):
            return None
        views = {}
        for camera, view in value.get("views", {}).items():
            public_file(view.get("cloud"), case=case, phase=phase, role="handle/" + camera,
                        source_step=value.get("source_step"))
            views[camera] = {key: view.get(key) for key in ("pose", "points", "width_m", "height_m", "reason")}
        return {"pose": value.get("pose"), "source_step": value.get("source_step"),
                "source": value.get("source"), "source_cameras": value.get("source_cameras"),
                "fusion_version": value.get("fusion_version"), "views": views,
                "reason": value.get("reason"), "centre_disagreement_m": value.get("centre_disagreement_m")}

    raw_refs = report["ledgers"] + report["infrastructure_ledgers"]
    for ref in raw_refs:
        path = root / ref["path"].removeprefix(REMOTE_ROOT + "/")
        assert sha(path) == ref["sha256"]
    for ref in report["ledgers"]:
        path = root / ref["path"].removeprefix(REMOTE_ROOT + "/")
        for line_no, line in enumerate(path.read_text().splitlines(), 1):
            row = json.loads(line)
            case, first = row["case"], row["first_attempt"]
            method = case["condition"]
            assert method in METHODS
            controls = helper.stage_controls(first)
            server = row["server_chunk_execution"]
            assert controls["vla_chunks"] == 160
            assert controls["vla_requested"] == controls["vla_executed"] == 800
            assert controls["vla_short_chunks"] == 0
            assert server["requested_controls"] == server["executed_controls"] == controls["vla_executed"]
            assert not server["native_success_stops_chunk"]
            assert not server["external_truncation"]
            assert not server["private_joint_or_predicate_used_for_control"]
            before, after = first["private_before"], first["private_after"]
            assert before["satisfied"] is False
            receipt = first["receipt"]
            public = receipt.get("articulate_verified")
            value = first.get("verification_measurements", {}).get("articulation", {})
            approach = receipt.get("fixture_handle_approach") or first.get("contact_evidence", {}).get("approach") or {}
            selected_entity = receipt.get("object")
            entity_before = next((e for e in first["public_before"].get("entities", []) if e["id"] == selected_entity), None)
            entity_after = next((e for e in first["public_after"].get("entities", []) if e["id"] == selected_entity), None)
            chunks = [m for m in first.get("motion_evidence", []) if m.get("name") == "vla_act_chunk"]
            expected_prompt = case["subtask_prompt"]
            assert len({m["instruction"] for m in chunks}) == 1
            assert chunks[0]["instruction"] == expected_prompt
            diagnostic = {
                "case": case["name"], "method": method, "episode": case["episode"],
                "pair_id": case["diagnostic_pair_id"], "state_sha256": case["state_sha256"],
                "captured_ledger": ref["path"], "line": line_no, "status": row["status"],
                "selected": first["selected"], "selected_entity_measured_before": entity_before,
                "selected_entity_measured_after": entity_after,
                "public_receipt_measurement": receipt.get("measurement"),
                "binding_evidence": first.get("binding_evidence"),
                "controls": controls, "server_control_accounting": server,
                "registered_prompt": expected_prompt, "literal_prompt_sha256": hashlib.sha256(expected_prompt.encode()).hexdigest(),
                "recorded_first_chunk_prompt": chunks[0]["instruction"],
                "first_chunk_eef": chunks[0].get("final_eef_pos"),
                "last_chunk_eef": chunks[-1].get("final_eef_pos"),
                "contact_evidence": first.get("contact_evidence"),
                "approach": {"ready_for_contact": approach.get("ready_for_contact"),
                             "target_xyz": approach.get("target_xyz"), "waypoints": approach.get("waypoints"),
                             "handle_before": handle(approach.get("before"), case=case["name"], phase="approach_before"),
                             "handle_wrist_refinement": handle(approach.get("after_wrist_refinement"), case=case["name"], phase="approach_after")},
                "body_endpoint": {"rule": value.get("verification_scope"), "measured_extension_cm": value.get("measured_extension_cm"),
                                  "reason": value.get("reason"),
                                  "before": geometry(value.get("before"), case=case["name"], phase="verification_before"),
                                  "after": geometry(value.get("after"), case=case["name"], phase="verification_after")},
                "private_before_label": before, "private_after_label": after,
                "native_success_latched_final": row.get("native_original_success_latched"),
                "runtime_verdict": public, "runtime_verification": receipt.get("verification"),
                "wall_s": row.get("case_wall_s", row.get("wall_s")),
                "classification": "newly_satisfied" if after["satisfied"] else "executed_endpoint_false",
            }
            rows.append(diagnostic)
            assert method not in pairs[case["diagnostic_pair_id"]]
            pairs[case["diagnostic_pair_id"]][method] = diagnostic
            group = groups[method]
            group["recorded"] += 1
            group["endpoint_true"] += after["satisfied"] is True
            group["endpoint_false"] += after["satisfied"] is False
            group["public_true"] += public is True
            group["public_false"] += public is False
            group["public_null"] += public is None
            group["TP"] += public is True and after["satisfied"] is True
            group["FN"] += public is False and after["satisfied"] is True
            group["TN"] += public is False and after["satisfied"] is False
            group["FP"] += public is True and after["satisfied"] is False
            for k, v in controls.items():
                group[k] += v
    pairing = []
    for pair_id, items in pairs.items():
        assert set(items) == set(METHODS)
        assert len({item["state_sha256"] for item in items.values()}) == 1
        assert items["native_original160"]["registered_prompt"] == items["stage_original160"]["registered_prompt"]
        assert items["stage_original160"]["approach"]["target_xyz"] == items["stage_reordered160"]["approach"]["target_xyz"]
        pairing.append({"pair_id": pair_id, "state_sha256": items[METHODS[0]]["state_sha256"],
                        "outcomes": {method: {"private_before": False,
                                               "private_after": item["private_after_label"]["satisfied"],
                                               "private_after_joint": item["private_after_label"].get("joint_qpos"),
                                               "public": item["runtime_verdict"],
                                               "measured_extension_cm": item["body_endpoint"]["measured_extension_cm"],
                                               "measurement_reason": item["body_endpoint"]["reason"]}
                                     for method, item in items.items()}})
    comparisons = []
    for a, b, factor in ((METHODS[0], METHODS[1], "scripted measured staging added; same literal prompt"),
                         (METHODS[1], METHODS[2], "literal original prompt reordered; same recorded staging target")):
        va = [items[a]["private_after_label"]["satisfied"] for items in pairs.values()]
        vb = [items[b]["private_after_label"]["satisfied"] for items in pairs.values()]
        comparisons.append({"method_a": a, "method_b": b, "factor": factor, "paired_n": len(va),
                            "a_only_success": sum(x and not y for x, y in zip(va, vb)),
                            "b_only_success": sum(y and not x for x, y in zip(va, vb)),
                            "success_difference_pp_a_minus_b": 100 * (sum(va) - sum(vb)) / len(va),
                            "scope": "5 visited selection states; no confirmation or population qualification claim"})
    result = {"job_id": 4235, "source": report["source"], "report_sha256": sha(report_path),
              "script_sha256": sha(Path(__file__)), "helper_sha256": sha(helper_path),
              "manifest": report["manifests"], "captured_raw_refs": raw_refs,
              "registered_cases": 15, "unique_raw_states": 5,
              "groups": {k: {**v, "physical_success_rate": v["endpoint_true"] / v["recorded"],
                               "physical_success_wilson95": wilson(v["endpoint_true"], v["recorded"])} for k, v in groups.items()},
              "paired_states": pairing, "paired_comparisons": comparisons, "records": rows,
              "private_truth_controlled_execution": False, "qualification_authorized": False,
              "new_physical_trials": 0, "new_training_rows": 0, "raw_or_gzip_staged": False}
    write_json(directory / "paired_control_and_measurement_audit.json", result)
    write_json(directory / "public_measurement_refs.json", {
        "job_id": 4235, "scope": "explicit file references recorded in public handle and body measurements only",
        "refs": public_refs, "count": len(public_refs), "new_physical_trials": 0})
    lines = ["# 4235 三方法 × 同5状态抽屉选择批", "",
             "15/15记录已齐，5片COMPLETED 0:0，最后结束 2026-10-06 15:10:30 UTC。原版 LIBERO-90 t6，init10–14，同5个raw状态配对；没有重跑确认批或改判。", "",
             "| 方法 | 私有端点新完成 | Wilson95 | 公共true / false / null | VLA controls |",
             "|---|---:|---:|---:|---:|"]
    for method in METHODS:
        group = groups[method]
        ci = wilson(group["endpoint_true"], group["recorded"])
        lines.append(f"| {method} | {group['endpoint_true']}/{group['recorded']} | {100*ci[0]:.2f}–{100*ci[1]:.2f}% | {group['public_true']} / {group['public_false']} / {group['public_null']} | {group['vla_executed']}/{group['vla_requested']} |")
    lines += ["", "原句为 `open the bottom drawer of the cabinet`；旧重排句为 `open the cabinet bottom drawer`。相同原句加脚本stage后5→2（3个a-only、0个b-only）；相同stage把原句重排后2→0（2个a-only、0个b-only）。这5例支持接近与语序都影响接触结果；不能推广成达到行业门槛。", "",
              "全部private-before=false。每例160完整chunks、800controls，三方法共12000/12000 VLA controls；短块0、无native或external截断、无private joint/predicate控制。非VLA接近/恢复计数另列在审计，不算VLA步数。", "",
              "公共验证器没有一次true：7个私有真端点中4次false、3次null（moving_face_or_static_frame_not_measured）；其余8次为TN。测量分母下recall0/4，全已知真值分母下一致率8/15；null保留。不得把私有成功覆盖公共回执。", "",
              "| init | native joint/公共延伸 | stage原句 joint/公共延伸 | stage重排 joint/公共延伸 |",
              "|---|---|---|---|"]
    for pair in pairing:
        cols = []
        for method in METHODS:
            item = pair["outcomes"][method]
            cols.append(f"{item['private_after_joint'][0][0]:.6f} m / {item['measured_extension_cm']} cm ({item['public']})")
        lines.append(f"| {pair['pair_id'].split('_s')[-1]} | " + " | ".join(cols) + " |")
    lines += ["", "native的4次公共false均将约16cm私有关节位移测成小于1cm的moving-face延伸；整体实体回执与独立几何端点证据均保存。疑似打开后moving-face关联到了原静态柜面，仍需在独立源码开发中定位，不调整当前结果阈值。", "",
              "源码 `/public/home/sunyihan/rpent_libero_eval/source_v5_pan556_20261006`，commit `d8b1d980603e6e0e8f7e14f9541c01f7686c7673`。source和manifest未改；原report SHA256 `f3392d5a78e9dcf7623e8601c33ff4ce37908aa4a545a62afbbf29490a838fd0`。", ""]
    (directory / "summary.md").write_text("\n".join(lines))
    print(json.dumps({"output": str(directory), "paired_audit_sha256": sha(directory / "paired_control_and_measurement_audit.json"),
                      "public_ref_count": len(public_refs), "groups": {k: dict(v) for k, v in groups.items()}}))


if __name__ == "__main__":
    main()
