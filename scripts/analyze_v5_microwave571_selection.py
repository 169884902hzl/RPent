"""Audit the ten explicitly registered public-parent microwave selection cases."""

import argparse
from collections import Counter, defaultdict
import hashlib
import json
import math
from pathlib import Path


REMOTE_ROOT = Path("/public/home/sunyihan/rpent_libero_eval")
MANIFEST_REL = Path("results/harness_v5/microwave571_public_parent_CPU_20261006/preparation/registered/microwave_public_parent_original10.json")
MANIFEST_SHA = "f9a8b3532b169c0cf93e3d78445e11e96c8beeb343ec36b76ad96c491b9a2296"
SOURCE_COMMIT = "5da67d19fe8dde8564e06c39266bb1fedc330d2a"
LEDGER_BASE = REMOTE_ROOT / "results/harness_v5/microwave571_public_parent_CPU_20261006/physical_original10/job4340"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def wilson(k, n):
    if not n:
        return None
    z = 1.959963984540054
    denominator = 1 + z * z / n
    centre = (k / n + z * z / (2 * n)) / denominator
    half = z * math.sqrt((k / n * (1 - k / n) + z * z / (4 * n)) / n) / denominator
    return {"successes": k, "trials": n, "rate": k / n, "wilson95": [centre - half, centre + half]}


def measurement_summary(value):
    phases = {}
    for phase in ("before", "after"):
        frame = value.get(phase) or {}
        phases[phase] = {"source_step": frame.get("source_step"),
            "fixed_frame_measured": bool(frame.get("frame")), "moving_face_measured": bool(frame.get("moving")),
            "fixed_frame_geometry": frame.get("fixed_frame_geometry"),
            "frame": frame.get("frame"), "moving": frame.get("moving"),
            "views": {name: {"frame": view.get("frame"), "moving": view.get("moving"),
                "measurement_counts": view.get("measurement_counts"),
                "fixed_frame_geometry": view.get("fixed_frame_geometry")}
                for name, view in frame.get("views", {}).items()}}
    return {"reason": value.get("reason"), "verification_scope": value.get("verification_scope"), **phases}


def controls(stage):
    rows = (stage or {}).get("motion_evidence", [])
    vla = [r for r in rows if r.get("name") == "vla_act_chunk"]
    requested = sum(r.get("requested_action_count", r.get("requested_actions", 5)) for r in vla)
    actual = sum(r.get("executed_action_count", r.get("actions_used", r.get("steps_used", 0))) for r in vla)
    return {"vla_chunks": len(vla), "requested_controls": requested, "executed_controls": actual,
        "non_vla_controls": sum(r.get("executed_action_count", r.get("actions_used", r.get("steps_used", 0)))
                                 for r in rows if r.get("name") != "vla_act_chunk")}


def walk_refs(value, refs):
    if isinstance(value, dict):
        if isinstance(value.get("path"), str) and isinstance(value.get("sha256"), str):
            old = refs.setdefault(value["path"], value["sha256"])
            if old != value["sha256"]:
                raise ValueError("one public artifact path has inconsistent recorded SHA")
        for child in value.values():
            walk_refs(child, refs)
    elif isinstance(value, list):
        for child in value:
            walk_refs(child, refs)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root, out = args.root.resolve(), args.output.resolve()
    manifest_path = root / MANIFEST_REL
    assert sha(manifest_path) == MANIFEST_SHA
    plan = json.loads(manifest_path.read_text())
    assert plan["source_snapshot"]["commit"] == SOURCE_COMMIT
    registered = {case["name"]: case for case in plan["cases"]}
    seen, refs, ledgers, records, groups = set(), {}, [], [], defaultdict(Counter)
    for part in range(5):
        local = out / "preparation" / f"ledger_{part:02d}.jsonl"
        remote = LEDGER_BASE / f"part{part}" / "episodes.jsonl"
        ledgers.append({"path": str(remote), "local_copy": str(local), "sha256": sha(local)})
        lines = local.read_text().splitlines()
        assert len(lines) == 2, "all registered cases retained in each explicit shard"
        for line_no, line in enumerate(lines, 1):
            raw = json.loads(line)
            case = raw["case"]
            assert case == registered[case["name"]] and case["name"] not in seen
            seen.add(case["name"])
            first = raw.get("first_attempt") or {}
            receipt = first.get("receipt") or {}
            before = first.get("private_before") or {}
            after = first.get("private_after") or {}
            setup = raw.get("setup") or []
            setup_valid = not setup or setup[-1].get("private_after", {}).get("satisfied") is True
            c = groups[case["type"]]
            c["registered"] += 1
            c["setup_valid"] += setup_valid
            executed = first.get("physically_executed") is True
            if executed:
                c["executed"] += 1
                assert before.get("satisfied") is False, "no already-satisfied endpoint can count as new completion"
                c["newly_satisfied"] += after.get("satisfied") is True
                c["endpoint_false"] += after.get("satisfied") is False
                c["valid_setup_newly_satisfied"] += setup_valid and after.get("satisfied") is True
                c["public_null"] += receipt.get("articulate_verified") is None
                c["public_true"] += receipt.get("articulate_verified") is True
                c["public_false"] += receipt.get("articulate_verified") is False
                c["effect:" + str(receipt.get("effect"))] += 1
                assert receipt.get("verification") == "unmeasured"
            else:
                c["not_executed"] += 1
            if raw.get("infrastructure_failure") or raw.get("case_had_infrastructure_failure"):
                c["infrastructure_failure"] += 1
            category = ("public_parent_binding_missing" if not first else
                "execution_error" if receipt.get("error") or receipt.get("verification") == "execution_error" else
                "newly_satisfied" if after.get("satisfied") is True else "executed_endpoint_false")
            c["classification:" + category] += 1
            stage_counts = [controls(stage) for stage in setup] + ([controls(first)] if first else [])
            server = raw["server_chunk_execution"]
            for key in ("requested_controls", "executed_controls"):
                assert sum(s[key] for s in stage_counts) == server[key]
                c[key] += server[key]
            assert all(s["requested_controls"] == s["executed_controls"] == s["vla_chunks"] * 5 for s in stage_counts)
            assert server["requested_controls"] == server["executed_controls"]
            assert not server["native_success_stops_chunk"] and not server["external_truncation"]
            assert not server["private_joint_or_predicate_used_for_control"]
            value = first.get("verification_measurements", {}).get("articulation", {})
            measured = measurement_summary(value)
            for phase in ("before", "after"):
                c[phase + "_fixed_frame_measured"] += measured[phase]["fixed_frame_measured"]
                c[phase + "_moving_face_measured"] += measured[phase]["moving_face_measured"]
            public_capture = first.get("public_microwave_adapter")
            walk_refs(public_capture, refs)
            walk_refs(value, refs)
            records.append({"case": case["name"], "type": case["type"], "episode": case["episode"],
                "raw_state_sha256": case["state_sha256"], "ledger": str(remote), "line": line_no,
                "status": raw["status"], "classification": category, "setup_valid": setup_valid,
                "setup_private_endpoints": [s.get("private_after") for s in setup],
                "executed": executed, "private_before": before, "private_after": after,
                "public_receipt": receipt, "public_measurements": measured, "public_capture": public_capture,
                "binding_error": raw.get("binding_error"), "binding_evidence": first.get("binding_evidence"),
                "controls": stage_counts, "server_controls": server, "wall_s": raw["wall_s"],
                "native_original_success_latched": raw.get("native_original_success_latched")})
    assert seen == set(registered)
    totals = Counter()
    for counts in groups.values():
        totals.update(counts)
    stats = {name: {**dict(counts), "registered_success": wilson(counts["newly_satisfied"], counts["registered"]),
        "executed_success": wilson(counts["newly_satisfied"], counts["executed"])} for name, counts in groups.items()}
    report = {"job": 4340, "complete": True, "cohort": "selection", "qualification_authorized": False,
        "new_training_rows": 0, "manifest": {"path": str(REMOTE_ROOT / MANIFEST_REL), "sha256": MANIFEST_SHA},
        "source": plan["source_snapshot"], "ledgers": ledgers, "total": dict(totals), "by_type": stats,
        "registered_success": wilson(totals["newly_satisfied"], totals["registered"]),
        "executed_success": wilson(totals["newly_satisfied"], totals["executed"]),
        "verifier": {"precision": None, "recall": None, "agreement": None,
            "unmeasured": totals["public_null"], "reason": "all executed endpoint verdicts null; no measured confusion denominator"},
        "setup_scope": "open s0/s2 close setup failed; all ten registered requests retained; do not treat nonconforming setup as confirmation",
        "records": records}
    (out / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    (out / "public_artifact_manifest.json").write_text(json.dumps({"source": "recorded public measurement/capture refs only",
        "job": 4340, "artifacts": [{"path": p, "sha256": h} for p, h in sorted(refs.items())]}, indent=2) + "\n")
    (out / "summary.md").write_text(
        "# 4340 微波炉公共父绑定 current160 原10选择批\n\n"
        "五片完整10记录，无基础设施失败和执行异常；新端点4/10（40%，Wilson 16.8–68.7%），真实first执行4/9。"
        "open 1/5，close 3/5；open s0父实体绑定缺失，open s0/s2的close setup未满足，全部保留。\n\n"
        "9个真实first公共判定全部unmeasured/null，precision/recall/一致率均不可计算；没有将null改false。"
        "close s0只有agentview测到固定frame；after两视角moving面法向相差约90度，融合拒绝为null。"
        "其余主要缺静态frame，open before还缺moving面。SOURCE571严格判据未放宽。\n\n"
        "setup+first共14次160块（2240块、11200请求及实际5步控制），无native success截断。"
        "这不是确认批；无新训练行、不授行业门槛或冻结资格。所有公共RGB-D/分割点云引用在public_artifact_manifest，逐次证据在report。\n")
    print(json.dumps({"report": str(out / "report.json"), "sha256": sha(out / "report.json"),
        "counts": dict(totals), "public_artifacts": len(refs)}))


if __name__ == "__main__":
    main()
