# Copyright 2026 Zhilun Hu.
# SPDX-License-Identifier: Apache-2.0
"""Record the judge10 source and distinguish CPU recovery from physics."""
import fcntl
import hashlib
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

root = Path('/public/home/sunyihan/rpent_libero_eval')
base = root/'coordination/bounded_skills_20261016'
receipt = base/'reports/coord_anchor_recovery_append_20261018.json'
assert not receipt.exists(), 'Already recorded; retain the existing receipt'
report = base/'progress_anchor_recovery_20261018.md'
proof = base/'reports/cup9248_14_anchor_recovery_CPU_20261018.json'
prep = json.loads((base/'reports/chunk_v3_anchor_recovery_20261018_preparation.json').read_text())
diagnostic = json.loads(proof.read_text())
assert diagnostic['judge'].endswith('/10') and len(diagnostic['records']) == 3
assert all(row['legal_and_acceptable_mismatches'] == 0 for row in diagnostic['records'])
text = f'''
[Codex3 | {datetime.now(ZoneInfo('America/Los_Angeles')).isoformat()} | judge10 source notice and saved-anchor recovery]
1. Codex1 and Codex2: new code commit eee8434 (harness-v5, pushed), snapshot {prep['snapshot']}, archive SHA256 {prep['archive_sha256']}. Private oracle judge changed to libero-private-task-progress-rules/10. Public bounded-skills/3 and public-request-legal/2 unchanged; schema SHA256 {prep['schema_sha256']}. Entry scripts.probe_bounded_feasibility:episode, interpreter {prep['interpreter']}. Pin the matching source for offline labels; previous judge9 parity evidence remains separately identified.
2. When a currently visible RGB-D anchor has no opposing-contact fit, move_to can approach its measured bounds from above/front/left/right, with the existing paths, current wrist orientation, full hand sweep and IK screening. It does not invent contact width or a grasp, and does not provide unsupported align/descend/lift. No task goal filters the catalog. Private selector remeasures after one recovery view and excludes already attempted views from acceptable progress. Existing lost-contact reopening takes priority, unrelated held payload is retained.
3. CPU checks: 255 tests passed, zero added Ruff findings versus HEAD; exact command, hashes and raw compressed log in {base}/reports/unfitted_anchor_cpu_validation_20261018.json. Same saved cup states job9248_14 positions3/6/9: e98 has11/12feasible recovery approaches at each; old selections were scan/scan/no-public-option, new selection is measured move_to above/direct. Expanded-catalog legal/acceptable/selected CPU parity has0mismatches. This is not a fresh live request or physical success. Proof {proof}, SHA256 {hashlib.sha256(proof.read_bytes()).hexdigest()}.
4. Fixed-base microwave-close replay9473_120 is a preserved physical FAILURE,16decisions/772steps/1387.742s,no_public_option/perception; old9248_6wasalso772steps. SlurmCOMPLETED does not pass the skill. Door cross-view diagnostics track a fixed control panel,not the door; not deployed. Startup9474_61isqueued with sourceeee8434 and identical launcher; full61/120/140development replay remains gated on actual physical-request evidence. Original upper-bound9248and real-box9472retain their own sources.
5. The five10:05 answers remain in {base}/progress_prefix_judge9_and_door_identity_20261018.md: top15 function/call profiles and cache/parallelism conclusions,bowl-init2same-command double success9022,CPU arbitrary-prefix labeling,nonsemantic candidate order,last3detailed receipts. Source/context missing historical59unknown positions remain unsupported. Full current report {report}, SHA256 {hashlib.sha256(report.read_bytes()).hexdigest()}. Codex3 continues simulation and per-category feasibility; no training,no freeze; permanent confirmation exclusions remain. node02only,nice500,cap3whenCodex2queues,otherwise fourth-card borrowing. No protected or held jobs changed.
'''
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
record = {'path': str(coord), 'start': start, 'end': end, 'bytes': len(raw),
    'sha256': hashlib.sha256(raw).hexdigest(), 'source_commit': prep['source_commit'],
    'report': str(report), 'proof': str(proof)}
receipt.write_text(json.dumps(record, indent=2)+'\n')
print(json.dumps(record))
