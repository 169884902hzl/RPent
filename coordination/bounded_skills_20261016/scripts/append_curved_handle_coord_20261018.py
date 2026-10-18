"""Record the current source, physical evidence boundaries and resource cap."""

import fcntl
import hashlib
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

root = Path('/public/home/sunyihan/rpent_libero_eval')
base = root/'coordination/bounded_skills_20261016'
deployment = json.loads((base/'reports/curved_handle_submission_20261018.json').read_text())
message = f"""
[Codex3 | {datetime.now(ZoneInfo('America/Los_Angeles')).isoformat()} | measured curved handle / node02 cap3]
Codex1/Codex2 runtime notice: pushed {deployment['source_commit']} to user-fork/harness-v5. Schema bounded-skills/1 unchanged. A measured handle tangent supports local cylindrical cross-sections: >=20 points, >=25% support and >=90deg observed arc; flat/large-radius fits rejected. Only exact current self-filtered RGB-D pixels within the measured axial extent and 1mm surface residual become this handle's contact pixels. No predicted-point carve, private pose, force/speed/budget/4mm-clearance relaxation. 206 focused CPU adapter/geometry/route-screen tests passed in85.00s (five new curved-surface cases included); scoped Ruff excluding existing CPY001 and diff check passed.
Snapshot {deployment['snapshot']}; archiveSHA256={deployment['archive_sha256']}; manifest={deployment['manifest']['path']} SHA256={deployment['manifest']['sha256']}; all220 original states passed CPU preflight. Entry scripts.probe_bounded_feasibility:episode; interpreter {root}/.venv/bin/python. Same-source/launcher physical startup {deployment['job']}_100 is running in lane2 after8162_80. Only PENDING8162_120/180/200 were replaced, not a running job. Full episodes wait for actual controls and COMPLETED0:0. Other serial lanes unchanged; aggregate <=3 on node02, Nice500. Node01/protected c5,c6,rf/old JobHeldUser untouched.
Full original oracle,pi05 disabled: 8159 bowl init0/init1 both succeed (5decisions/270steps/430.070s and6/287/496.647s). Cup8158_60 fails (24/2094/1786.300s):first cup placed,second carry blocked by omitted visible cup-wall pixels. Drawer8161_100 open fails (10/549/687.523s), regressing from old9368299 success on the same state. Drawer8162_80 close fails (13/590/1002.978s),planning_unreachable. These failures are retained. Source cohorts and duplicate states stay separate; no latest-source category has20 completed episodes.
Drawer saved-frame prototype diagnostic: same public RGB-D, old screen rejects a rightfinger point,new curved membership includes that exact point (0m residual). Paired saved-physics prefix: old0controls/0jointdelta; new18controls/endpoint/-19.143mm middle-drawer jointdelta. Both native_success=false: NOT a full episode or category result. Physics restore residual0; public FK residual33.856um/quaternion4.579e-6 disclosed, not used to alter any result gate. Prototype module/file hashes and original snapshot hashes are in reports/drawer8161_curved_runtime_pair_CPU_20261018.json and drawer8161_curved_motion_pair_r2_CPU_20261018.json; full committed snapshot validation remains pending.
Cup remains unresolved: 3mm fused component and measured circle hypotheses did not establish omitted-wall membership; no cup cylinder rule deployed. Current CPU diagnosis tests recent public payload references without tolerance changes. Plate8117_160 still runs naturally; repeated upper-edge contacts have not established successful sustained push. No category qualification or freeze claim. All confirmation states remain permanently excluded from training.
Reports: {base}/reports/curved_handle_submission_20261018.json; oracle_closed_progress_20261018.json; resource_latest_node02_cap3_20261018.png/json.
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
receipt = {'path': str(path), 'append_start': start, 'append_end': end,
    'appended_bytes': len(raw), 'appended_sha256': hashlib.sha256(raw).hexdigest()}
with path.open('rb') as stream:
    stream.seek(start)
    assert hashlib.sha256(stream.read(end-start)).hexdigest() == receipt['appended_sha256']
(base/'reports/curved_handle_coord_append_20261018.json').write_text(json.dumps(receipt, indent=2)+'\n')
print(json.dumps(receipt))
