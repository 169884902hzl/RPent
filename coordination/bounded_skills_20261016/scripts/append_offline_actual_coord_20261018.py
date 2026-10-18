# Copyright 2026 Zhilun Hu.
# SPDX-License-Identifier: Apache-2.0
"""Deliver actual-capture offline-prefix checks through shared coordination."""
import fcntl
import hashlib
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

root = Path('/public/home/sunyihan/rpent_libero_eval')
base = root/'coordination/bounded_skills_20261016'
path = base/'reports/offline_prefix_9046_120_CPU_20261018.json'
report = json.loads(path.read_text())
assert report['oracle_positions'] == 4 and report['oracle_mismatches'] == 0
assert report['physics_steps'] == 0 and not report['gpu_used']
measurements = [{'kind': r['kind'], 'elapsed_s': r['elapsed_s'], 'status': r['label']['status'],
    'legal_n': len(r['label']['legal']), 'acceptable_n': len(r['label']['rule_acceptable'])}
    for r in report['records']]
text = f"""
[Codex3 | {datetime.now(ZoneInfo('America/Los_Angeles')).isoformat()} | actual CPU arbitrary-prefix evidence for Codex2/Codex1]
Completed actual-launcher check: startup9046_120 executed305controls, saved one canonical request and hash-pinned private context. CPU annotate_prefix matches all4 online oracle positions exactly in legal/rule_acceptable/selected; a different, nonoracle nudge prefix also returns a nonempty valid acceptable set. Zero environment steps/GPU in the CPU audit. This is conditional rule annotation, not branch success or task qualification. Source c916ab11f0f97e591f6094d80db7f03f4f1264f4; snapshot {report['snapshot']}.
Codex2 can now use capture_annotation_state/save_annotation_state/load_annotation_state/annotate_prefix for NEW synchronous requests with matching capture-time context, including model-selected prefixes. Historical simulator pickle plus request alone still cannot reconstruct masks/routes/binding history faithfully; those unknowns remain unsupported. Prefetch capture is not yet exported. Keep snapshots private, never in model input. Public schema3/legal2 unchanged; last3 detailed receipts and nonsemantic candidate catalog order unchanged.
Measured cost: compressed context {report['snapshot_bytes']}bytes; capture/save wall7.616s in startup ledger. CPU per-prefix records: {json.dumps(measurements)}. Correctness established, bulk-label throughput remains expensive (9-51s/prefix); no claim of cheap annotation.
Evidence {path}; SHA {hashlib.sha256(path.read_bytes()).hexdigest()}; startup ledger {root}/results/bounded_skills/feasibility_20261017/job9046_120/episodes.jsonl. CPU interface script {base}/scripts/audit_offline_prefix_state_CPU_20261018.py. New source microwave full-pair9209 is queued; older9025/9026 remain separately identified. No training or confirmation-state reuse.
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
(base/'reports/coord_offline_actual_append_20261018.json').write_text(json.dumps(receipt, indent=2)+'\n')
print(json.dumps(receipt))
