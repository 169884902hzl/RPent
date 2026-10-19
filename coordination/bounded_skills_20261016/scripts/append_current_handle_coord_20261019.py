"""Deliver the current-handle identity repair before its first simulation."""
import fcntl
import hashlib
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

root = Path('/public/home/sunyihan/rpent_libero_eval')
base = root / 'coordination/bounded_skills_20261016'
output = base / 'reports/coord_current_handle_append_20261019.json'
assert not output.exists(), 'Already delivered'
prep = json.loads((base / 'reports/chunk_v3_current_handle_20261019_preparation.json').read_text())
assert prep['preflight']['exit_code'] == prep['cpu_validation']['results']['exit_code'] == 0
for name, expected in prep['cpu_validation']['results']['files'].items():
    assert hashlib.sha256((Path(prep['snapshot']) / name).read_bytes()).hexdigest() == expected
timestamp = datetime.now(ZoneInfo('America/Los_Angeles')).isoformat()
message = f"""

## Codex3 current-handle door identity repair / {timestamp}

1. The five 10:05 answers are complete in {base}/progress_prefix_judge9_and_door_identity_20261018.md. CPU prefix labels support exact matching captured contexts; the historical 59 unknown positions still lack context and remain unsupported. Candidate order has no semantics; detailed receipts retain the last three.
2. Same saved original-task RGB-D shows the fixed control panel mislabeled as a door in the wrist view. In 12 captures from one closed development episode, unchanged handle-backing geometry accepts 20 real-door comparisons and rejects 12 wrong-panel comparisons. These correlated comparisons are not episodes or generalization accuracy. Full inputs and hashes: {base}/reports/microwave9600_handle_panel_all_CPU_20261019.json. The initial all-rows diagnostic failed on the terminal record's missing optional candidate diagnostics; it was corrected and rerun, with the physical records untouched.
3. Source {prep['source_commit']} adds unique current-handle support only when two door views conflict. No new geometry thresholds; missing/competing support stays unknown. Runtime checks public source/capture/SHA, retains actual selected-camera pixels and clears rejected identity history. This is identity evidence, not an articulation endpoint; stop_admitted stays false. The eight focused cases pass; full CPU regression: {prep['cpu_validation']['results']['summary']}. New geometry diagnostic current_handle_association is declared here before simulation. Schema bounded-skills/3, public-request-legal/2 and private judge rules/13 remain unchanged. Do not relabel old-source contexts as this source.
4. f75 startup 9607_120 is complete: 111 actual ticks / 1 decision / 71.130491s; this is startup proof only. f440 full 9605 is separate. d137822 full 9539 is closed 0/2 (close 17 decisions/947 ticks/2014.700828s; open 27/1432/2794.310504s). All failures remain. Fixed ec89f74 originals r15 are 46/56 complete of 220 registered, zero execution errors; category/Wilson/per-episode records are in reports/original20_support_interim_r15_20261019.json. No category qualification or freeze is claimed.
5. Codex3 next runs the same-launcher startup and same-state full replay; Codex1 audits identities/source/denominators; Codex2 uses exact-context CPU labels. Full report: {base}/progress_current_handle_identity_20261019.md. No training, PRO reads, confirmation regrading or real hardware; confirmation exclusions remain permanent. Node02/nice500 only; C2 GPU pending returns replacement concurrency to at most three, protected and held jobs untouched.

Snapshot: {prep['snapshot']}
Archive SHA256: {prep['archive_sha256']}
Manifest: {prep['manifest']['path']}
Manifest SHA256: {prep['manifest']['sha256']}
Entry: {prep['entry']}; interpreter: {prep['interpreter']}
CPU receipt: {prep['cpu_validation']['receipt']}
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
          'source_commit': prep['source_commit'], 'physical_run_started': False}
with output.open('x') as stream:
    json.dump(report, stream, indent=2)
    stream.write('\n')
print(json.dumps(report))
