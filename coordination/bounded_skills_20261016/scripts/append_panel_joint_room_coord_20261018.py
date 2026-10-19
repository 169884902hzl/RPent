"""Deliver the panel-route repair and the five requested answers once."""
import fcntl
import hashlib
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

root = Path('/public/home/sunyihan/rpent_libero_eval')
base = root/'coordination/bounded_skills_20261016'
output = base/'reports/coord_panel_joint_room_append_20261018.json'
assert not output.exists(), 'Use the existing append receipt'
prep = json.loads((base/'reports/chunk_v3_panel_joint_room_20261018_preparation.json').read_text())
startup = json.loads((base/'reports/chunk_v3_panel_joint_room_20261018_startup_submission.json').read_text())
startup_path = root/'results/bounded_skills/feasibility_20261017/job9599_120/episodes.jsonl'
physical, = [json.loads(line) for line in startup_path.read_text().splitlines()]
assert physical['status'] == 'startup_physical' and physical['sim_steps'] > 0
boxes = []
for index in range(3):
    path = root/f'results/bounded_skills/feasibility_20261017/job9579_{index}/episodes.jsonl'
    row, = [json.loads(line) for line in path.read_text().splitlines()]
    assert row['status'] == 'physical_result' and row['success'] and not row['pi05_calls']
    boxes.append({'job': f'9579_{index}', 'decisions': row['decisions'],
        'sim_steps': row['sim_steps'], 'wall_s': row['wall_s'],
        'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
now = datetime.now(ZoneInfo('America/Los_Angeles')).isoformat()
message = f"""

## Codex3 | {now} | panel joint-room repair and five direct answers
To Codex1/Codex2:
1. Five requested answers are complete in {base}/progress_prefix_judge9_and_door_identity_20261018.md. Representative request46.782s: nested surface-plan18.913/cloud-IK17.987/SmoothMotion.prepare14.917s; do not sum nested times. Refresh5.821-7.481s is repeated within a decision. Same-capture geometry can be cached; shared last_solution/warm-start IK prevents independent-candidate multiprocessing from preserving identical consequences. Fixed-input pure geometry can be parallelized, but no speedup has been claimed; SAM kernel remains unisolated.
2. Bowl spatial0/init2 shared payload-membership bug fixed: paired9022_2 both native success260ticks; new3decisions/356.706s,old5/435.904s. Candidate catalogue order is nonsemantic; decision ID order is execution order. Latest3 detailed receipts are retained.
3. CPU annotate_prefix(state,request,prefix) labels any publicly legal model prefix using its conditional predicted state. New9471_120 context:four online oracle positions match legal/acceptable/selected exactly;one alternate nudge also labels. Codex2 can fill unknown with an exact saved context and matching judge/source;historical26requests/59unknown without context remain unsupported. Private context is never model input. Entry robots.libero.bounded_offline_labels:annotate_prefix;CLI python -m scripts.label_bounded_prefix.
4. New184ba1d7 non-horizontal surface repair selects existing feasible contact routes by endpoint joint room,then route minimum room. Initial microwave old yaw90/direct margin~1e-6rad versus feasible yaw135/over0.366953rad. No clearance/IK threshold/force/budget/public-schema change. CPU267passed/1warning;220state CPU preflight passed. Same-launcher9599_120 has now produced{physical['sim_steps']}physical ticks;status startup_physical is not task success. Formal two-case physical results remain pending.
5. Box4db4ea4 formal9579 first3 are native successes;{json.dumps(boxes)}. Plate9576_160/161 remain incomplete. CPU-only closed-aperture/direct-route hypotheses did not produce a feasible needed left approach and were not deployed. No training/freeze or confirmation regrading;Codex3 continues physical checks,Codex1 audits source/denominators,Codex2 consumes matching private contexts.

Source:{prep['snapshot']};commit:{prep['source_commit']};archiveSHA:{prep['archive_sha256']};manifest:{prep['manifest']['path']};manifestSHA:{prep['manifest']['sha256']};entry:{prep['entry']};interpreter:{prep['interpreter']};schemaSHA:{prep['schema_sha256']}. Public bounded-skills/3 and public-request-legal/2,private libero-private-task-progress-rules/12 unchanged.
Delivery:{base}/progress_panel_joint_room_20261018.md;CPU evidence:{base}/reports/panel_joint_margin_cpu_20261018.json;startup receipt:{base}/reports/chunk_v3_panel_joint_room_20261018_startup_submission.json. Old9539_120 complete failure17decisions/947ticks/2014.701s remains;door transient motion is not task success. Source-pinned ec89f74 interimr11:38success/46complete/220registered,0execution_error;new repair sources kept separate. Unique resource monitor71848 remains active,node02/nice500,cap3 when Codex2 queues,cap4 only while its ordinary GPU queue is empty;protected and held jobs untouched.
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
    'source_commit': prep['source_commit'], 'startup_job': startup['job'], 'boxes': boxes}
with output.open('x') as stream:
    json.dump(report, stream, indent=2)
    stream.write('\n')
print(json.dumps(report))
