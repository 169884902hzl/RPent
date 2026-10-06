"""Package completed 4219 audits from explicit references; no physical execution."""

import hashlib
import json
import math
from pathlib import Path


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


def percent(value):
    return f"{100 * value:.2f}%"


def rate(k, n):
    ci = wilson(k, n)
    return f"{k}/{n}" + (f" ({percent(k / n)}; Wilson95 {percent(ci[0])}–{percent(ci[1])})" if n else "")


def main():
    directory = Path(__file__).resolve().parent
    root = directory.parents[4]
    remote_root = "/public/home/sunyihan/rpent_libero_eval"
    remote_directory = remote_root + "/" + str(directory.relative_to(root))
    report = json.loads((directory / "report.json").read_text())
    strict = json.loads((directory / "strict_setup_and_control_audit.json").read_text())
    controls = json.loads((directory / "server_controls_audit.json").read_text())
    assert report["complete"] and report["overall"]["recorded"] == 40
    assert report["overall"]["missing"] == 0
    assert strict["report_sha256"] == sha(directory / "report.json")
    assert controls["captured_report_sha256"] == sha(directory / "report.json")
    refs = report["ledgers"] + report["infrastructure_ledgers"]
    raw = []
    for ref in refs:
        local = root / ref["path"].removeprefix(remote_root + "/")
        assert sha(local) == ref["sha256"]
        raw.append({**ref, "size_bytes": local.stat().st_size,
                    "kind": "raw recorded evidence; not staged"})
    slurm = []
    for line in (directory / "slurm_completed_UTC.tsv").read_text().splitlines():
        job, state, exit_code, ended = line.split("|")
        if "." not in job:
            assert state == "COMPLETED" and exit_code == "0:0"
            slurm.append({"job_id": job, "state": state, "exit_code": exit_code,
                          "ended_UTC": ended})
    assert len(slurm) == 8
    group_rows = []
    for key, item in strict["groups"].items():
        known = next(group for group in report["by_type_method"] if group["type_method"] == key)
        successes = item.get("strict_true_setup_newly_satisfied", 0)
        trials = item.get("strict_true_setup_first", 0)
        group_rows.append({"type_method": key, "planned": item["recorded"],
                           "setup_legacy_true": item["setup_legacy_true"],
                           "setup_all_current_support_v2_true": item["setup_v2_true"],
                           "first_physically_executed": item["first_physically_executed"],
                           "newly_satisfied_any_setup": item.get("class:newly_satisfied", 0),
                           "already_satisfied_preserved": item.get("class:already_satisfied_preserved", 0),
                           "strict_ready_executed_first": trials,
                           "strict_ready_newly_satisfied": successes,
                           "strict_ready_rate": successes / trials if trials else None,
                           "strict_ready_wilson95": wilson(successes, trials),
                           "confusion": known["confusion"],
                           "exclusive_classification": {k.removeprefix("class:"): v
                                                         for k, v in item.items() if k.startswith("class:")}})
    total = strict["overall"]
    control_total = {}
    for item in controls["by_type_condition"].values():
        for key, value in item.items():
            if key.startswith("server_") or key == "private_truth_used_for_control":
                control_total[key] = control_total.get(key, 0) + value
    assert control_total["server_requested_controls"] == total["setup_vla_requested"] + total["first_vla_requested"]
    assert control_total["server_executed_controls"] == 24940
    assert control_total["server_motion_accounting_matches"] == 40
    assert control_total["server_requested_equals_executed"] == 40
    assert not control_total["server_external_truncation"]
    assert not control_total["server_native_success_stops_chunk"]
    assert not control_total["private_truth_used_for_control"]
    overall = report["overall"]
    evidence = {
        "job_id": 4219,
        "scope": "complete original paired selection; no confirmation, behavior freeze or training admission",
        "source": report["source"],
        "slurm_array_tasks": slurm,
        "last_ended_UTC": max(row["ended_UTC"] for row in slurm),
        "registered_cases": 40, "completed_case_records": 40,
        "unique_raw_initial_states": 20,
        "raw_files": raw,
        "overall_exclusive_classification": {k.removeprefix("class:"): v
                                             for k, v in total.items() if k.startswith("class:")},
        "setup_truth_strata": {
            "legacy_true": 30, "all_current_support_v2_true": 25,
            "legacy_true_v2_false": 5,
            "scope": "read-only diagnostic strata; private truth did not control execution"},
        "first_execution": {"physically_executed": 31,
                            "endpoint_true": 24,
                            "newly_satisfied": 22,
                            "already_satisfied_preserved": 2,
                            "endpoint_false": 7,
                            "strict_ready_executed_first": 21,
                            "strict_ready_newly_satisfied": 18,
                            "strict_ready_rate": 18 / 21,
                            "strict_ready_wilson95": wilson(18, 21)},
        "verifier": overall["verifier_known_truth_audit"],
        "verifier_confusion": {"TP": 11, "FN": 9, "TN": 6, "FP": 0,
                               "null_private_positive": 4, "null_private_negative": 1},
        "control_accounting": {
            "server": control_total,
            "setup_vla_requested_executed": [11040, 11040],
            "first_vla_requested_executed": [13900, 13900],
            "setup_non_vla_motion_controls": 2559,
            "first_non_vla_motion_controls": 1398,
            "short_vla_chunks": 0,
            "scope": "VLA totals are controls in recorded policy chunks; non-VLA motion and private fixed-hold metrology are separate, not included in the VLA total"},
        "by_type_method": group_rows,
        "legacy_report_retained": strict["legacy_original_report_retained"],
        "median_wall_s": overall["median_wall_s"],
        "qualification_authorized": False, "new_physical_trials": 0,
        "new_training_rows": 0,
    }
    write_json(directory / "complete_evidence.json", evidence)
    lines = [
        "# 4219 完整放置选择批 CPU 审计",
        "",
        "40/40 已保存，8 个数组分片均 COMPLETED 0:0；最后结束于 2026-10-06 14:54:51 UTC。20 个唯一原版 LIBERO-90 raw states，两个方法配对，仍是已访问选择状态，不构成确认批或冻结资格。",
        "",
        f"严格 all-current-support v2 准备真为 25/40，实际执行首次放置 21 例，其中新完成 {rate(18, 21)}。legacy 准备真 30/40、首次放置 21/25 的原 report 原样保留。5 例 legacy=true 而 v2=false。所有严格准备真且已执行的首次放置均从目标未满足开始，没有把保持已有成功计入这 18 例。",
        "",
        "全批 31 次真正执行首次动作：22 次新增物理完成、2 次保持已有成功、7 次物理失败。9 次未执行分为准备抓取公共未验证 3、目标公共 binding 缺失 4、selected_instance_not_uniquely_measured 2；这些记录全部保留。",
        "",
        "| 类型 / 方法 | 严格准备真 / 计划 | 真正执行首次动作 | 新增 / 保持 | 严格真准备的新增成功 |",
        "|---|---:|---:|---:|---:|",
    ]
    for group in group_rows:
        lines.append(f"| {group['type_method']} | {group['setup_all_current_support_v2_true']}/{group['planned']} | {group['first_physically_executed']} | {group['newly_satisfied_any_setup']} / {group['already_satisfied_preserved']} | {rate(group['strict_ready_newly_satisfied'], group['strict_ready_executed_first'])} |")
    lines += [
        "",
        f"公共放置验证器：TP11、FN9、TN6、FP0；缺测5（私有真4、假1）。测量到的精度 {rate(11, 11)}、召回 {rate(11, 20)}；把缺测保留在已知真值分母中的一致率 {rate(17, 31)}。缺测既没有删掉，也没有改成 FP/FN。",
        "",
        "| 类型 / 方法 | TP | FN | TN | FP | 缺测真 | 缺测假 |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for group in group_rows:
        c = group["confusion"]
        lines.append(f"| {group['type_method']} | {c.get('tp', 0)} | {c.get('fn', 0)} | {c.get('tn', 0)} | {c.get('fp', 0)} | {c.get('unmeasured_private_positive', 0)} | {c.get('unmeasured_private_negative', 0)} |")
    lines += [
        "",
        "完整动作块：40/40 服务端与运动计数一致，24940/24940 VLA controls（准备11040、首次13900），短块0；native 不截断、external 截断0、private truth 控制0。非VLA运动另为准备2559、首次1398 controls；私有固定hold测量也另记，不把 VLA 总数说成全仿真步数。",
        "",
        "源码快照：`/public/home/sunyihan/rpent_libero_eval/source_v5_runtime553_20261006`，commit 未嵌入，保留 null。probe SHA256 `f57769ec6ba120430f1feec114d3f17dacd68961d2700346674dcadbc542725c`。",
        "",
        "原 report SHA256 `3aa5f85715f4a5ee0732d80f8666c063a3440ad83b250e9a5a83d8873c277247`；控制审计 SHA256 `772805e091364ff03554ce15ad3d965dcf156f187f38121106dcfbe9b151089b`。",
        "",
        "本批不达首次放置90%目标，验证器一致率也未达95%。精度11/11仅是选择批点估计；不授确认资格。未修改已完成作业，没有物理重跑，没有新增训练行。raw JSONL/gzip 不入 Git。",
        "",
    ]
    (directory / "summary.md").write_text("\n".join(lines))
    names = ["report.json", "server_controls_audit.json", "strict_setup_and_control_audit.json",
             "slurm_completed_UTC.tsv", "analyze_complete4219.py", "finalize_complete4219.py",
             "complete_evidence.json", "summary.md"]
    files = [{"path": remote_directory + "/" + name, "sha256": sha(directory / name),
              "size_bytes": (directory / name).stat().st_size} for name in names]
    write_json(directory / "artifact_manifest.json", {
        "job_id": 4219, "files": files, "raw_refs": raw,
        "original_manifest": report["manifests"],
        "qualification_authorized": False, "new_physical_trials": 0, "new_training_rows": 0})
    write_json(directory / "handoff.json", {
        "status": "completed selection CPU evidence ready", "job_id": 4219,
        "output_directory": remote_directory,
        "physical_directory": remote_root + "/results/harness_v5/place553_fullchunks_selection_CPU_20261006/physical_same40/job4219",
        "source": report["source"],
        "manifest": {"path": remote_directory + "/artifact_manifest.json",
                     "sha256": sha(directory / "artifact_manifest.json")},
        "evidence": {"path": remote_directory + "/complete_evidence.json",
                     "sha256": sha(directory / "complete_evidence.json")},
        "summary": {"path": remote_directory + "/summary.md", "sha256": sha(directory / "summary.md")},
        "result": {"recorded": 40, "strict_setup_true": 25,
                   "strict_ready_first_place": "18/21", "newly_satisfied": 22,
                   "preserved": 2, "unmeasured_verifier": 5,
                   "VLA_requested_executed": "24940/24940"},
        "next_problem": "on endpoint failures and verifier FN/null; confirmation and behavior freeze remain unauthorized",
        "raw_or_gzip_staged": False, "GPU_submitted_by_this_CPU_audit": False,
        "qualification_authorized": False, "new_physical_trials": 0, "new_training_rows": 0})
    print(json.dumps({"directory": str(directory), "handoff_sha256": sha(directory / "handoff.json"),
                      "evidence_sha256": sha(directory / "complete_evidence.json"),
                      "manifest_sha256": sha(directory / "artifact_manifest.json")}))


if __name__ == "__main__":
    main()
