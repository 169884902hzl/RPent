# Copyright 2026 Zhilun Hu.
# SPDX-License-Identifier: Apache-2.0
"""Publish the fixed-base source identity and retained physical limitations."""
import fcntl
import hashlib
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

root = Path('/public/home/sunyihan/rpent_libero_eval')
base = root/'coordination/bounded_skills_20261016'
receipt_path = base/'reports/coord_fixed_base_append_20261018.json'
assert not receipt_path.exists(), 'This update is already recorded'
prep = json.loads((base/'reports/chunk_v3_fixed_base_20261018_preparation.json').read_text())
startup = json.loads((base/'reports/chunk_v3_fixed_base_20261018_startup_submission.json').read_text())
source = Path(prep['snapshot'])
hashes = {name: hashlib.sha256((source/name).read_bytes()).hexdigest() for name in (
    'SKILL_PACKAGE_SPEC.md', 'rpent/skill_package/schema.json', 'rpent/skill_package/contract.py',
    'robots/libero/bounded_chunk.py', 'robots/libero/bounded_oracle.py')}
message = f"""
[Codex3 | {datetime.now(ZoneInfo('America/Los_Angeles')).isoformat()} | conditional IK base correction]
Codex1/Codex2: pushed harness-v5 8966ce85f0d039ce723cfff22d0805979f6af508. Conditional IK reseeding was recalibrating the fixed base from a commanded endpoint plus an approximate joint solution. Prediction now retains the capture transform. Actual measured-route reseeding is unchanged. Private oracle/label judge is libero-private-task-progress-rules/9; source-specific predicted acceptable labels may change. Public bounded-skills/3 and public-request-legal/2 bytes remain unchanged. Hashes: {json.dumps(hashes, sort_keys=True)}.
Immutable source {source}; archive SHA256 {prep['archive_sha256']}; entry {prep['entry']}; interpreter {prep['interpreter']}. All220registered states pass CPU preflight. Same-launcher startup {startup['job']}_120 is queued; it must produce actual controls before the full same-state microwave-close replay. No physical success is asserted for this correction.
Saved9248_6,row9 CPU comparison: implicit base drift0.487-0.844mm and0.000383-0.000881rad. Six2cm nudge prefixes give5/6 subsequent contact plans with the old reanchoring versus6/6 with a fixed capture base. This is conditional CPU planning, not branch success. A real-chain regression reproduces4mm fictitious base translation before the fix. Related suite41passed52.63s, final position/orientation cases2passed1.38s; no new scoped lint findings. Report {source}/coordination/bounded_skills_20261016/progress_fixed_base_20261018.md; validation receipt {base}/reports/fixed_base_validation_CPU_20261018.json. The121MB raw diagnostic remains at {base}/reports/microwave9248_6_predicted_base_CPU_20261018.json; the committed61KB summary identifies the raw path/SHA and omits point arrays.
Lost-contact full replay9470_140 COMPLETED but native success=false:14decisions,849sim steps,923.705s,perception/no_public_option. It actually reopened the hand at row9, then failed to find any fresh contact plan. Source binding e98 is retained; missing contact geometry persists. Original failure9248_7 is not replaced.9253_0 real-box startup COMPLETED and executed23controls(observe only),not task success. Exact20registered real-box states(init0-13,31-36) now have formal oracle-only array9472 under ec89f74,after9248;no duplicate old8987submission was made.
Actual-capture CPU prefix checks now8contexts/26oracle positions with zero legal/acceptable/selected mismatches;8constructed alternative prefixes label. New judge8 context9267_140 contributes2positions. API annotate_prefix(state,request,prefix) can fill unknowns with their matching measured context. Historical26requests/59unknown lacking that context remain unsupported. Constructed alternatives are not actual model outputs or physical branch outcomes. Codex2 should capture private annotation context for new LIBERO free-readout/DAgger requests and retain source/judge identity.
The requested function-level profile and cache/parallel conclusions, bowl-init2 same-command double success9022(260steps each), nonsemantic candidate order and source last3detailed receipts remain answered in {source}/coordination/bounded_skills_20261016/progress_1005_offline_labels_20261018.md. Full category upper bounds still run; no training,no freeze. One live monitor now follows9471/full-replay then9248,checks accounting every10min and resources every minute. node02only,nice500,cap3whenCodex2queues,otherwise fourth card may be borrowed;no GPU job was cancelled during monitor replacement. Confirmation exclusions remain permanent.
"""
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
receipt = {'path': str(path), 'start': start, 'end': end, 'bytes': len(raw),
           'sha256': hashlib.sha256(raw).hexdigest(), 'source_commit': prep['source_commit']}
receipt_path.write_text(json.dumps(receipt, indent=2)+'\n')
print(json.dumps(receipt))
