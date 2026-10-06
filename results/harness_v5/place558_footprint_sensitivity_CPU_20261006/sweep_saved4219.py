"""Selection-only placement footprint sensitivity; all other gates stay exact."""

import __future__
import argparse
import ast
from collections import Counter
import hashlib
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace


REMOTE_ROOT = "/public/home/sunyihan/rpent_libero_eval"
DIAGNOSIS_REL = "results/harness_v5/place558_endpoint_diagnosis_CPU_20261006/diagnosis.json"
DIAGNOSIS_SHA = "1f6b5a30d79b0aa2c8df9be79ddfbad5a6feafb2d145df1f53cfba4b6f378a7a"
THRESHOLDS = (.5, .6, .7, .75, .8, .85, .9, .95)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")


def counts(records, verdicts):
    result = Counter({key: 0 for key in ("TP", "FP", "FN", "TN", "null", "null_private_true", "null_private_false")})
    for record, verdict in zip(records, verdicts):
        truth = record["private_after_label"]
        assert isinstance(truth, bool)
        if verdict is None:
            result["null"] += 1
            result["null_private_true" if truth else "null_private_false"] += 1
        else:
            result["TP" if verdict and truth else "FP" if verdict else "FN" if truth else "TN"] += 1
    tp, fp, fn, tn = (result[key] for key in ("TP", "FP", "FN", "TN"))
    return {**dict(result), "records": len(records), "private_true": sum(r["private_after_label"] for r in records),
            "precision": tp / (tp + fp) if tp + fp else None,
            "recall_measured": tp / (tp + fn) if tp + fn else None,
            "recall_over_all_private_positive": tp / sum(r["private_after_label"] for r in records)
                  if any(r["private_after_label"] for r in records) else None,
            "known_truth_agreement_including_null": (tp + tn) / len(records) if records else None,
            "precision_wilson95": wilson(tp, tp + fp), "recall_measured_wilson95": wilson(tp, tp + fn)}


def wilson(k, n):
    if not n:
        return None
    import math
    z = 1.959963984540054
    den = 1 + z * z / n
    centre = (k / n + z * z / (2 * n)) / den
    half = z * math.sqrt(k / n * (1 - k / n) / n + z * z / (4 * n * n)) / den
    return [max(0, centre - half), min(1, centre + half)]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    args = parser.parse_args()
    root = args.root.resolve()
    directory = root / "results/harness_v5/place558_footprint_sensitivity_CPU_20261006"
    directory.mkdir(exist_ok=True)
    diagnostic_directory = root / Path(DIAGNOSIS_REL).parent
    diagnosis_path = root / DIAGNOSIS_REL
    assert sha(diagnosis_path) == DIAGNOSIS_SHA
    diagnosis = json.loads(diagnosis_path.read_text())
    for ref in [diagnosis["source_report"], *diagnosis["captured_raw_refs"]]:
        assert sha(root / Path(ref["path"]).relative_to(REMOTE_ROOT)) == ref["sha256"]
    helper_path = diagnostic_directory / "analyze_saved4219.py"
    spec = importlib.util.spec_from_file_location("diagnosis_saved4219", helper_path)
    helper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helper)
    original = helper.verifier_functions(diagnostic_directory)
    verifier_source = diagnostic_directory / "preparation/v5_verification.py"
    source_refs = diagnosis["source_files"]
    for ref in source_refs:
        assert sha(diagnostic_directory / "preparation" / Path(ref["path"]).name) == ref["sha256"]
    records = diagnosis["records"]
    assert len(records) == 31

    def evaluate(function, record):
        value = record["public_verification_measurements"]
        entities = [SimpleNamespace(**value[key]) if value[key] else None for key in ("first", "second", "target")]
        return function(*entities, value["opening"], tuple(value["eef_xyz"]), value["interval_s"], relation=value["relation"])

    baseline = [evaluate(original, record) for record in records]
    assert all(a is b["runtime_verdict_saved"] for a, b in zip(baseline, records))
    # Replace one footprint keyword expression inside copied pure v2 only.
    # Other functions, thresholds, missing-evidence branches and metadata stay exact.
    ns = original.__globals__.copy()
    ns["SWEEP_ON"], ns["SWEEP_IN"] = .9, .85
    tree = ast.parse(verifier_source.read_text())
    function = next(node for node in tree.body if isinstance(node, ast.FunctionDef)
                    and node.name == "strict_place_verified_v2")
    expression = next(keyword for node in ast.walk(function) if isinstance(node, ast.Call)
                      for keyword in node.keywords if keyword.arg == "minimum_footprint_overlap")
    assert isinstance(expression.value, ast.IfExp)
    assert expression.value.body.value == .9 and expression.value.orelse.value == .85
    expression.value.body = ast.Name(id="SWEEP_ON", ctx=ast.Load())
    expression.value.orelse = ast.Name(id="SWEEP_IN", ctx=ast.Load())
    ast.fix_missing_locations(function)
    exec(compile(ast.Module(body=[function], type_ignores=[]), "copied_pure_footprint_parameter_sweep", "exec",
                 flags=__future__.annotations.compiler_flag), ns)
    # Recompile wrappers into the parameterized namespace; cloned functions
    # cannot retain their original globals during the sensitivity runs.
    names = {"strict_place_verified_v3", "strict_place_verified_v5", "strict_place_verified_v6"}
    wrappers = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in names]
    exec(compile(ast.Module(body=wrappers, type_ignores=[]), "copied_pure_footprint_wrappers", "exec",
                 flags=__future__.annotations.compiler_flag), ns)
    swept = ns["strict_place_verified_v6"]
    assert [evaluate(swept, record) for record in records] == baseline
    all_rows = []
    for relation in ("on", "in"):
        subset_indices = [i for i, record in enumerate(records)
                          if record["public_verification_measurements"]["relation"] == relation]
        subset = [records[i] for i in subset_indices]
        for threshold in THRESHOLDS:
            ns["SWEEP_ON"] = threshold if relation == "on" else .9
            ns["SWEEP_IN"] = threshold if relation == "in" else .85
            verdicts = [evaluate(swept, record) for record in records]
            assert all(verdicts[i] is baseline[i] for i in range(31) if i not in subset_indices)
            assert all(new is None for new, old in zip(verdicts, baseline) if old is None)
            changes = []
            for record, old, new in zip(records, baseline, verdicts):
                if new is not old:
                    assert record["public_verification_measurements"]["relation"] == relation
                    changes.append({"case": record["case"], "episode": record["episode"], "method": record["method"],
                                    "raw_state_sha256": record["raw_state_sha256"],
                                    "private_before_label_original": record["private_before_label"],
                                    "private_after_label_original": record["private_after_label"],
                                    "setup_v2_label_original": record["setup_all_current_support_v2_label"],
                                    "public_verdict_original": old, "hypothetical_verdict": new,
                                    "footprint_overlap_two_frames": record["rejection_flags"].get("footprint_overlap"),
                                    "original_categories": record["categories"], "ledger": record["captured_ledger"],
                                    "line": record["line"], "ledger_sha256": record["ledger_sha256"]})
            all_rows.append({"swept_relation": relation, "threshold": threshold,
                             "fixed_other_threshold": .85 if relation == "on" else .9,
                             "relation_counts": counts(subset, [verdicts[i] for i in subset_indices]),
                             "relation_initially_unsatisfied_counts": counts(
                                 [records[i] for i in subset_indices if records[i]["private_before_label"] is False],
                                 [verdicts[i] for i in subset_indices if records[i]["private_before_label"] is False]),
                             "all31_counts": counts(records, verdicts), "hypothetical_changed_rows": changes,
                             "all31_initially_unsatisfied_counts": counts(
                                 [record for record in records if record["private_before_label"] is False],
                                 [verdict for record, verdict in zip(records, verdicts) if record["private_before_label"] is False]),
                             "hypothetical_all31_verdicts": [{"case": record["case"], "private_truth_original": record["private_after_label"],
                                                             "public_verdict_original": old, "hypothetical_verdict": new}
                                                            for record, old, new in zip(records, baseline, verdicts)]})
    result = {"job_id": 4219, "version": "saved-original-selection-footprint-sensitivity/1",
              "input_diagnosis": {"path": REMOTE_ROOT + "/" + DIAGNOSIS_REL, "sha256": DIAGNOSIS_SHA},
              "source": diagnosis["source"], "source_files": source_refs, "source_report": diagnosis["source_report"],
              "original_manifest": diagnosis["input_manifest"], "captured_raw_refs": diagnosis["captured_raw_refs"],
              "helper": {"path": REMOTE_ROOT + "/" + str(helper_path.relative_to(root)), "sha256": sha(helper_path)},
              "script_sha256": sha(Path(__file__)), "baseline_exact_matches": 31,
              "baseline_all31": counts(records, baseline),
              "baseline_all31_initially_unsatisfied": counts(
                  [record for record in records if record["private_before_label"] is False],
                  [verdict for record, verdict in zip(records, baseline) if record["private_before_label"] is False]),
              "baseline_by_relation": {relation: counts([r for r in records if r["public_verification_measurements"]["relation"] == relation],
                                                         [v for r, v in zip(records, baseline) if r["public_verification_measurements"]["relation"] == relation])
                                       for relation in ("on", "in")},
              "one_AST_expression_changed": "strict_place_verified_v2 minimum_footprint_overlap conditional values only",
              "fixed": ["centre_xy", "vertical_center", "on_support_bottom_gap_1cm", "in_bottom_bounds",
                        "gripper_opening_7cm", "eef_withdrawal_5cm", "two_frame_stability_2cm", "interval_300ms",
                        "missing_evidence_unknown", "unmeasured_cavity_unknown", "area_support_unknown"],
              "runs": all_rows, "source_or_labels_modified": False, "qualification_authorized": False,
              "physical_replay": False, "new_training_rows": 0,
              "scope": "31 saved first executions from already-visited original selection states; hypothetical verifier outputs only; precision/recall here cannot qualify a threshold or establish confirmation performance"}
    write(directory / "sensitivity.json", result)
    columns = ["swept_relation", "threshold", "n", "TP", "FP", "FN", "TN", "null", "precision", "recall_measured", "recall_all_positive", "changed_rows"]
    rows = ["\t".join(columns)]
    for run in all_rows:
        c = run["relation_counts"]
        values = [run["swept_relation"], run["threshold"], c["records"], c["TP"], c["FP"], c["FN"], c["TN"], c["null"],
                  c["precision"], c["recall_measured"], c["recall_over_all_private_positive"], len(run["hypothetical_changed_rows"])]
        rows.append("\t".join(str(value) for value in values))
    (directory / "precision_recall.tsv").write_text("\n".join(rows) + "\n")
    print(json.dumps({"sensitivity_sha256": sha(directory / "sensitivity.json"), "baseline": result["baseline_all31"],
                      "sweeps": [{"relation": run["swept_relation"], "threshold": run["threshold"], "counts": run["relation_counts"],
                                  "changes": len(run["hypothetical_changed_rows"])} for run in all_rows]}))


if __name__ == "__main__":
    main()
