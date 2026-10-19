"""Append source-pinned raw CPU evidence for C1/C2 without claiming physics."""
import fcntl
import hashlib
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

root = Path('/public/home/sunyihan/rpent_libero_eval')
base = root / 'coordination/bounded_skills_20261016'
profile_path = base / 'reports/runtime_spawn_profile_CPU_20261019.json'
profile = json.loads(profile_path.read_bytes())
assert profile['all_saved_context_and_label_bytes_equal']
for arm in profile['arms']:
    for item in (arm['request'], arm['labels'], *arm['contexts']):
        raw = Path(item['path']).read_bytes()
        assert len(raw) == item['bytes'] and hashlib.sha256(raw).hexdigest() == item['sha256']
message = f"""

[Codex3 | {datetime.now(ZoneInfo('America/Los_Angeles')).isoformat()} | FULL_CPU_CONTEXT_ORIGINALS_AND_STOVE_DIAGNOSIS]
1. Complete CPU profile and raw context/labels are now available: {profile_path} (SHA256 {hashlib.sha256(profile_path.read_bytes()).hexdigest()}); reports/runtime_spawn_profile_CPU_20261019/ contains all 12 canonical JSON artifacts. Same cup9544_124 request, each of 4 public prefix contexts, full labels, choice and legality audit match byte-for-byte across serial/spawn4. Actual CPU host={profile['host']}, interpreter={profile['interpreter']}. C1 can compare the original bytes directly; pstats remain on the source host.
2. Profiled wall 72.206->37.069s includes instrumentation overhead. Use the unprofiled report runtime_spawn_oracle_CPU_20261019.json for timing:35.255->23.331s bowl,60.415->33.248s cup,14.939->8.112s microwave. Serial cup270 prepare calls accumulate60.053s, including route screen44.043s, geometry_at25.988s and IK check11.261s (nested, DO NOT sum). Spawn main process waits34.115s for three prefix batches; worker internals are not profiled. Initial request/contact generation and live perception remain outside this experiment. No actual episode acceleration claim.
3. Original fixed-source ec89f74 stays109/136 complete/220 registered,27 failures/84 incomplete. Eight saved stove states audited in reports/stove_recovery_CPU_20261019.json and stove_observation_routes_CPU_20261019.json; see progress_failure_audit_20261019.md. Four turn-off second wrist rotations reach public J7 upper limit vicinity (2.8973rad static limit, final2.897756-2.897760rad), endpoint errors17.7-25.2mm/angular0.135-0.168rad. Current generic lost-contact recovery selects set_gripper(open) in all4 plus2 turn-on collision states. Two turn-on states have zero knob detection across6 public prompts; current measured noncontact approaches pass12/12 and6/12 route screens. These are cross-source CPU diagnostics, not successful physical recovery or replacement labels.
4. Raw compact27-episode receipts: reports/original_failures_receipts_CPU_20261019.json; full diagnostic raw projection51MB remains source-side reports/original_failures_stage_audit_CPU_20261019.json. Cup private goal-progress audit is running; reaching a lift/carry/release sequence is not treated as task success.
5. Physical startup9791/9891/9928/9967 remains queued on node02 behind protected rf jobs; D2 formal40 not submitted. Actual VLA preparation, four triggers, same-state3 VLA branches and selected-method independent full replay remain unverified. No protected/held jobs changed, no training, all confirmation states stay excluded.
"""
raw = message.encode()
coord = Path('/public/home/sunyihan/rd_instruction_20260923/COORDINATION.md')
with coord.open('ab') as stream:
    fcntl.flock(stream, fcntl.LOCK_EX)
    start = stream.tell()
    stream.write(raw)
    stream.flush()
    end = stream.tell()
receipt = {'time_pacific': datetime.now(ZoneInfo('America/Los_Angeles')).isoformat(),
           'start': start, 'end': end, 'sha256': hashlib.sha256(raw).hexdigest()}
with (base / 'reports/coord_cpu_profile_stove_append_20261019.json').open('x') as stream:
    json.dump(receipt, stream, indent=2)
    stream.write('\n')
print(json.dumps(receipt))
