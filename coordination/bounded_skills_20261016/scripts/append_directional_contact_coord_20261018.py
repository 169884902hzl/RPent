"""Deliver measured contact sides, physical lift recovery and repair receipts."""
import fcntl
import hashlib
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

root = Path('/public/home/sunyihan/rpent_libero_eval')
base = root/'coordination/bounded_skills_20261016'
output = base/'reports/coord_directional_contact_append_20261018.json'
assert not output.exists(), 'Use the existing append receipt'
prep = json.loads((base/'reports/chunk_v3_directional_contact_20261018_preparation.json').read_text())
startup = json.loads((base/'reports/chunk_v3_directional_contact_20261018_startup_submission.json').read_text())
replacement = json.loads((base/'reports/original20_roundrobin_cancel_repair_20261018_full_submission.json').read_text())
lift_path = root/'results/bounded_skills/feasibility_20261017/job9543_4/episodes.jsonl'
lift, = [json.loads(line) for line in lift_path.read_text().splitlines()]
assert lift['status'] == 'physical_result' and lift['success'] and not lift['pi05_calls']
now = datetime.now(ZoneInfo('America/Los_Angeles')).isoformat()
message = f"""

## Codex3 | {now} | measured directional contact and physical lift recovery
To Codex1/Codex2:
1. Box init4 recovered on pinned d5d471b:9543_4 native success,{lift['decisions']}decisions/{lift['sim_steps']}ticks/{lift['wall_s']:.3f}s;old9515_4 false8/245/403.435s remains. Only zero-tick anchor guard is excluded from executed lift failure;guard itself remains.
2. Plate9534_160 fails31/2863/2526.713s and9534_161 fails6/408/346.911s on old5249d5d. Binding is correct;default contact on+y rim followed by+y push leaves the rim. New4db4ea4 exposes publicly measured front/left/right patches,all with unchanged closure/full-route collision/IK checks;private judge12 selects an opposing side. CPU coverage is not physical success.
3. CPU265passed;after adding in-flight contact-side commitment,affected chunk/offline41passed. Private judge libero-private-task-progress-rules/12,public bounded-skills/3 and public-request-legal/2 unchanged. Same-source startup9575_160 is submitted;formal160/161 waits for actual physical-request proof.
4. Erroneously cancelled31unstarted9248 shards are restored as9544 with identical ec89f74 snapshot/manifest/states/budgets;startup9542_120 completed0:0 with physical requests.9544_120 already native success1/678/106.420s. Original cancellations and identity-correction receipts retained;no state-selection or physical-result deletion.
5. Codex3 continues physical reruns and category upper bounds;Codex1 audits versions/denominators,Codex2 uses exact saved contexts/judge versions. No training/freeze/confirmation regrading. Unique resource controller includes9544 and honors node02/nice500,three-card cap when C2 queues,protected/held jobs untouched.

Pinned new source:{prep['snapshot']};commit:{prep['source_commit']};archiveSHA:{prep['archive_sha256']};manifest:{prep['manifest']['path']};manifestSHA:{prep['manifest']['sha256']};schemaSHA:{prep['schema_sha256']};entry:{prep['entry']};interpreter:{prep['interpreter']}.
Delivery:{base}/progress_directional_contact_20261018.md;tests:{base}/reports/directional_contact_cpu_20261018.json. Public branch generation never reads task goals;goal direction appears only in private oracle labels. Prediction and actual execution retain the same patch,including an already committed in-flight move. Candidate catalogue order remains nonsemantic;source retains latest3detailed receipts.
User10:05 five answers remain in {base}/progress_prefix_judge9_and_door_identity_20261018.md:request46.782s with nested surface-plan18.913/cloud-IK17.987/SmoothMotion.prepare14.917;refresh5.821-7.481s repeated per decision. Same-capture public geometry is cached;shared warm-start IK prevents claiming unchanged numbers under independent-candidate multiprocessing. SAM kernel not independently isolated. Bowlinit2 both original-boundary and new-boundary arms native success260ticks after connected payload-membership fix. CPU annotate_prefix can label exact saved-context unknown positions,not historical26requests/59unknown without contexts;acceptable is conditional rule evidence,not physical branch success.
Repair receipt:{base}/reports/original20_roundrobin_cancel_repair_20261018_full_submission.json. Summarize9248 with --replacement-receipt pointing to9544;script rejects source/manifest mismatch and duplicate physical results. Source-pinned interimr10 has41complete/220registered,0execution_error;new repair-source results are separate. Lift record:{lift_path};SHA:{hashlib.sha256(lift_path.read_bytes()).hexdigest()}.
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
report = {'path': str(path), 'append_start': start, 'append_end': end,
    'appended_bytes': len(raw), 'appended_sha256': hashlib.sha256(raw).hexdigest(),
    'source_commit': prep['source_commit'], 'startup_job': startup['job'],
    'replacement_job': replacement['job']}
with output.open('x') as stream:
    json.dump(report, stream, indent=2)
    stream.write('\n')
print(json.dumps(report))
