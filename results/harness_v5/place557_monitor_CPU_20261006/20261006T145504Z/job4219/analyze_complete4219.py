"""Audit completed4219 explicit files; never execute or relabel a trial."""

from collections import Counter, defaultdict
import hashlib
import importlib.util
import json
import math
from pathlib import Path


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def wilson(k, n):
    if not n:
        return None
    z = 1.959963984540054
    p, denom = k / n, 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    width = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return [centre - width, centre + width]


def main():
    root = Path(__file__).resolve().parents[5]
    directory = Path(__file__).resolve().parent
    report_path = directory / "report.json"
    assert sha(report_path) == "3aa5f85715f4a5ee0732d80f8666c063a3440ad83b250e9a5a83d8873c277247"
    report = json.loads(report_path.read_text())
    helper_path = root / "results/harness_v5/skill549_live_CPU_20261006/20261006T142400Z/audit_completed_records.py"
    assert sha(helper_path) == "b29487fba4ef8ed265d05f877ac2f44bdd59d0ad50e177a710efa7def9a5709a"
    spec = importlib.util.spec_from_file_location("completed_skill_controls", helper_path)
    helper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helper)
    groups, records, raw_files = defaultdict(Counter), [], []
    for ref in report["ledgers"]:
        path = root / ref["path"].removeprefix("/public/home/sunyihan/rpent_libero_eval/")
        assert sha(path) == ref["sha256"]
        raw_files.append({"remote_path": ref["path"], "local_path": str(path),
                          "sha256": ref["sha256"], "size_bytes": path.stat().st_size})
        for line_number, line in enumerate(path.read_text().splitlines(), 1):
            row = json.loads(line)
            case, first = row["case"], row.get("first_attempt")
            group = case["type"] + "/" + case["condition"]
            count = groups[group]
            setup = row.get("setup", [])
            setup_last = setup[-1] if setup else {}
            legacy = setup_last.get("private_true_sustained_grasp")
            strict = setup_last.get("private_hold_truth_v2", {}).get("success")
            count["recorded"] += 1
            count["setup_legacy_true"] += legacy is True
            count["setup_v2_true"] += strict is True
            count["setup_legacy_true_v2_false"] += legacy is True and strict is False
            record = {"case": case["name"], "group": group, "episode": case["episode"],
                      "state_sha256": case["state_sha256"], "captured_ledger": ref["path"], "line": line_number,
                      "status": row["status"], "binding_error": row.get("binding_error"),
                      "legacy_setup": legacy, "all_current_support_v2_setup": strict,
                      "first": helper.projected_stage(first),
                      "native_success_before_first": helper.latched(row.get("before_first_attempt_snapshot")),
                      "server_accounting": row.get("server_chunk_execution")}
            for phase, stages in (("setup", setup), ("first", [first] if first else [])):
                for stage in stages:
                    for key, value in helper.stage_controls(stage).items():
                        count[phase + "_" + key] += value
            controls = helper.stage_controls(first)
            executed = controls["vla_executed"] + controls["non_vla_executed"] > 0
            before = (first or {}).get("private_before", {}).get("satisfied")
            after = (first or {}).get("private_after", {}).get("satisfied")
            receipt = (first or {}).get("receipt", {})
            if not first:
                category = row["status"]
            elif not executed:
                category = receipt.get("failure_reason") or receipt.get("reason") or "no_physical_execution"
            elif before is False and after is True:
                category = "newly_satisfied"
            elif before is True and after is True:
                category = "already_satisfied_preserved"
            elif after is False:
                category = "executed_endpoint_false"
            else:
                category = "executed_endpoint_unknown"
            count["first_physically_executed"] += executed
            count["class:" + category] += 1
            record["exclusive_classification"] = category
            if executed and strict is True:
                count["strict_true_setup_first"] += 1
                count["strict_true_setup_before_false"] += before is False
                count["strict_true_setup_newly_satisfied"] += before is False and after is True
                count["strict_true_setup_preserved"] += before is True and after is True
            records.append(record)
    total = Counter()
    for values in groups.values():
        total.update(values)
    result = {"job_id": 4219, "scope": "completed original paired selection only; no physics rerun, relabeling, confirmation or freezing",
              "source": report["source"], "report_sha256": sha(report_path), "helper_sha256": sha(helper_path),
              "script_sha256": sha(Path(__file__)), "overall": dict(total), "groups": {k: dict(v) for k, v in groups.items()},
              "strict_true_setup_rate": total["strict_true_setup_newly_satisfied"] / total["strict_true_setup_first"],
              "strict_true_setup_wilson95": wilson(total["strict_true_setup_newly_satisfied"], total["strict_true_setup_first"]),
              "legacy_original_report_retained": {"setup": report["overall"]["setup_private_truth"],
                                                  "first_place_with_true_setup": report["overall"]["counts"]["first_place_with_true_setup"],
                                                  "true_first_place_successes": report["overall"]["counts"]["true_first_place_successes"]},
              "raw_files_double_end_SHA_verified": raw_files,
              "raw_total_size_bytes": sum(r["size_bytes"] for r in raw_files), "raw_or_gzip_staged": False,
              "records": records, "qualification_authorized": False, "new_physical_trials": 0, "new_training_rows": 0}
    out = directory / "strict_setup_and_control_audit.json"
    out.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"output": str(out), "sha256": sha(out), "overall": result["overall"],
                      "strict_true_setup_rate": result["strict_true_setup_rate"], "strict_true_setup_wilson95": result["strict_true_setup_wilson95"]}))


if __name__ == "__main__":
    main()
