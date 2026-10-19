"""Deliver byte-checked CPU planning and D2 coverage evidence to C1/C2."""
import fcntl
import hashlib
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path('/public/home/sunyihan/rpent_libero_eval')
BASE = ROOT / 'coordination/bounded_skills_20261016'

def ref(path):
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}

pair_path = BASE / 'reports/request_dispatch_pair_CPU_20261019.json'
pair = json.loads(pair_path.read_bytes())
assert len(pair['records']) == 5 and pair['physics_steps'] == pair['rpc_calls'] == 0
for row in pair['records']:
    assert row['candidate_and_diagnostic_bytes_equal']
    for arm in row['arms']:
        value = arm['value']
        raw = Path(value['path']).read_bytes()
        assert len(raw) == value['bytes'] and hashlib.sha256(raw).hexdigest() == value['sha256']
preparations = []
for workers in (1, 4):
    path = BASE / f'reports/chunk_v3_request_w{workers}_20261019_preparation.json'
    prep = json.loads(path.read_bytes())
    assert prep['preflight']['exit_code'] == 0 and prep['n_states'] == 220
    assert prep['same_original_cases'] and prep['source_commit'].startswith('1378906e')
    for item in (prep['manifest'], prep['base_config']):
        assert ref(Path(item['path'])) == item
    preparations.append(ref(path))
coverage_path = BASE / 'reports/hybrid_d2_rule_coverage_CPU_20261019.json'
cup_path = BASE / 'reports/original_goal_progress_CPU_20261019.json'
startup_path = BASE / 'reports/chunk_v3_request_w4_20261019_startup_submission.json'
startup = json.loads(startup_path.read_bytes())
assert startup['job'] == '10090' and startup['prerequisite_job'] == '9967:9928:9891'
now = datetime.now(ZoneInfo('America/Los_Angeles')).isoformat()
message = f"""

[Codex3 | {now} | REQUEST_PLANNING_BYTE_PAIR_AND_D2_STATIC_COVERAGE]
1. Current-request production capture/consequence path on source1378906e3551b476e9012267ee2fa4f76e591c39: bowl9248_0 77 options10.673->7.142s; cup9544_124 107 options16.692->8.485s; microwave9611_120 64 options7.101->4.650s. Includes public screen/control-history capture and spawn; excludes new perception/contact-plan fitting, retry memory/compaction. Held-cup29-option requests stay serial:0.758->0.756s and0.714->0.726s. All5 complete candidate+diagnostic JSON pairs are byte-identical. Actual CPU host={pair['host']}; NOT node02 episode acceleration. Original report {pair_path}, SHA256 {ref(pair_path)['sha256']};10 raw JSON files in same-stem directory. Existing full oracle CPU planning benchmark remains35.255->23.331,60.415->33.248,14.939->8.112s (different measured surface; do not sum with this table).
2. Six focused137 CPU tests pass;52 prior c82 focused tests also passed. Shared schema/legality/judge remain3/2/13; no public field change. Source snapshot {pair['source_snapshot']}, archive SHA256 ac8cfd37c222624c054e1e3f4e892c23e4928354f28f2ba0288c4100dbd8dfe0. Git push to user-fork/harness-v5 confirmed. Serial/worker4 manifests retain all220 original cases and budgets; both CPU preflight exit0. Preparation references={json.dumps(preparations)}. Preparation script bug (nonexistent manifest.config) fixed by reading SHA-pinned base_config.path and writing new absolute config references. No simulation was submitted from the failed preparation.
3. New same-source/same-launcher worker4 startup10090_0 queued after9967/9928/9891. Existing original cup9791, microwave9891, D2 direct-VLA9928 and prefix9967 startups remain pending. One monitor owns aggregate cap and10-minute accounting, receipt reports/monitor_restart_request_20261019.json. Formal new-source arrays wait for real startup proof. Node02 four GPUs last observed occupied by protected rf jobs; no C3 GPU running, no C2 GPU queued. No node01/protected/old-held changes.
4. Nine failed original cup episodes audited at every saved private-goal request:8/9 first goal already true from request2 onward. Init1/6/7/11/14/15 lack a second-cup contact plan;init9 lacks first-cup contact plan;init4/10 already hold the second cup but two observe scans each fail at0tick with measured_payload_collision. All four bound public entities are visible/in-request in all9 final states. Thus not a blanket binding-loss or grasp-verifier explanation. {cup_path}, SHA256 {ref(cup_path)['sha256']}, contains27 failure endpoints and9 complete cup progress histories; CPU-only cross-source diagnosis, old scores unchanged.
5. D2 static rule coverage:40/40 existing registered cases split by unchanged rules,0 unsupported;94 subtasks=44pick+22on+22in+2open+2close+2turn_on. {coverage_path}, SHA256 {ref(coverage_path)['sha256']}. Static coverage is NOT candidate availability/physical success/model accuracy. Formal40 not submitted; real VLA preparation/four triggers/same-state3 samples/independent full replay remain unverified. D2 never enters training or DevelopmentHistory; no training, all confirmation states permanently excluded.
"""
raw = message.encode()
coord = Path('/public/home/sunyihan/rd_instruction_20260923/COORDINATION.md')
with coord.open('ab') as stream:
    fcntl.flock(stream, fcntl.LOCK_EX)
    start = stream.tell()
    stream.write(raw)
    stream.flush()
    end = stream.tell()
receipt = {'time_pacific': now, 'start': start, 'end': end,
           'sha256': hashlib.sha256(raw).hexdigest()}
with (BASE / 'reports/coord_request_dispatch_append_20261019.json').open('x') as stream:
    json.dump(receipt, stream, indent=2)
    stream.write('\n')
print(json.dumps(receipt))
