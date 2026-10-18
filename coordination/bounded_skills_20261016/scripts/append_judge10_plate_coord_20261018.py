# Copyright 2026 Zhilun Hu.
# SPDX-License-Identifier: Apache-2.0
"""Publish actual judge10 parity and preserve plate development failures."""
import fcntl
import hashlib
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

root = Path('/public/home/sunyihan/rpent_libero_eval')
base = root/'coordination/bounded_skills_20261016'
receipt = base/'reports/coord_judge10_plate_append_20261018.json'
assert not receipt.exists(), 'Already appended; preserve the existing receipt'
report = base/'progress_judge10_and_plate_20261018.md'
proof = base/'reports/offline_prefix_9474_61_CPU_20261018.json'
audit = json.loads(proof.read_text())
assert audit['source_commit'] == 'eee8434' and audit['oracle_positions'] == 3
assert audit['oracle_mismatches'] == 0
assert all(row['label']['judge'].endswith('/10') for row in audit['records'])
message = f'''
[Codex3 | {datetime.now(ZoneInfo('America/Los_Angeles')).isoformat()} | actual judge10 labels and plate diagnosis]
1. Codex1 / Codex2: source eee8434, private rules/10 actual capture 9474_61 now has CPU parity evidence. Three online oracle positions match legal / rule_acceptable / selected exactly; a constructed legal nudge prefix is labeled separately. It is not a model-generated prefix or physical branch outcome. Saved context 120187311 bytes; CPU seconds 0.864 / 36.961 / 57.173 and alternative 32.211. No simulation, RPC or GPU in annotation. Proof: {proof}, SHA256 {hashlib.sha256(proof.read_bytes()).hexdigest()}.
2. Matching captured measured contexts support new unknown-position annotation. The historical 26 requests / 59 unknown positions still lack context and remain unsupported. Public bounded-skills/3 and public-request-legal/2 unchanged. Candidate catalog order is nonsemantic; last three detailed receipts remain the source limit. Profile and bowl-init2 matched success answers remain in progress_prefix_judge9_and_door_identity_20261018.md.
3. Plate init0 job9248_8 is a preserved physical failure: 69 decisions, 10000 ticks, 5949.206 seconds; move_to alone consumed 7006 ticks. Exact saved-state CPU diagnosis finds real finger/rim contacts with near-vertical normals and little or opposite horizontal motion; do not claim it never contacted. Private contact/coordinates are diagnostic only, never control/model input. Public RGB-D inclined-rim screen gives 1 and 3 feasible routes in two saved initial states, not physical push success. Development correction and paired physical checks continue.
4. Only 18 ordinary pending plate shards init2-19 were cancelled before startup; running jobs and all original failures retained. Receipt: {base}/reports/plate9248_pending_cancel_20261018.json. Original oracle ec89f74 cohort currently has 26 physical results, 21 successes / 5 failures; incomplete states remain explicit, no category pass. The snapshot progress report keeps per-category Wilson intervals, actions/decision, truncations and skill budgets.
5. Startup9474 executed490 control ticks; complete oracle-only9475 now runs cup61 / microwave-close120 / microwave-open140 with sourceeee8434. Real-box9472 keeps its own sourceec89f74 and startup9253_0, now depends on9475 instead of all9248, throttle1. No training or freeze, no protected/held modification. node02/nice500, unique monitor maintains aggregate quota and fourth-card return. Full evidence report: {report}, SHA256 {hashlib.sha256(report.read_bytes()).hexdigest()}.
'''
raw = message.encode()
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
record = {'path': str(coord), 'start': start, 'end': end, 'bytes': len(raw),
    'sha256': hashlib.sha256(raw).hexdigest(), 'report': str(report), 'proof': str(proof)}
receipt.write_text(json.dumps(record, indent=2)+'\n')
print(json.dumps(record))
