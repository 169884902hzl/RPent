"""Validate saved sustained truth and summarize current-view pan bindings."""

import hashlib
import importlib.util
import json
import sys
from collections import Counter
from pathlib import Path


OUT = Path(__file__).resolve().parent
source_file = Path(sys.argv[1]) / "robots/libero/v5_grasp_truth.py"
spec = importlib.util.spec_from_file_location("pinned_truth", source_file)
truth_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(truth_module)
rows_file = OUT / "original10_rows.json"
rows = json.loads(rows_file.read_text())
assert len(rows) == len({r["case"]["name"] for r in rows}) == 10
per_view, patterns, verdicts, cases = {}, Counter(), Counter(), []
for row in rows:
    saved_hold = row["sustained_hold"]
    recomputed = truth_module.sustained_grasp(saved_hold["samples"], row["support_reference"], .5)
    assert recomputed == saved_hold["truth"]
    assert row["true_sustained_grasp"] is recomputed["success"]
    frames = []
    for frame in row["stable_visual_grasp"]["frames"]:
        accepted = {}
        for view, acquisition in frame["handle_acquisition"].items():
            n = acquisition["accepted_instances"]
            kind = "unique" if n == 1 else "missing" if n == 0 else "ambiguous"
            accepted[view] = kind
            per_view.setdefault(view, Counter())[kind] += 1
            per_view[view]["body_binding_source:" + str(acquisition.get("body_binding_source"))] += 1
        patterns[json.dumps(accepted, sort_keys=True)] += 1
        verdicts[str(frame["verified"])] += 1
        views = {}
        for view, evidence in frame["per_view"].items():
            geometry = evidence.get("finger_geometry", {})
            views[view] = {"conditions": evidence.get("conditions"),
                           "lower_lift_m": evidence.get("lower_lift_m"),
                           "original_support_clearance_m": evidence.get("original_support_clearance_m"),
                           "current_handle_views": geometry.get("current_handle_views"),
                           "body_view": geometry.get("body_view")}
        frames.append({"step": frame["captured_step"], "selected_view": frame.get("selected_view"),
                       "verified": frame["verified"], "opening_m": frame["opening_m"],
                       "handle_acquisition": frame["handle_acquisition"], "per_view": views})
    cases.append({"case": row["case"]["name"], "registered_hold_truth": recomputed,
                  "posttrial_sustained_grasp": row["true_sustained_grasp"],
                  "public": row["first_receipt"].get("grasp_verified"),
                  "legacy_dual_pad_contact_bool": row.get("private_contact_at_final"), "frames": frames})
report = {"scope": "Completed original pan10 development: saved binding evidence and registered sustained truth",
          "producer_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
          "source_truth_file": {"path": str(source_file), "sha256": hashlib.sha256(source_file.read_bytes()).hexdigest()},
          "original_rows_sha256": hashlib.sha256(rows_file.read_bytes()).hexdigest(),
          "saved_sample_recomputations_equal_original_truth": 10,
          "truth_metric": "Registered 0.5s hold with >=3cm lower collision extent lift, target finger support and original support clear",
          "view_acquisition_counts": {k: dict(v) for k, v in per_view.items()},
          "frame_binding_patterns": dict(patterns), "saved_frame_verdicts": dict(verdicts), "cases": cases,
          "legacy_dual_pad_contact_bool_is_not_truth": True,
          "original_truth_and_public_verdicts_preserved": True,
          "qualification_authorized": False, "new_model_calls": 0, "new_physical_trials": 0}
(OUT / "public_binding_report.json").write_text(json.dumps(report, indent=2) + "\n")
print(json.dumps({k: report[k] for k in ("saved_sample_recomputations_equal_original_truth", "view_acquisition_counts", "frame_binding_patterns", "saved_frame_verdicts")}))
