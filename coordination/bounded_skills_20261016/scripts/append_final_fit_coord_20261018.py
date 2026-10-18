# Copyright 2026 Zhilun Hu.
# SPDX-License-Identifier: Apache-2.0
"""Append the closed physical pairs and bounded registration evidence."""
import fcntl
import hashlib
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

root = Path('/public/home/sunyihan/rpent_libero_eval')
base = root/'coordination/bounded_skills_20261016'
reports = base/'reports'
wall_path = reports/'wall_payload_interval_pair_20261018.json'
wall = json.loads(wall_path.read_text())
assert len(wall['rows']) == 6 and all(row['instrumented'] for row in wall['rows'])
rows = [{key: row[key] for key in ('job', 'case', 'arm', 'success', 'wall_s',
    'perception_s', 'consequence_planning_s', 'simulation_step_render_s',
    'oracle_decision_s', 'private_label_capture_s')} for row in wall['rows']]
assert sum(row['success'] for row in rows) == 4
evidence_names = ['9026_registration_path_CPU_20261018.json',
    '9026_16_final_fit_screens_CPU_20261018.json',
    '9026_19_final_fit_screens_CPU_20261018.json',
    '9026_final_fit_added_pixels_CPU_20261018.json',
    'final_fit_CPU_validation_20261018.json',
    'chunk_v3_payload_interval_20261018_paired_latest.json', wall_path.name]
evidence = [{'path': str(reports/name),
    'sha256': hashlib.sha256((reports/name).read_bytes()).hexdigest()} for name in evidence_names]
text = f"""
[Codex3 | {datetime.now(ZoneInfo('America/Los_Angeles')).isoformat()} | Final-fit CPU repair and closed physical pairs | Codex1/Codex2]
1. Source e5bbb18 is pushed to harness-v5: ICP checks its final returned transform instead of rejecting an intermediate optimization iterate. The same 0.1 rad / 15 mm limits, overlap/improvement tests, 3 mm continuity, 4 mm stationary veto and collision clearance are retained.
2. Saved-public CPU screens for bowl init16/19 now pass all 32 formerly rejected poses and 24 complete nudge routes. Membership adds 12 current pixels and removes none; independent CPU simulation restoration identifies all 12 as bowl pixels, zero control steps. That private identity is diagnostic only. No physical success is claimed for this source yet.
3. Source 87ef92e pair 9211 init10/14 is closed, all four arms succeed. Init10 new/old: 6/7 decisions, 1041/434 simulation steps, 740.839/627.727 wall seconds. Init14: 2/4 decisions, 316/289 steps, 355.908/422.763 seconds. New chunks are not uniformly faster. Init10 adds a 23-tick wrist scan and a 610-tick reapproach after release; the old arm reapproaches in 88 ticks. Further diagnosis continues.
4. Source c916ab1 microwave-close pair 9209 is closed, both arms fail: new 16 decisions/772 steps, legacy 20/585. The target-margin change has not established task-level recovery. Failures are retained.
5. Wall accounting now separates private label capture, 12.950–107.839 seconds across these six arms. Public schema/contract unchanged. CPU arbitrary-prefix labeling supports matching captured contexts; Codex2's 26 old requests/59 unknown positions lack those contexts and remain unsupported. Detailed source history stays at three receipts, and candidate order has no semantics.
New snapshot {root}/source_bounded_chunk_v3_final_fit_20261018_e5bbb18; archive SHA cd2f0d661c0ae61f39a11a843667824c7122daa36ed67a2f2d86b3d9f7eb5900. Entry scripts.probe_bounded_feasibility:episode; interpreter {root}/.venv/bin/python. CPU preflight covers 220 registered original states. Startup 9213_16 must prove a real physical request before the same-launcher 16/19 paired array is admitted. No training, confirmation admission or behavior freeze.
Schema bounded-skills/3 SHA df17c6c49e4992247ab8ff37ebf528f893ac6887ea8cf946e25668aca110b4aa; public-request-legal/2 contract SHA 7e898e3bd4e8f4c7a4e9951d897cc1fe682037ee35ee4d6d5cc1f52606e2f49c.
Closed exclusive wall buckets: {json.dumps(rows)}
Evidence: {json.dumps(evidence)}
Report {base}/progress_final_fit_20261018.md. Original ff00387 oracle cohort stays a separate source/denominator; pi0.5 remains disabled. Bowl init17 is a separate pre-lift failure; CPU registration diagnosis and a regression test are in progress, not a claimed physical fix.
"""
raw = text.encode()
coord = Path('/public/home/sunyihan/rd_instruction_20260923/COORDINATION.md')
with coord.open('ab') as stream:
    fcntl.flock(stream, fcntl.LOCK_EX)
    stream.seek(0, 2)
    start = stream.tell()
    stream.write(raw)
    stream.flush()
    end = stream.tell()
with coord.open('rb') as stream:
    stream.seek(start)
    assert stream.read(len(raw)) == raw
receipt = {'path': str(coord), 'start': start, 'end': end, 'bytes': len(raw),
    'sha256': hashlib.sha256(raw).hexdigest()}
(reports/'coord_final_fit_append_20261018.json').write_text(json.dumps(receipt, indent=2)+'\n')
print(json.dumps(receipt))
