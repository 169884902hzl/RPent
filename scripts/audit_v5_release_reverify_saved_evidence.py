"""Replay explicit saved public sensors to audit a release request, not success."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import fields
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from robots.libero.v5_runtime import V5Executor
from robots.libero.v5_state import Candidate, Entity


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def entity(record: dict) -> Entity:
    return Entity(**{field.name: record[field.name] for field in fields(Entity)
                     if field.name in record})


def local_path(root: Path, remote: str) -> Path:
    prefix = "/public/home/sunyihan/rpent_libero_eval/"
    if not remote.startswith(prefix):
        raise ValueError(f"unexpected saved evidence path: {remote}")
    return root / remote[len(prefix):]


def audit(root: Path, diagnosis_path: Path) -> dict:
    diagnosis = json.loads(diagnosis_path.read_text())
    records = [record for record in diagnosis["records"] if
               "FN:endpoint_empty_gripper_closed_release_history_not_checked" in record["categories"]]
    if len(records) != 2:
        raise ValueError("expected the two explicitly diagnosed endpoint-closure cases")
    results = []
    for record in records:
        ledger = local_path(root, record["captured_ledger"])
        if sha(ledger) != record["ledger_sha256"]:
            raise ValueError(f"saved ledger hash changed: {ledger}")
        raw = json.loads(ledger.read_text().splitlines()[record["line"] - 1])
        if raw["case"]["name"] != record["case"]:
            raise ValueError("saved case identity does not match the explicit line")
        attempt = raw["first_attempt"]
        action = Candidate.from_text(attempt["selected"])
        measured = attempt["verification_measurements"]
        old = attempt["public_before"]
        objects = {item["id"]: entity(item) for item in old["entities"]}
        target = entity(measured["target"])
        objects[target.id] = target
        samples = [entity(measured[key]) for key in ("first", "second")]
        motions = [row for row in attempt["motion_evidence"] if row.get("name") == "vla_act_chunk"]
        if len(motions) != record["policy_chunks"]:
            raise ValueError("saved chunk count differs from the diagnosed action")
        clock = [0.]
        refresh_count = [0]
        release_requests = []
        p = SimpleNamespace(_last_obs_gripper=old["robot"]["gripper_opening"],
                            _last_obs_eef_pos=np.asarray(old["robot"]["eef_xyz"]),
                            env=SimpleNamespace(terminated=False, truncated=False))
        remaining = iter(motions)
        def chunk(_prompt):
            motion = next(remaining)
            p._last_obs_gripper = float(motion["gripper_opening"])
            p._last_obs_eef_pos = np.asarray(motion["final_eef_pos"])
        def request_release():
            # CPU audit cannot actuate or invent the future opening/image.
            release_requests.append({"request": "release", "physically_executed": False})
            return release_requests[-1]
        p._vlm_chunk, p.release = chunk, request_release
        scene = SimpleNamespace(entities=objects, last_measurement_s={},
            view_axes=old.get("view_axes", ((1., 0., 0.), (0., -1., 0.))))
        def refresh(_names, **_kwargs):
            refresh_count[0] += 1
            index = refresh_count[0] - 1
            if index < 2:
                sample = samples[index]
                scene.entities[sample.id] = sample
                clock[0] = 0. if index == 0 else measured["interval_s"]
            else:
                scene.entities.pop(action.object, None)
            scene.last_measurement_s[samples[0].name] = clock[0]
        scene.refresh = refresh
        executor = V5Executor.__new__(V5Executor)
        executor.scene, executor.p = scene, p
        executor.target_cache_v1, executor.strict_place_v6 = True, True
        executor.target_cache = {target.id: target}
        executor.subtask_release_reverify_v8 = True
        executor.motion_trace_v1 = False
        executor.max_chunks = len(motions)
        executor.motion_evidence = []
        executor.held, executor.held_offset = attempt["held_before"], np.zeros(3)
        executor._refresh = refresh
        executor.capture = lambda: None
        receipt = {}
        with patch("robots.libero.v5_runtime.time.perf_counter", lambda: clock[0]), patch(
                "robots.libero.v5_runtime.time.sleep", lambda elapsed: clock.__setitem__(0, clock[0] + elapsed)):
            executor.execute_subtask(action, receipt)
        evidence = executor.last_verification_measurements["release_reverification"]
        if not evidence["triggered"] or len(release_requests) != 1 or receipt["place_verified"] is not None:
            raise AssertionError("saved public evidence must request release while future evidence remains unknown")
        results.append({
            "case": record["case"], "input_ledger": str(ledger), "ledger_sha256": sha(ledger),
            "line": record["line"], "historical_verdict_preserved": record["runtime_verdict_saved"],
            "triggered": evidence["triggered"], "geometry_passed": evidence["geometry_passed"],
            "fresh_frames": evidence["fresh_frames"], "open_events": evidence["release_history"]["open_events"],
            "release_requests": release_requests, "future_verdict": receipt["place_verified"],
            "future_verification_reason": receipt["verification_reason"], "before": evidence["before"],
        })
    return {"scope": "CPU release eligibility only; historical labels unchanged; no physical release or future measurement",
            "diagnosis": str(diagnosis_path), "diagnosis_sha256": sha(diagnosis_path), "records": results}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--diagnosis", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = audit(args.root.resolve(), args.diagnosis.resolve())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")


if __name__ == "__main__":
    main()
