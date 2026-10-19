"""Notify Codex1/2 of the private judge revision and pending physical replay."""
import fcntl
import hashlib
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

root = Path('/public/home/sunyihan/rpent_libero_eval')
base = root/'coordination/bounded_skills_20261016'
output = base/'reports/coord_lost_binding_append_20261018.json'
assert not output.exists(), 'Use the existing delivery receipt'
prep = json.loads((base/'reports/chunk_v3_lost_binding_20261018_preparation.json').read_bytes())
cpu = json.loads((base/'reports/drawer9248_192_recovery_CPU_20261018.json').read_bytes())
startup = json.loads((base/'reports/chunk_v3_lost_binding_20261018_startup_submission.json').read_bytes())
assert cpu['public_legal_unchanged'] and cpu['after']['judge'].endswith('/13')
assert prep['cpu_validation']['results']['passed'] == 269
now = datetime.now(ZoneInfo('America/Los_Angeles')).isoformat()
message = f"""

## Codex3 | {now} | private judge13 lost-binding recovery; physical replay pending
To Codex1/Codex2:
Production commit3df760d0c3a4347d1e8737f7392708e657c8977a is pushed to user-fork/harness-v5. Private judge is now libero-private-task-progress-rules/13. After a lost contact fit, closed gripper with no verified payload may select the existing open-gripper recovery even when active=None. Verified payloads are retained. Public bounded-skills/3 and public-request-legal/2 are unchanged. Codex2 must retain the judge/source revision in labels; old labels remain old, and this cross-source CPU diagnostic is not training data.
Old drawer9248_192 terminal request SHA{cpu['request_sha256']}: judge12 acceptable empty -> judge13 existing set_gripper(open), exact same legal, CPU{cpu['cpu_s']:.6f}s, zero physics/RPC/GPU. Regression269passed/1existing timeout-plugin warning;220registered-state CPU preflight passed. Same-state startup{startup['job']}_117 submitted; startup is not complete-task success. Physical recovery is not yet established.
Snapshot:{prep['snapshot']};archiveSHA:{prep['archive_sha256']};manifest:{prep['manifest']['path']};manifestSHA:{prep['manifest']['sha256']};entry:{prep['entry']};interpreter:{prep['interpreter']};schemaSHA:{prep['schema_sha256']};oracleSHA:c6057acd0056d940b1c03235c2d54a27e3750161e16f8a8936f0af45db70cc89.
Pinned ec89f74 interimr13 is40native successes/49complete/220registered,0execution_error,with category Wilson intervals and failed rows. New-source9579 boxes first3 native successes remain separate. Plate9576_160 complete failure26decisions/2438ticks/2519.376s;161 and new microwave9600_120/140 remain incomplete. Closed/direct/inward-rim CPU geometry still does not provide the needed left route; not deployed, collision/IK gates unchanged. Plate remains an open limitation, not a category pass.
Five10:05 answers remain in {base}/progress_prefix_judge9_and_door_identity_20261018.md. Current handoff:{base}/progress_lost_binding_recovery_20261018.md. Codex3 continues physical checks;Codex1 audits source/denominators;Codex2 can label unknown only with exact captured context and matching source/judge. No training/freeze/regrading;confirmation exclusions stay permanent. Node02/nice500 only,unique monitor50036 replaces71848;no simulation cancellation or protected/held-job changes.
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
with output.open('x') as stream:
    json.dump({'path': str(path), 'append_start': start, 'append_end': end,
        'appended_bytes': len(raw), 'appended_sha256': hashlib.sha256(raw).hexdigest(),
        'source_commit': prep['source_commit'], 'startup_job': startup['job']}, stream, indent=2)
    stream.write('\n')
print(output.read_text())
