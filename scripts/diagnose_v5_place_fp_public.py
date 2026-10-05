"""Explain placement false positives from explicit original-task evidence.

Alternate current-target/cache checks are development analyses, not verified
runtime changes or independently confirmed precision claims.
"""

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path

from robots.libero.v5_state import Entity
from robots.libero.v5_verification import strict_place_verified_v5, strict_place_verified_v6


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def entity(raw):
    return None if raw is None else Entity(**{k: v for k, v in raw.items() if k in Entity.__dataclass_fields__})


def verdict(measurement, function, target=None):
    return function(entity(measurement.get("first")), entity(measurement.get("second")),
                    entity(target or measurement["target"]), measurement["opening"],
                    measurement["eef_xyz"], measurement["interval_s"], relation=measurement["relation"])


def metrics(records, field):
    counts = Counter()
    for record in records:
        truth, value = record["private_recorded_truth"], record[field]
        if not isinstance(truth, bool):
            counts["truth_unknown"] += 1
        elif value is None:
            counts["abstained_positive" if truth else "abstained_negative"] += 1
        else:
            counts["tp" if truth and value else "fp" if value else "fn" if truth else "tn"] += 1
    positive = counts["tp"] + counts["fn"] + counts["abstained_positive"]
    predicted = counts["tp"] + counts["fp"]
    return {"counts": dict(counts), "precision": counts["tp"] / predicted if predicted else None,
            "recall_including_abstentions": counts["tp"] / positive if positive else None}


def geometry(measurement, target):
    rows = []
    for key in ("first", "second"):
        item = measurement.get(key)
        if item is None:
            rows.append({"frame": key, "missing": True})
            continue
        area = math.prod(max(item["upper"][i] - item["lower"][i], 1e-6) for i in (0, 1))
        overlap = math.prod(max(0, min(item["upper"][i], target["upper"][i])
                               - max(item["lower"][i], target["lower"][i])) for i in (0, 1))
        rows.append({"frame": key, "source_step": item["source_step"], "visible": item["visible"],
                     "footprint_overlap": overlap / area,
                     "lower_to_target_top_cm": 100 * (item["lower"][2] - target["upper"][2]),
                     "center_in_target_xy": all(target["lower"][i] <= item["xyz"][i] <= target["upper"][i] for i in (0, 1))})
    return rows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text())
    captured_at_utc = datetime.now(timezone.utc).isoformat()
    report_path = Path(manifest["placement_report"]["path"])
    raw = report_path.read_bytes()
    if sha(raw) != manifest["placement_report"]["sha256"]:
        raise ValueError("source placement report changed")
    previous = json.loads(raw)
    expected_sha = {source["path"]: source["sha256"] for source in previous["sources"]}
    traces, sources, records = {}, [], []
    for record in previous["records"]:
        trace = record["trace"]
        if trace not in traces:
            raw = Path(trace).read_bytes()
            if sha(raw) != expected_sha[trace]:
                raise ValueError(f"source trace changed: {trace}")
            traces[trace] = {event["decision"]: event for event in map(json.loads, raw.splitlines())}
            sources.append({"path": trace, "sha256": sha(raw)})
        event = traces[trace][record["decision"]]
        measurement = record["measurement"]
        if measurement != event["verification_measurements"]:
            raise ValueError("report and trace measurements differ")
        truth = (event.get("predicate_verification_evidence") or {}).get("physical_placement_predicate")
        if truth != record["private_recorded_truth"]:
            raise ValueError("report and trace physical labels differ")
        cached = measurement["target"]
        current = next((e for e in event.get("post_measurements", []) if e["id"] == cached["id"]), None)
        baseline = verdict(measurement, strict_place_verified_v5)
        if baseline != record["recomputed"]["v5"]:
            raise ValueError("saved v5 verdict could not be reproduced")
        strict6 = verdict(measurement, strict_place_verified_v6)
        delta = math.dist(cached["xyz"], current["xyz"]) if current else None
        fresh = bool(current and measurement.get("first") and
                     current["source_step"] >= measurement["first"]["source_step"])
        alternate = verdict(measurement, strict_place_verified_v6, target=current) if current else None
        guard = None if strict6 is True and fresh and delta > .02 else strict6
        rows = {**record, "v5": baseline, "v6": strict6,
                "candidate_current_visible_target": alternate,
                "candidate_cache_change_abstain_2cm": guard,
                "post_target_public_measurement": current, "target_center_change_cm": delta * 100 if delta is not None else None,
                "post_target_at_or_after_first_frame": fresh,
                "cached_target_geometry": geometry(measurement, cached),
                "current_target_geometry": geometry(measurement, current) if current else None,
                "perception_provenance": event.get("post_perception_measurement_evidence", {}).get(cached["id"]),
                "decision_frame_step": event.get("decision_frame_step"), "post_frame_step": event.get("post_frame_step")}
        if baseline is True and truth is False:
            rows["supported_failure_mechanism"] = (
                "anchor_region_has_no_measured_support_surface" if cached["name"].startswith("area ") else
                "cached_support_disagrees_with_new_visible_target_geometry")
            rows["causal_limit"] = (
                "Anchor-derived height is not a measured support surface." if cached["name"].startswith("area ") else
                "RGB-D visible-bounds shift can combine physical displacement and occlusion; saved data do not isolate these causes.")
        records.append(rows)
    smoke_source = None
    smoke_closed_prefix = None
    smoke_records, smoke_unavailable = [], []
    if manifest.get("smoke_ledger"):
        path = Path(manifest["smoke_ledger"])
        if path.exists():
            raw = path.read_bytes()
            end = raw.rfind(b"\n") + 1
            closed = raw[:end]
            smoke_closed_prefix = closed
            smoke_source = {"path": str(path), "captured_sha256": sha(raw), "closed_prefix_sha256": sha(closed),
                            "bytes": len(raw), "incomplete_tail_bytes": len(raw) - end,
                            "selection": "all complete rows in one explicit ledger read; no outcome filtering"}
            for episode in map(json.loads, closed.splitlines()):
                trace = Path(episode["output_dir"]) / "choices.jsonl"
                choice_raw = trace.read_bytes()
                if episode.get("choices_sha256") and sha(choice_raw) != episode["choices_sha256"]:
                    raise ValueError("smoke choices SHA changed")
                for event_index, event in enumerate(map(json.loads, choice_raw.splitlines())):
                    receipt = event.get("receipt") or {}
                    if receipt.get("tool") not in ("place", "adjust_place", "vla_subtask") or not receipt.get("target"):
                        continue
                    measurement = event.get("verification_measurements") or {}
                    hook = event.get("predicate_verification_evidence") or {}
                    truth = hook.get("physical_placement_predicate") if hook else (event.get("private_after") or {}).get("satisfied")
                    base = {"episode": episode.get("episode") or episode.get("case", {}).get("episode"),
                            "trace": str(trace), "trace_sha256": sha(choice_raw),
                            "decision": event.get("decision"), "event_index": event_index, "phase": event.get("phase"),
                            "receipt": receipt, "measurement": measurement,
                            "private_recorded_truth": truth,
                            "label_source": "predicate_verification_evidence" if hook else "private_after.satisfied"}
                    missing = [k for k in ("target", "opening", "eef_xyz", "interval_s", "relation") if measurement.get(k) is None]
                    if measurement.get("kind") != "placement" or missing:
                        smoke_unavailable.append({**base, "missing": missing})
                        continue
                    smoke_records.append({**base, "v5": verdict(measurement, strict_place_verified_v5),
                                          "v6": verdict(measurement, strict_place_verified_v6)})
        else:
            smoke_source = {"path": str(path), "not_present_at_capture": True}
    output = {"scope": "development reanalysis only; not independent qualification or altered old verdicts",
              "captured_at_utc": captured_at_utc,
              "manifest": {"path": str(args.manifest), "sha256": sha(args.manifest.read_bytes())},
              "placement_report_source": manifest["placement_report"], "checked_original_traces": sources,
              "verifier_source": {"path": str(Path("robots/libero/v5_verification.py").resolve()), "sha256": sha(Path("robots/libero/v5_verification.py").read_bytes())},
              "script_sha256": sha(Path(__file__).read_bytes()),
              "metrics": {field: metrics(records, field) for field in ("v5", "v6", "candidate_current_visible_target", "candidate_cache_change_abstain_2cm")},
              "four_v5_false_positives": [r for r in records if r["v5"] is True and r["private_recorded_truth"] is False],
              "candidate_cache_guard_lost_true_positives": [r for r in records if r["v6"] is True and r["candidate_cache_change_abstain_2cm"] is None and r["private_recorded_truth"] is True],
              "original_records": records,
              "smoke": {"source": smoke_source, "events": smoke_records, "unrecomputable": smoke_unavailable,
                        "metrics": {name: metrics(smoke_records, name) for name in ("v5", "v6")},
                        "recorded_runtime_rule_counts": dict(Counter(r["receipt"].get("verification_rule", "not_recorded") for r in smoke_records))},
              "limits": ["All 174 original events are used, including false negatives and abstentions.",
                         "The 13 unavailable original events remain unavailable and retained in the old report.",
                         "Current-target and 2cm cache checks are analyses, not runtime changes; confirmation is still required.",
                         "Visible geometry changes do not alone identify physical target motion.",
                         "Live smoke is a fixed closed prefix, not a completed evaluation.",
                         "No new physics, model calls, or training rows."]}
    args.output.mkdir(parents=True, exist_ok=False)
    if smoke_closed_prefix is not None:
        capture_path = args.output / "smoke_closed_episodes.jsonl"
        capture_path.write_bytes(smoke_closed_prefix)
        output["smoke"]["source"]["captured_closed_prefix_path"] = str(capture_path)
    path = args.output / "report.json"
    path.write_text(json.dumps(output, indent=2) + "\n")
    print(json.dumps({"report": str(path), "sha256": sha(path.read_bytes()), "metrics": output["metrics"],
                      "false_positives": [{"episode": r["episode"], "decision": r["decision"],
                                           "cached_target": r["measurement"]["target"]["name"], "v6": r["v6"],
                                           "center_change_cm": r["target_center_change_cm"],
                                           "current_target": r["candidate_current_visible_target"]} for r in output["four_v5_false_positives"]],
                      "smoke_events": len(smoke_records), "smoke_unavailable": len(smoke_unavailable)}))


if __name__ == "__main__":
    main()
