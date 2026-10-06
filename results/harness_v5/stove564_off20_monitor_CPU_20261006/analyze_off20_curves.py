"""Classify fixed-contact and recovery losses after all cells are collected."""

from collections import Counter
import csv
import hashlib
import json
from pathlib import Path
import statistics


def identity(path):
    path = Path(path)
    return {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    root = Path(__file__).resolve().parent
    final = root / "final_complete_v1"
    summary = json.loads((final / "summary.json").read_text())
    curves = [json.loads(line) for line in (final / "private_chunk_curves.jsonl").read_text().splitlines()]
    assert summary["valid_physical_cells"] == 20 and summary["completed_contact_chunks"] == 6400
    assert summary["private_score_rows"] == 6440 and not summary["source_and_reference_violations"]
    rows = []
    for cell in summary["cells"]:
        name = cell["name"]
        chunk_rows = [r for r in curves if r["cell"] == name and r["phase"] == "off"]
        true_rows = [r for r in chunk_rows if r["turn_off_satisfied"]]
        if cell["turn_off_after_recovery"]:
            category = "off_satisfied_after_recovery"
        elif cell["turn_off_after_contact"]:
            category = "off_satisfied_after_contact_lost_during_combined_recovery"
        elif true_rows:
            category = "transient_off_lost_during_fixed_contact"
        else:
            category = "never_observed_off_in_fixed_contact"
        runs, current = [], []
        for r in chunk_rows:
            if r["turn_off_satisfied"]:
                current.append(r)
            elif current:
                runs.append(current)
                current = []
        if current:
            runs.append(current)
        longest = max(runs, key=len) if runs else []
        final_q = cell["post_recovery"]["joint_qpos"][0][0]
        contact_q = cell["after_contact"]["joint_qpos"][0][0]
        refinement = cell["public_refinement"]
        refined = refinement.get("fixture_handle_approach", {}).get("before", {})
        row = {"cell": name, "seed": cell["seed"], "method": cell["method"],
               "on_setup_satisfied": cell["on_setup_satisfied"], "failure_category": category,
               "first_off_chunk": true_rows[0]["chunk_index"] if true_rows else None,
               "off_true_chunk_count": len(true_rows),
               "longest_true_off_start_chunk": longest[0]["chunk_index"] if longest else None,
               "longest_true_off_end_chunk": longest[-1]["chunk_index"] if longest else None,
               "longest_true_off_scored_span_s": longest[-1]["sim_time"] - longest[0]["sim_time"] if longest else None,
               "off_contact_q": contact_q, "recovery_q": final_q,
               "recovery_joint_delta": final_q - contact_q,
               "after_contact_off": cell["turn_off_after_contact"], "after_recovery_off": cell["turn_off_after_recovery"],
               "after_recovery_on": cell["post_recovery"]["turn_on"],
               "public_refinement_requested": cell["method"] == "measured_complete_knob_off",
               "public_refinement_executed": refinement.get("executed", False),
               "public_refinement_status": refinement.get("verification", "not_requested"),
               "public_refinement_fusion_version": refined.get("fusion_version"),
               "public_refinement_source_cameras": refined.get("source_cameras", []),
               "refinement_query_instances": sum(q["sam_instances"] for view in refined.get("views", {}).values() for q in view["queries"]),
               "wall_s": cell["wall_s"]}
        rows.append(row)
    counts = Counter(r["failure_category"] for r in rows)
    report = {"version": "off20-postcollection-causal-boundaries/1", "job": 4303,
              "input_refs": [identity(final / name) for name in ("summary.json", "private_chunk_curves.jsonl", "capture_scoring_table.jsonl")],
              "producer": identity(Path(__file__)), "rows": rows,
              "failure_category_counts": dict(counts), "on_setup_true": 20, "on_setup_false": 0,
              "failed_on_denominator_not_filtered": True,
              "method_summary": summary["method_and_setup_stratum_summary"],
              "paired_methods": summary["paired_method_comparisons"],
              "median_cell_wall_s": statistics.median(r["wall_s"] for r in rows),
              "recovery_private_joint_gap": "Existing motion_trace stores robot joints only, no stove q between release and retreat. Captures prove loss during combined recovery, cannot separate the two actions.",
              "interpretation": ["Only literal_off reached official turnoff during contact: all5 paired original states; 2/5 at160chunk endpoint, 0/5 after combined recovery.",
                "The three rewritten conditions did not improve measured completion. Public-refinement arm was unmeasured in5/5, so it does not estimate a successful refined approach's effect.",
                "No original reset was removed; these are5 original state identities times4 methods, not20 independent confirmation trials.",
                "Do not claim endpoint qualification, infer a visual endpoint threshold from private q, or use private success to stop execution.",
                "All fixed phase counts and public/capture/source SHA checks passed; zero infrastructure or model-selection score is inferred from Slurm alone."],
              "private_truth_used_for_execution": False, "new_training_rows": 0, "endpoint_qualified": False}
    (final / "failure_classification.json").write_text(json.dumps(report, indent=2) + "\n")
    with (final / "per_cell.csv").open("w") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(json.dumps({"failure_categories": dict(counts), "median_wall_s": report["median_cell_wall_s"]}))


if __name__ == "__main__":
    main()
