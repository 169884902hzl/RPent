"""Replay the staged gate on job4516's explicit public frames and action traces."""

import copy
import gzip
import hashlib
import json
from pathlib import Path

from robots.libero.v5_microwave_capture import public_endpoint_candidate, stable_public_endpoint_candidates


ROOT = Path(__file__).resolve().parent
INPUT = ROOT.parent / "microwave4516_wrist_roi_close_CPU_20261008/records.json.gz"
INPUT_SHA = "fb7fe5affb61491e9a5c655f78b6065720b0cfde47a0677b0c3c5b40b9ac72b6"


def ref(path):
    return {"path": str(path.resolve()), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


if __name__ == "__main__":
    if ref(INPUT)["sha256"] != INPUT_SHA:
        raise ValueError("registered4516 input changed")
    saved = json.loads(gzip.decompress(INPUT.read_bytes()))
    chunks = [trace for trace in saved["motion_evidence"] if trace.get("name") == "vla_act_chunk"]
    counts = [trace["executed_action_count"] for trace in chunks]
    if len(counts) != 40 or any(type(count) is not int or count <= 0 for count in counts):
        raise ValueError("measured forty-block controls missing")
    history, rows = [], []
    for record in saved["public_records"]:
        if record["phase"] != "probe":
            continue
        block, frame = record["chunks"], record["frames"][0]
        candidate = public_endpoint_candidate(frame, "close")
        if candidate["endpoint_candidate"]:
            history.append({"frame": frame, "candidate": copy.deepcopy(candidate),
                            "executed_controls": sum(counts[:block])})
            history = history[-3:]
            evidence = stable_public_endpoint_candidates(history)
            if evidence["reason"] in ("endpoint_candidate_still_moving", "independent_fixed_frame_not_stable"):
                history = history[-1:]
        else:
            history = []
            evidence = {"withdrawal_admitted": False, "stop_admitted": False,
                        "reason": "current_endpoint_candidate_not_measured"}
        rows.append({"block": block, "source_step": frame["source_step"],
            "executed_controls": sum(counts[:block]), "endpoint_candidate": candidate["endpoint_candidate"],
            "relative_angle_deg": candidate.get("relative_angle_deg"), "staged_confirmation": evidence,
            "prefix_precedes_original_withdrawal": block <= 36})
    rejected = next(row for row in rows if row["block"] == 36)
    if not rejected["endpoint_candidate"] or rejected["staged_confirmation"]["withdrawal_admitted"]:
        raise ValueError("real4516 block36 premature withdrawal was not prevented")
    output = ROOT / "recompute4516.json"
    if output.exists():
        raise FileExistsError(output)
    output.write_text(json.dumps({"version": "microwave4516-staged-public-recompute/1-dev",
        "input": ref(INPUT), "script": ref(Path(__file__)), "public_probe_records": len(rows),
        "actual_executed_contact_controls": sum(counts), "block36": rejected,
        "withdrawals_admitted_on_recorded_frames": sum(row["staged_confirmation"]["withdrawal_admitted"] for row in rows),
        "physical_counterfactual_success_claimed": False,
        "limitation": "Frames after block36 follow the old intervening withdrawal; they cannot predict the new physical trajectory.",
        "private_labels_used_by_replay": False, "qualification": False, "rows": rows}, indent=2) + "\n")
    print(json.dumps({"output": ref(output), "block36": rejected, "new_physical_trials": 0}))
