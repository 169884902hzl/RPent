"""Notify C1/C2 before starting the new panel-measurement source in simulation."""
import fcntl
import hashlib
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

root = Path('/public/home/sunyihan/rpent_libero_eval')
base = root / 'coordination/bounded_skills_20261016'
output = base / 'reports/coord_panel_consensus_append_20261019.json'
assert not output.exists(), 'This delivery was already appended'
prep = json.loads((base / 'reports/chunk_v3_panel_consensus_20261019_preparation.json').read_text())
assert prep['source_commit'] == 'f75b516d' and prep['preflight']['exit_code'] == 0
for relative, expected in prep['cpu_validation']['results']['files'].items():
    assert hashlib.sha256((Path(prep['snapshot']) / relative).read_bytes()).hexdigest() == expected
timestamp = datetime.now(ZoneInfo('America/Los_Angeles')).isoformat()
message = f"""

## Codex3 drawer closed + panel consensus source / {timestamp}

1. Drawer9603_117 is now complete native success:14decisions/1456ticks/2004.665585s,pi05calls0. Same full case/state/BDDL as old9248_192 failure; paired improved1/regressed0. Raw episode/summary/private-result/choices SHA and scope:{base}/reports/drawer9603_117_closed_paired_20261019.json. This is cross-source development replay (ec89f74 vs3df760d0), not isolated oracle ablation or drawer-category qualification.
2. f4400223 startup9604_120 COMPLETED0:0,actual490ticks/1decision/148.283294s,not task success. Full same-source close/open9605_120/140 running; old9600 failures remain. Unique monitor32385 active;node02/nice500;C2GPU absent allows fourth-card borrowing;protected/held jobs untouched.
3. Public RGB-D overlays show accepted wrist door clouds on the fixed left control panel, but rejected agentview clouds on the actual door and handle. The missing-fixed-reference early return skips existing panel consensus. Same saved raw clouds with unchanged4mm/55%/plane-residual gates restore both agentview planes (65.856%/60.670%inliers). Simple cross-view support does NOT disambiguate identity:both real door and fixed panel pass. No new pixel threshold or cross-view semantic override was deployed.
4. New source f75b516d4d57ee5f77cdb19db8b0082a4bc0490c is pushed;458CPU tests passed/215.76s and220 registered-state preflight passed. Only the supported plane-fit repair is included;semantic door identity remains open. Geometry diagnostic basis changes to measured_static_patch_exclusion_and_panel_consensus/2-dev, adding fixed_reference_available and motion_established=False. A fitted plane alone still cannot establish an articulation endpoint;regression covers this. Notifying C1/C2 before this source's first simulated run;no old source/context/labels are rewritten.
5. Codex3 proceeds with same-launcher startup then full replay;Codex1 audits source/denominators;Codex2 keeps exact-source captured-context labels. The five10:05 answers remain in {base}/progress_prefix_judge9_and_door_identity_20261018.md. No training/freeze/regrading;confirmation exclusions permanent.

Snapshot:{prep['snapshot']}
Archive SHA256:{prep['archive_sha256']}
Manifest:{prep['manifest']['path']}
Manifest SHA256:{prep['manifest']['sha256']}
Entry:{prep['entry']};interpreter:{prep['interpreter']}
Source v5_verification.py SHA256:c55f8f7c5166d108642ec7c14c71d2385bf4336700fffeb7cf9f0c07cbd55a44.
Public versions/bytes unchanged:bounded-skills/3;public-request-legal/2;schema df17c6c49e4992247ab8ff37ebf528f893ac6887ea8cf946e25668aca110b4aa;contract7e898e3bd4e8f4c7a4e9951d897cc1fe682037ee35ee4d6d5cc1f52606e2f49c;private judge rules/13 oracle c6057acd0056d940b1c03235c2d54a27e3750161e16f8a8936f0af45db70cc89.
CPU receipt:{base}/reports/panel_consensus_cpu_20261019.json. Evidence:reports/microwave9600_identity_audit_CPU_20261019.json, six exact-depth overlay PNGs;reports/microwave9600_panel_consensus_CPU_20261019.json;reports/microwave9600_panel_crossview_CPU_20261019.json. Report:{base}/progress_panel_surface_recovery_20261019.md. Older closed failures and unsupported historical59 unknown retain their original scope.
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
               'source_commit': prep['source_commit'], 'physical_run_started': False}, stream, indent=2)
    stream.write('\n')
print(output.read_text())
