# Copyright 2026 Zhilun Hu.
# SPDX-License-Identifier: Apache-2.0
"""Append source-pinned CPU evidence and closed pairs without reading the ledger."""
import fcntl
import hashlib
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

root = Path('/public/home/sunyihan/rpent_libero_eval')
base = root/'coordination/bounded_skills_20261016'
reports = base/'reports'
receipt_path = reports/'coord_precontact_component_append_20261018.json'
assert not receipt_path.exists(), 'Already appended; retain the existing byte receipt'
names = [
    'reciprocal_precontact_validation_CPU_20261018.json',
    'precontact_component_identity_CPU_20261018.json',
    'can_contact_motion_private_CPU_20261018.json',
    'chunk_v3_final_fit_20261018_paired_latest.json',
    'chunk_v3_precontact_component_20261018_preparation.json',
    'chunk_v3_precontact_component_20261018_startup_submission.json',
    'chunk_v3_precontact_stationary_20261018_full_submission.json',
    'original20_panel_recovery_20261018_progress.json',
]
evidence = [{'path': str(reports/name),
    'sha256': hashlib.sha256((reports/name).read_bytes()).hexdigest()} for name in names]
startup = json.loads((reports/names[5]).read_text())
old = json.loads((reports/names[-1]).read_text())
raw = f"""
[Codex3 | {datetime.now(ZoneInfo('America/Los_Angeles')).isoformat()} | Pre-lift occlusion source68573bc | Codex1/Codex2]
Commit68573bc5fe3a752ce8bfb6034a89ea2eb5606fab is pushed to user-fork/harness-v5. One-sided pre-lift ICP invents0.249/0.174rad rotations in saved can init2/5 while private diagnostic restoration measures0.004017/0.005381rad and0.190/0.361mm translations. Reciprocal measured correspondences are now used only before lift; held-payload fitting stays unchanged. Can init5 also needs the existing current-depth connected-component completion within original measured bounds,3mm connectivity and4mm stationary-scene veto. No private pose/identity is consumed by runtime.
Saved-public CPU lift routes pass for bowl init17 and can init2/5. Final additions/removals are31/0,10/6372,33/4612. Independent CPU rendering identifies74/74added pixels as the target, with zero restored-state error. Removed pixels come from the old completed surface, not raw current masks. This is geometry-only evidence, not physical grasp/task success. The global reciprocal-held variant failed one existing test and was rejected; removing voxelization did not fix can init5 and was also rejected. No clearance, force, speed, budget or success criterion was relaxed.
CPU adapter/payload247passed/108.92s; focused19passed/1.72s overlaps that set. Existing timeout-configuration warning and pre-existing Ruff findings remain. Source snapshot {root}/source_bounded_chunk_v3_precontact_component_20261018_68573bc; archive SHA a18a58c10f614242927cbdb198d1c617acd61f5d5c32df39311971808b69867a. Entry scripts.probe_bounded_feasibility:episode; interpreter {root}/.venv/bin/python. All220original registered states pass CPU preflight. Startup{startup['job']}_22 is submitted after9239; only actual startup controls allow formal22/25pairs. No physical result exists yet for68573bc. A new --after launcher argument sets the dependency at submission time; CLI help, byte-compilation and diff whitespace checks pass. There remains only one active resource controller.
Closed sourcee5bbb18 job9214: bowl init16 new=true/3decisions/244sim/378.394s,legacy=true/5/270/475.534s; init19 new=true/5/432/647.212s,legacy=false/12/414/862.661s. Legacy init19 has collision-rejected carries,0tick wrist-scan rejection and no remaining acceptable option. Totals new2/2,legacy1/2 are targeted checks, not category qualification. Sourcec1bc859 startup9216_17 completed0:0 with203actual controls; formal9239_17 remains queued separately. Old sourceff00387 remains {old['success']}/{old['completed_states']} completed of{old['registered_states']} registered, never relabeled as either new source. Historical box_transfer means the alphabet-soup can.
Public bounded-skills/3 schema SHA df17c6c49e4992247ab8ff37ebf528f893ac6887ea8cf946e25668aca110b4aa and public-request-legal/2 contract SHA 7e898e3bd4e8f4c7a4e9951d897cc1fe682037ee35ee4d6d5cc1f52606e2f49c are unchanged. Candidate order is nonsemantic; detailed history remains three receipts. CPU prefix labels support matching captured measured contexts; historical missing contexts remain unsupported. The five10:05 questions and profile/cache/parallelism conclusions remain in {base}/progress_1005_offline_labels_20261018.md.
Node02/nice500 only; rf/c5/c6 and held jobs untouched. No training, confirmation admission or behavior freeze. Pending priority is normal scheduling. Remaining original-state oracle failures continue CPU diagnosis before controls.
Evidence {json.dumps(evidence)}
Report {base}/progress_precontact_reciprocal_20261018.md
""".encode()
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
receipt = {'path': str(coord), 'start': start, 'end': end, 'bytes': len(raw),
    'sha256': hashlib.sha256(raw).hexdigest()}
receipt_path.write_text(json.dumps(receipt, indent=2)+'\n')
print(json.dumps(receipt))
