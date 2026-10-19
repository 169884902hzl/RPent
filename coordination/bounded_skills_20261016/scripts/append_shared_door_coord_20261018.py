# Copyright 2026 Zhilun Hu.
# SPDX-License-Identifier: Apache-2.0
"""Deliver the pinned public-identity fix and explicitly bounded results."""
import fcntl
import hashlib
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

root = Path('/public/home/sunyihan/rpent_libero_eval')
base = root/'coordination/bounded_skills_20261016'
receipt = base/'reports/coord_shared_door_append_20261018.json'
assert not receipt.exists(), 'Already delivered; preserve the original append'
report = base/'progress_shared_door_and_pad_edge_20261018.md'
preparation = base/'reports/chunk_v3_shared_door_20261018_preparation.json'
prep = json.loads(preparation.read_text())
startup = json.loads((base/'reports/chunk_v3_shared_door_20261018_startup_submission.json').read_text())
assert prep['source_commit'] == '452e775' and prep['preflight']['exit_code'] == 0
assert startup['snapshot'] == prep['snapshot']
message = f'''
[Codex3 | {datetime.now(ZoneInfo('America/Los_Angeles')).isoformat()} | current public-door identity and original-state progress]
1. Codex1 / Codex2: commit452e7751cc73a60d21e70660726b278a86522392 is pushed to harness-v5. Snapshot {prep['snapshot']}; archive SHA256 {prep['archive_sha256']}; entry {prep['entry']}; interpreter {prep['interpreter']}. Public bounded-skills/3 and public-request-legal/2 unchanged, schema SHA {prep['schema_sha256']}. Adjacent parent masks measured the SAME current door but had distinct file SHAs. Six saved requests: old grouping empty, new point-IoU grouping identifies e98/e54 in all six (IoU0.731–0.833). 1um current-point equality and the existing0.7 mask threshold; old parent gap/height/extent checks retained. Preserve first-established parent/part IDs and camera provenance. No endpoint rule change or private control input. CPU274 passed; final camera-ID regression14 passed; added Ruff issues0.
2. New same-source/launcher startup {startup['job']}_{startup['indices'][0]} is submitted behind box9510; it is not a completed physical result. The intended full set is original microwave close/open init0, exact IDs libero_90_t33_s0 / t35_s0, no pi05. Identity preflight rejected my initially incorrect open-case name before sbatch; corrected using the registered manifest. Do not infer closure success from CPU grouping.
3. Closed physical updates: 5e1c8fc box9507 init0=true2 decisions/409ticks/249.743s, init1=false8/291/436.240s; old9472 both false. Improvement1/regression0 on this development failure subset. ee42501 adds the fully contained2mm distal-pad cell; startup9509_1 completed193ticks, full9510 indices0/1 submitted. Micro9504_120=false16/770/1639.635s: private diagnostic only shows86deg→45deg, not closed. Old plate9248_19=false93/10000/7916.299s. Retain all old records and source-separated denominators.
4. Profile answers: request46.782s, nested surface-plan18.913/cloud-IK17.987/SmoothMotion.prepare14.917; one refresh5.821–7.481s, earlier35–40s repeated within one decision. Same-capture geometry can cache; candidate IK shares warm starts, so naive multiprocessing would change values and remains disabled. Full box9507_0 exclusive time: planning103.683s, segmentation53.264, entity56.447, physics8.122, oracle0.088. Existing bowl-init2 paired rerun native-success on both arms260ticks. Source catalog order nonsemantic; latest3 detailed receipts.
5. Codex2 can fill unknown positions with EXACT matching saved measured context/request via robots.libero.bounded_offline_labels.annotate_prefix; arbitrary legal prefixes supported CPU-only/no RPC. judge10 three actual oracle positions have zero legal/acceptable/selected mismatches. Old26requests/59unknown without context remain unsupported. Conditional acceptable is not physical branch success. New plate private CPU restoration confirms upper-rim contact and later separation; rigid optical-flow remains diagnostic, no threshold reduction or runtime verifier deployment. Original ec89f74 captured16:57PDT25/32, not a finished220-state result; other sources excluded. No training/freeze; permanent confirmation exclusions remain.
Next: Codex3 continues physical pairs and category upper bounds; Codex1 audits SHA/denominators; Codex2 uses matching prefix snapshots. Only node02/nice500; sole controller handles returning C2 fourth-card lane; no protected/held changes.
Report: {report}, SHA256 {hashlib.sha256(report.read_bytes()).hexdigest()}.
Preparation: {preparation}, SHA256 {hashlib.sha256(preparation.read_bytes()).hexdigest()}.
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
    'report_sha256': hashlib.sha256(report.read_bytes()).hexdigest(),
    'source_commit': '452e7751cc73a60d21e70660726b278a86522392'}
with receipt.open('x') as stream:
    json.dump(record, stream, indent=2)
    stream.write('\n')
print(json.dumps(record))
