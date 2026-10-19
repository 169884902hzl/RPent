"""Deliver the pinned panel-route repair without claiming physical success."""
import fcntl
import hashlib
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

root = Path('/public/home/sunyihan/rpent_libero_eval')
base = root / 'coordination/bounded_skills_20261016'
output = base / 'reports/coord_panel_surface_append_20261019.json'
assert not output.exists(), 'This delivery was already appended'
prep = json.loads((base / 'reports/chunk_v3_panel_facing_20261019_preparation.json').read_text())
startup = json.loads((base / 'reports/chunk_v3_panel_facing_20261019_startup_submission.json').read_text())
source = Path(prep['snapshot'])
assert prep['source_commit'] == startup['source_commit'] == 'f4400223'
assert prep['manifest'] == startup['manifest']
for relative, expected in prep['cpu_validation']['results']['files'].items():
    assert hashlib.sha256((source / relative).read_bytes()).hexdigest() == expected
timestamp = datetime.now(ZoneInfo('America/Los_Angeles')).isoformat()
message = f"""

## Codex3 panel surface recovery / {timestamp}

1. The five 10:05 questions have direct answers in {base}/progress_prefix_judge9_and_door_identity_20261018.md: function profiles and cache/parallel limits, bowl init2 paired native success, CPU arbitrary-prefix labels, candidate order has no semantics, and three detailed receipts retained.
2. New production source f44002235eefa806d7731b842566740aea2525c9 is pushed to harness-v5. Panel normal faces measured EEF; after every measured-handle route fails, the existing measured-panel route is also screened. Collision/IK gates, force and budget are unchanged. CPU 272 passed, 218.25s; original 220-state path/identity preflight passed.
3. Same saved microwave-close terminal: old normal 0/16 screened routes feasible; measured-EEF-facing normal 1/16 feasible, CPU 4.607s. This is cross-source CPU geometry diagnosis, not physical success or a training label. New same-snapshot/launcher startup {startup['job']}_120 is queued; full close/open cases120/140 wait for actual physical startup proof.
4. Previous source184ba1d7 full microwave results remain failures: close9600_120=19decisions/1477ticks/2015.367s/planning_unreachable; open9600_140=27/1432/2809.683s/perception. Drawer9603_117 still incomplete; plate9576 remains0/2, improved0/regressed0 versus ec89f74. RGB overlays identify real cabinet-handle blockers, not removable phantom points.
5. Codex3 continues physical checks; Codex1 audits source/protocol/denominators; Codex2 labels unknown only with exact captured context and matching source/judge. Missing-context historical59 unknown remain unsupported. No training/freeze/regrading; confirmation exclusions stay permanent.

Source snapshot: {source}
Archive SHA256: {prep['archive_sha256']}
Manifest: {prep['manifest']['path']}
Manifest SHA256: {prep['manifest']['sha256']}
Entry: {prep['entry']}; interpreter: {prep['interpreter']}
Public schema bounded-skills/3 SHA df17c6c49e4992247ab8ff37ebf528f893ac6887ea8cf946e25668aca110b4aa; legal public-request-legal/2 contract SHA 7e898e3bd4e8f4c7a4e9951d897cc1fe682037ee35ee4d6d5cc1f52606e2f49c; private judge rules/13 oracle SHA c6057acd0056d940b1c03235c2d54a27e3750161e16f8a8936f0af45db70cc89. Machine protocol bytes unchanged; new behavior is separately source-pinned.
Current delivery: {base}/progress_panel_surface_recovery_20261019.md and reports/panel_surface_recovery_cpu_20261019.json. Original ec89f74 interimr14 is43/52completed/220registered,0execution_error, with category Wilson intervals and all failed rows. Box ee42501 remaining18 closed15/18 (not20); 4db4ea4 current box cohort3/20complete,3success. Sources remain separate.
Judge13 actual-context offline labels: {base}/reports/offline_prefix_9602_117_CPU_20261018.json, two oracle positions match legal/acceptable/selected and one alternative nudge prefix labels successfully, CPU1.584/53.605/48.774s; functionality verified, throughput unresolved. Not a substitute for missing old contexts.
Node02/nice500 only; unique controller session32385 replaces50036 (the old controller was deliberately stopped, no simulation cancellation). C2GPU absent permits fourth-card borrowing; its queued GPU work reduces replacement cap to3. Protected and held jobs untouched.
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
