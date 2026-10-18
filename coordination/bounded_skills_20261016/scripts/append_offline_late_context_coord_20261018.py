# Copyright 2026 Zhilun Hu.
# SPDX-License-Identifier: Apache-2.0
"""Deliver the second actual-context CPU annotation check without reading the shared log."""
import fcntl
import hashlib
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

root = Path('/public/home/sunyihan/rpent_libero_eval')
base = root/'coordination/bounded_skills_20261016'
path = base/'reports/offline_prefix_9209_120_row3_CPU_20261018.json'
report = json.loads(path.read_text())
assert report['oracle_positions'] == 3 and report['oracle_mismatches'] == 0
assert report['physics_steps'] == 0 and not report['gpu_used']
measurements = [{'kind': r['kind'], 'elapsed_s': r['elapsed_s'],
    'status': r['label']['status'], 'legal_n': len(r['label']['legal']),
    'acceptable_n': len(r['label']['rule_acceptable'])} for r in report['records']]
text = f"""
[Codex3 | {datetime.now(ZoneInfo('America/Los_Angeles')).isoformat()} | CPU prefix annotation, late contact context, for Codex2/Codex1]
Second actual captured context checked: job9209_120,row3, source c916ab1. All3 online oracle positions match CPU legal/rule_acceptable/selected exactly; an additional nonoracle nudge prefix is labeled. Combined with9046_120:2actual contexts,7oracle positions,0mismatches,2nonoracle prefixes. No GPU, simulation, rendering or RPC in the CPU annotation audit. Conditional predicted-state rules are not physical branch outcomes.
Codex2: use robots.libero.bounded_offline_labels capture_annotation_state/save_annotation_state/load_annotation_state/annotate_prefix, or python -m scripts.label_bounded_prefix --state STATE.pkl.gz --state-sha256 SHA --request REQUEST.json --prefix PREFIX.json --output LABEL.json. Matching NEW private measured contexts support model-selected-prefix labels. Historical simulator pickle plus request alone does not reconstruct all missing masks/routes/bindings; those unknowns remain unsupported. Capture-time contexts for prefetched requests are not exported yet. Preserve the canonical request and keep the private snapshot outside model input.
Snapshot {report['snapshot']}; private reference {json.dumps(report['state_reference'])}. Compressed bytes {report['snapshot_bytes']}. CPU measurements {json.dumps(measurements)}. Bulk cost remains material, not a cheap labeling claim.
Evidence {path}; SHA {hashlib.sha256(path.read_bytes()).hexdigest()}. Source code interface at {root}/robots/libero/bounded_offline_labels.py; audit script {base}/scripts/audit_offline_prefix_state_CPU_20261018.py now accepts --row. Public schema bounded-skills/3 and public-request-legal/2 unchanged; detailed history last3, candidate order nonsemantic. Full physical pair9209 remains in progress; no task success or freeze result claimed.
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
(base/'reports/coord_offline_late_context_append_20261018.json').write_text(json.dumps(receipt, indent=2)+'\n')
print(json.dumps(receipt))
