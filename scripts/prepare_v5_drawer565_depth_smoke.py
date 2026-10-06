"""Pin a deterministic 20-state original drawer depth-window development test."""

import argparse
import copy
import hashlib
import json
from collections import Counter
from pathlib import Path


def ref(path):
    path = Path(path).resolve(strict=True)
    return {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--parent", type=Path, required=True)
    parser.add_argument("--parent-sha", required=True)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--source-archive", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--public-stop", action="store_true")
    parser.add_argument("--contact-clearance", action="store_true")
    parser.add_argument("--frontmost-panel", action="store_true")
    args = parser.parse_args()
    if args.contact_clearance and not args.public_stop:
        parser.error("contact clearance comparison requires the existing public stop")
    if args.frontmost_panel and not args.contact_clearance:
        parser.error("this frontmost comparison requires the pinned contact-clearance recipe")
    if not all(p.is_absolute() for p in (args.parent, args.source, args.source_archive, args.output)):
        parser.error("all registered paths must be absolute")
    parent_ref = ref(args.parent)
    if parent_ref["sha256"] != args.parent_sha:
        raise ValueError("registered original selection parent changed")
    parent = json.loads(args.parent.read_text())
    if (parent["cohort"] != "selection" or parent["qualification_authorized"] is not False
            or parent["new_training_rows"] != 0 or len(parent["cases"]) != 200):
        raise ValueError("expected the preserved 200-state original selection")
    selected = []
    for kind in ("drawer_open", "drawer_close"):
        ordered = [c for c in parent["cases"] if c["type"] == kind]
        if len(ordered) != 100:
            raise ValueError("expected 100 registered states per type")
        # This rule depends only on the parent ordering, never an outcome.
        selected.extend(ordered[::10])
    source_identity = copy.deepcopy(parent["source_snapshot"])
    source_identity.update(path=str(args.source), commit=args.source_commit,
                           archive=ref(args.source_archive))
    for item in source_identity["files"]:
        item.update(ref(args.source / item["relative_path"]))
    method = ("native_frontmost_clearance_v7_v8_160" if args.frontmost_panel else
              "native_clearance_v8_160" if args.contact_clearance else
              "native_public_stop_v6_160" if args.public_stop else "native_depth_v5_160")
    condition = copy.deepcopy(parent["conditions"]["native_original160"])
    condition["overrides"]["drawer_bounds_depth_v5"] = True
    condition["overrides"]["drawer_current_binding_v4"] = True
    if args.public_stop:
        condition["overrides"]["drawer_public_stop_v6"] = True
    if args.contact_clearance:
        condition["overrides"]["drawer_contact_clearance_v8"] = True
        condition["private_fixture_sync"] = True
    if args.frontmost_panel:
        condition["overrides"]["drawer_frontmost_panel_v7"] = True
    cases = []
    for case in selected:
        new = copy.deepcopy(case)
        new.update(name=case["name"].replace("drawer559_", "drawer565_")
                   .replace("native_original160", method), condition=method,
                   parent_case_name=case["name"])
        cases.append(new)
    plan = copy.deepcopy(parent)
    for key in ("native_recipe_reference", "parent_manifest"):
        plan.pop(key, None)
    plan.update(version="drawer565-public-depth-smoke/1", cases=cases, cases_count=20,
                purpose="Physical metrology test of measured cabinet depth search; no qualification",
                source_snapshot=source_identity, parent_manifest=parent_ref,
                conditions={method: condition}, producer=ref(__file__),
                producer_dependencies=[parent_ref],
                selection="Every tenth registered case within each type, preserving original ordering",
                state_repetition="20 already visited original selection states; never confirmation",
                metrics={**parent["metrics"], "new_public_geometry": "Measured parent-depth search only"},
                diagnostic_factors={"only_change": "drawer_bounds_depth_v5=true",
                                    "unchanged": "prompt, reset,160 complete chunks,setup and scoring"},
                preregistered_requests_by_type_arm={f"{kind}/{method}": 10
                    for kind in ("drawer_open", "drawer_close")},
                qualification_authorized=False, new_training_rows=0,
                new_physical_trials=0, run_status="CPU_prepared_not_submitted")
    if args.public_stop:
        plan.update(version="drawer566-measured-complete-endpoint-stop/1",
                    purpose="Original development comparison of measured complete endpoints and public early stop",
                    diagnostic_factors={"changes": "depth-v5, signed complete endpoints, two-fresh-frame public stop",
                                        "unchanged": "original prompts, reset, setup, max160 chunks and private scoring"},
                    public_stop_contract={"poll_every_chunks": 5, "stable_fresh_frames": 2,
                                          "open_min_m": .141, "close_max_m": .0005,
                                          "frame_drift_max_m": .01, "panel_delta_max_m": .005,
                                          "direction": "runtime_measured_handle_front_axis",
                                          "calibration": "original200 selection only; no qualification",
                                          "private_inputs_used_for_control": False})
    if args.contact_clearance:
        plan.update(version="drawer569-measured-contact-clearance/1-dev",
                    purpose="Original selection20: preserve public contact stop and clear the fixture before view retreat",
                    diagnostic_factors={"changes": "real40-step release, measured8cm outward clearance, recoverable view retreat; read-only staged private scoring",
                                        "unchanged": "original prompts, reset, setup, max160 contact chunks, depth-v5 geometry, public-stop-v6 thresholds and private endpoint scoring"},
                    recovery_contract={"release_steps": 40, "minimum_measured_opening_m": .075,
                                       "outward_clearance_m": .08, "clearance_tolerance_m": .03,
                                       "axis_source": "runtime_public_measured_handle_front_axis",
                                       "private_labels": "chunk/stop/release/clearance/retreat read-only; never controls",
                                       "scoring_failure": "unknown/infra after execution; no physical reexecution"})
    if args.frontmost_panel:
        plan.update(version="drawer571-frontmost-supported-and-clearance/1-dev",
                    purpose="Original selection20: fit the outward supported selected drawer face and preserve contact clearance",
                    diagnostic_factors={"changes": "frontmost supported moving-plane rank; no added width gate; measured8cm clearance with staged diagnostic scoring",
                                        "unchanged": "original prompts, reset, setup, max160 contact chunks, old vertical-face/frame/binding gates and stop-v6 thresholds"},
                    public_plane_selection={"source": "paired public RGB-D",
                                            "ranking": "outward-depth after existing vertical-face fit gates",
                                            "extra_frame_width_gate": False,
                                            "cpu_same20": "all fixed frames unchanged, one formerly width-rejected front restored; private labels excluded",
                                            "qualification_authorized": False})
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x") as handle:
        handle.write(json.dumps(plan, indent=2) + "\n")
    print(json.dumps({"manifest": ref(args.output), "source": source_identity,
                      "by_type": dict(Counter(c["type"] for c in cases)), "new_gpu_jobs": 0}))


if __name__ == "__main__":
    main()
