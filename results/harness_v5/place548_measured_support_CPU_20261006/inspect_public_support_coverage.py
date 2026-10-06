"""Inspect only explicitly pinned selection ledgers and public measurements."""

import argparse
import ast
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def pinned(ref):
    path = Path(ref["path"])
    assert sha(path) == ref["sha256"], str(path)
    return path


def defaults(path):
    tree = ast.parse(path.read_text())
    result = {}
    for cls in tree.body:
        if isinstance(cls, ast.ClassDef) and cls.name in {"MeasuredScene", "V5Executor"}:
            method = next(node for node in cls.body if isinstance(node, ast.FunctionDef) and node.name == "__init__")
            values = {}
            for arg, value in zip(method.args.kwonlyargs, method.args.kw_defaults):
                if value is not None:
                    try:
                        values[arg.arg] = ast.literal_eval(value)
                    except ValueError:
                        pass
            result[cls.name] = values
    return result


def top_parts(public, parent):
    return [e for e in public.get("entities", []) if e.get("part_of") == parent
            and e.get("visible") and e.get("geometry") == "measured_top_surface"]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--captured-report", type=Path, required=True)
    parser.add_argument("--captured-report-sha", required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--source-snapshot", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    assert sha(args.captured_report) == args.captured_report_sha
    report, plan = json.loads(args.captured_report.read_text()), json.loads(args.manifest.read_text())
    base = json.loads(pinned(plan["base_config"]).read_text())
    defs = defaults(args.source_snapshot / "robots/libero/v5_runtime.py")
    flag_names = ["dual_view_fusion_v1", "fusion_depth_trim_v2", "fixture_front_geometry_v1",
                  "fixture_parts_v1", "fixture_identity_cache_v1", "target_cache_v1", "strict_place_v5",
                  "strict_place_v6", "fixture_in_contact_v1", "shape_completion_v2", "occluded_measurement_cache_v2"]
    # Include real constructor names matching support/part rather than infer a flag from a part's presence.
    flag_names = sorted(set(flag_names) | {key for value in defs.values() for key in value
                                        if "fixture" in key or "fusion" in key or "cache" in key})
    effective = {}
    for name, condition in plan["conditions"].items():
        cfg = {**base, **condition.get("overrides", {})}
        effective[name] = {key: {"value": cfg.get(key, next((values[key] for values in defs.values() if key in values), None)),
                                 "origin": "condition_override" if key in condition.get("overrides", {})
                                 else "pinned_base_config" if key in base else "source_constructor_default"}
                           for key in flag_names if key in cfg or any(key in values for values in defs.values())}
    rows, seen = [], set()
    for ref in report["ledgers"]:
        path = pinned(ref)
        for line_number, line in enumerate(path.read_text().splitlines(), 1):
            row = json.loads(line)
            case = row["case"]
            assert case["name"] not in seen
            seen.add(case["name"])
            stage = row.get("first_attempt") or {}
            public = stage.get("public_before", {})
            selected = stage.get("selected") or ""
            arguments = selected.partition("(")[2].rstrip(")").split(",")
            target_id = arguments[1] if len(arguments) >= 3 else None
            target = next((e for e in public.get("entities", []) if e["id"] == target_id), None)
            supports = top_parts(public, target_id) if target_id else []
            before_grasp = next((s.get("public_before", {}) for s in reversed(row.get("setup", []))
                                 if (s.get("selected") or "").startswith("grasp(")), {})
            pre = top_parts(before_grasp, target_id) if target_id else []
            measurement = stage.get("verification_measurements", {})
            receipt = stage.get("receipt", {})
            rows.append({"case": case["name"], "type": case["type"], "condition": case["condition"],
                         "status": row["status"], "first_attempt_recorded": bool(stage),
                         "selected": selected, "target": target,
                         "current_visible_associated_top_surfaces": supports,
                         "before_grasp_visible_associated_top_surfaces": pre,
                         "target_cached_recorded": measurement.get("target_cached"),
                         "runtime_verification_rule": receipt.get("verification_rule"),
                         "captured_ledger": str(path), "line": line_number})
    grouped = defaultdict(Counter)
    for row in rows:
        group = grouped[f"{row['type']}/{row['condition']}"]
        group["recorded"] += 1
        if not row["first_attempt_recorded"]:
            group["no_first_attempt"] += 1
            continue
        group["first_attempt"] += 1
        if row["target"] and row["target"]["name"] == "cabinet":
            group["selected_cabinet_shell"] += 1
            group[f"current_top_supports_{len(row['current_visible_associated_top_surfaces'])}"] += 1
            group[f"before_grasp_top_supports_{len(row['before_grasp_visible_associated_top_surfaces'])}"] += 1
        group[f"verifier_{row['runtime_verification_rule']}"] += 1
        group[f"target_cached_recorded_{row['target_cached_recorded']}"] += 1
    result = {"version": "place548-public-support-coverage/1", "scope": "CPU inspection; no new physical trial or relabeling",
              "captured_report": str(args.captured_report), "captured_report_sha256": sha(args.captured_report),
              "manifest": str(args.manifest), "manifest_sha256": sha(args.manifest),
              "source_snapshot": str(args.source_snapshot), "source_runtime_sha256": sha(args.source_snapshot / "robots/libero/v5_runtime.py"),
              "script_sha256": sha(__file__), "effective_flags": effective,
              "internal_target_cache_visibility": "cache contents were not serialized; pre-grasp public availability is evidence of availability, not a claim that a particular internal cache entry exists",
              "by_type_condition": {k: dict(v) for k, v in grouped.items()}, "cases": rows}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"output": str(args.output), "sha256": sha(args.output), "counts": result["by_type_condition"]}))


if __name__ == "__main__":
    main()
