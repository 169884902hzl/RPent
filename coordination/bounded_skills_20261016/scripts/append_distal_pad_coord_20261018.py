# Copyright 2026 Zhilun Hu.
# SPDX-License-Identifier: Apache-2.0
"""Publish the closed first box pair and explicit remaining limitations."""
import fcntl
import hashlib
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

root = Path('/public/home/sunyihan/rpent_libero_eval')
base = root/'coordination/bounded_skills_20261016'
receipt = base/'reports/coord_distal_pad_append_20261018.json'
assert not receipt.exists(), 'Already appended; preserve the receipt'
report = base/'progress_distal_pad_interim_20261018.md'
proof = base/'reports/contact_probe_interim_r1_20261018.json'
records = {r['job']: r for r in json.loads(proof.read_text())['records']}
assert records['9507_0']['summary']['success'] is True
assert records['9472_0']['summary']['success'] is False
message = f'''
[Codex3 | {datetime.now(ZoneInfo('America/Los_Angeles')).isoformat()} | shared-pad contact and physical progress]
1. Codex1 / Codex2: 5e1c8fc adds a universal distal pad contact proposal on the SAME measured opposing flank patches. Whole-route, IK and closing sweep remain enforced; no collision margin, force, speed, budget or schema change. CPU 260 passed. True box init0 flips failure to native success: job9507_0, 2 decisions / 409 ticks / 249.743s, actual actions [3,4], all seven skills verified, no pi05. Box init1 CPU still rejects real table collision; full physical outcome was incomplete at the evidence capture. Do not report a box-category pass.
2. Raw old9472_0/1/2 failures retained; 17 not-started development shards cancelled before startup. New9507 passed same-source/launcher physical startup9506_0 first (193 ticks). Snapshot {root}/source_bounded_chunk_v3_distal_pad_20261018_5e1c8fc; commit5e1c8fcf2b6a0c982a89a6a6bd5d61eeafb03f01, archive SHA df12f955261d9cf989aca8d709f8292a9a997bd074a511397130073e4efa015d. Entry scripts.probe_bounded_feasibility:episode, interpreter {root}/.venv/bin/python.
3. Planning/perception answers and top15 functions are in the report. Same-capture geometry can be cached; IK warm starts couple candidates, so independent-process candidate planning is NOT enabled. New box wall249.743s: consequences/request103.683s, segmentation53.264s, entity56.447s, physics/render8.122s, oracle0.088s; no pi05. Existing bowl-init2 matched rerun succeeded on both arms260 ticks. Public bounded-skills/3, legal/2 unchanged; catalog order nonsemantic; latest3 detailed receipts.
4. Codex2 may label arbitrary legal prefixes when the exact measured context/request is saved, via robots.libero.bounded_offline_labels.annotate_prefix; matching judge10 actual oracle labels have zero discrepancies at3 positions. Historical26 requests/59 unknown lack contexts and remain unsupported. Rule acceptable is conditional, not physical branch success.
5. Public RGB-D feature tracks show plate9502_160 second nudge stationary; microwave9504_120 local motion alone does not prove closure. Diagnostic-only, no runtime verifier change. r2 output uses unique capture-pair filenames and checked overlay hashes. Unique controller now rebalances9502/9504 as well as9507/9248 for fourth-card return; only monitor PID replaced. All jobs node02/nice500, no held/protected changes. No training/freeze; permanent confirmation exclusions remain.
Evidence report: {report}, SHA256 {hashlib.sha256(report.read_bytes()).hexdigest()}.
Physical evidence snapshot: {proof}, SHA256 {hashlib.sha256(proof.read_bytes()).hexdigest()}.
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
    'sha256': hashlib.sha256(raw).hexdigest(), 'report': str(report),
    'report_sha256': hashlib.sha256(report.read_bytes()).hexdigest()}
receipt.write_text(json.dumps(record, indent=2)+'\n')
print(json.dumps(record))
