"""Keep diagnostic native latches separate from final task and public truth."""
from collections import Counter
import datetime
import hashlib
import json
from pathlib import Path
from summarize_registered_grasp_v3r9 import pin, metric, confusion

ROOT = Path("/public/home/sunyihan/rpent_libero_eval")
BASE = ROOT / "results/harness_v5/moka_layout_skill76_CPU_20261008"
plan_path = BASE / "preparation_r2/moka_layout76.json"
plan = json.loads(plan_path.read_text())
rows, inputs = [], []
for job in (5476, 5525):
    for path in sorted((BASE / f"smoke10/job{job}").glob("part*/probe/episodes.jsonl")):
        data = path.read_bytes()
        inputs.append(pin(path))
        for line_no, line in enumerate(data.splitlines(), 1):
            if not line.strip():
                continue
            raw = json.loads(line)
            public = raw.get("public_placement_verdict")
            # This producer saves a bool, not a {verified: bool} dictionary.
            if type(public) is not bool:
                public = None
            receipt = raw.get("public_receipt_before_private_metrology") or {}
            final = raw.get("private_original_task_status_after") or {}
            result = raw.get("result") or {}
            rows.append({"case": raw["case"]["name"], "layout_seed": raw["case"].get("layout_seed"),
                "state_sha256": raw["case"].get("state_sha256"), "input": str(path),
                "input_sha256": pin(path)["sha256"], "line": line_no,
                "row_sha256": hashlib.sha256(line).hexdigest(),
                "public": public, "receipt_place_verified": receipt.get("place_verified"),
                "public_verification": receipt.get("verification"), "public_reason": receipt.get("verification_reason"),
                "official_final": final.get("done"), "official_subtask_success": raw.get("official_subtask_success"),
                "native_success_latched": result.get("termination_category") == "success",
                "termination_category": result.get("termination_category"), "wall_s": raw.get("wall_s"),
                "chunks": raw.get("chunks"), "infrastructure_failure": raw.get("case_had_infrastructure_failure", False),
                "training_allowed": False, "classification": "old5801xx_layout_diagnostic_not_confirmation"})
registered = {c["name"] for c in plan["cases"]}
invalid = set(plan["preparation_invalid_case_names"])
startup = "moka_layout_580125"
expected = registered - invalid - {startup}
names = [r["case"] for r in rows]
if len(names) != len(set(names)) or set(names) - expected:
    raise ValueError("duplicate/unregistered formal result")
report = {"generated_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    "plan": pin(plan_path), "summary_source": pin(Path(__file__)), "inputs": inputs,
    "classification": "old_layout_diagnostic_not_current920xxxx_confirmation", "qualification_allowed": False,
    "registered_n": len(registered), "invalid_retained": sorted(invalid), "startup_separate": startup,
    "formal_expected": len(expected), "formal_completed": len(rows), "missing": sorted(expected - set(names)),
    "counts": {key: dict(Counter(str(r[key]) for r in rows)) for key in (
        "official_final", "official_subtask_success", "native_success_latched", "public", "receipt_place_verified", "termination_category")},
    "final_success_registered_denominator": metric(sum(r["official_final"] is True for r in rows), len(expected)),
    "public_verifier_final_truth": confusion(rows, "official_final"),
    "latched_success_but_final_false": [r["case"] for r in rows if r["native_success_latched"] and r["official_final"] is False],
    "public_summary_v1_error": "v1 wrongly expected a dictionary; stored public_placement_verdict is bool or null",
    "old_summary_and_original_records_preserved": True, "training_allowed": False}
out = ROOT / "coordination" / ("moka5476_diagnostic_v2_" + datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ"))
out.mkdir()
(out / "rows.jsonl").write_text("".join(json.dumps(r, sort_keys=True) + "\n" for r in rows))
(out / "summary.json").write_text(json.dumps(report, indent=2) + "\n")
print(str(out))
print(json.dumps({k:v for k,v in report.items() if k != "inputs"}, indent=2))
