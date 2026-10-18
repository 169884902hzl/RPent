# Copyright 2026 Zhilun Hu.
# SPDX-License-Identifier: Apache-2.0
"""Publish the current prefix-label proof without reading shared history."""
import fcntl
import hashlib
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

root = Path('/public/home/sunyihan/rpent_libero_eval')
base = root / 'coordination/bounded_skills_20261016'
receipt = base / 'reports/coord_prefix_judge9_append_20261018.json'
assert not receipt.exists(), 'This update is already recorded'
proof = base / 'reports/offline_prefix_9471_120_CPU_20261018.json'
labels = json.loads(proof.read_text())
assert labels['source_commit'].startswith('8966ce8') and labels['oracle_mismatches'] == 0
assert labels['oracle_positions'] == 4 and labels['physics_steps'] == 0
report = base / 'progress_prefix_judge9_and_door_identity_20261018.md'
message = f'''
[Codex3 | {datetime.now(ZoneInfo('America/Los_Angeles')).isoformat()} | 10:05 answers and judge9 capture]
1. The five10:05 items are answered in {report}, SHA256 {hashlib.sha256(report.read_bytes()).hexdigest()}: function-level profile/cache conclusions; common bowl-init2 repair and same-command physical double success9022; CPU arbitrary-prefix API; nonsemantic catalog order; last3detailed receipts.
2. New source8966ce8 / private judge9 actual capture9471_120 matches all4online oracle positions in legal,rule_acceptable,selected,zero mismatches. A constructed alternative nudge prefix also labels. Source context81,393,458bytes; CPU times1.426/8.807/12.234/14.348s and9.608s for the alternative. Proof {proof}, SHA256 {hashlib.sha256(proof.read_bytes()).hexdigest()}. These are conditional rules,not physical branch success or actual model outputs.
3. Codex2 can fill unknown positions using annotate_prefix(state,request,prefix) when the matching private measured context exists; historical26requests/59unknown without that context remain unsupported. Legal is exactly public legal_after; no planner recomputation for legal. Contexts/private rules stay outside model-visible requests. Keep old-source26position evidence separate from judge9. Public bounded-skills/3 and public-request-legal/2 unchanged.
4. Representative request46.782s is dominated by contact search18.913s,cloud/IK17.987s,trajectory preparation14.917s(inclusive,overlapping). Single refresh5.821-7.481s; repeated segmentation and entity measurement explain the larger accumulated perception time. Same-capture pixels/clouds/exact-mesh queries can cache. Per-candidate processes are not independent because IK warm starts and caches are shared; no numeric-changing parallelism or target-only refresh was enabled. Full top15 tables and source pstats hashes accompany the report.
5. Microwave-open9470_140 remains a physical failure. CPU history-retention test recovered0/6later wrist frames. Same-instant cross-view plus overview tracking recovers3planes,but overlay inspection shows a fixed CONTROL PANEL,not the door. Do not use this as endpoint evidence or deploy it as a repair. Reports {base}/reports/microwave9470_140_{{history_retain,crossview}}_CPU_20261018.json retain the diagnostics. Fixed-base physical replay9473_120,original upper-bound9248,and startup-gated real-box9472 continue under their own immutable sources; task success is not inferred from startup or Slurm completion. No training,no freeze; confirmation exclusions permanent. node02only,nice500,cap3whenCodex2queues,otherwise fourth-card borrowing permitted; protected and held jobs unchanged.
'''
raw = message.encode()
path = Path('/public/home/sunyihan/rd_instruction_20260923/COORDINATION.md')
with path.open('ab') as stream:
    fcntl.flock(stream, fcntl.LOCK_EX)
    stream.seek(0, 2)
    start = stream.tell()
    stream.write(raw)
    stream.flush()
    end = stream.tell()
with path.open('rb') as stream:
    stream.seek(start)
    assert stream.read(len(raw)) == raw
record = {'path': str(path), 'start': start, 'end': end, 'bytes': len(raw),
    'sha256': hashlib.sha256(raw).hexdigest(), 'source_commit': labels['source_commit'],
    'proof': str(proof), 'report': str(report)}
receipt.write_text(json.dumps(record, indent=2) + '\n')
print(json.dumps(record))
