# Copyright 2026 Zhilun Hu.
# SPDX-License-Identifier: Apache-2.0
"""Deliver the private-prefix interface and evidence to Codex1/Codex2."""
import fcntl
import hashlib
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

root = Path('/public/home/sunyihan/rpent_libero_eval')
base = root/'coordination/bounded_skills_20261016'
prep = json.loads((base/'reports/chunk_v3_offline_labels_20261018_preparation.json').read_text())
source = Path(prep['snapshot'])
hashes = {name: hashlib.sha256((source/name).read_bytes()).hexdigest()
          for name in ('SKILL_PACKAGE_SPEC.md', 'rpent/skill_package/schema.json',
                       'rpent/skill_package/contract.py', 'robots/libero/bounded_offline_labels.py')}
message = f"""
[Codex3 | {datetime.now(ZoneInfo('America/Los_Angeles')).isoformat()} | 10:05 follow-up, CPU arbitrary-prefix interface]
Conclusions: bowl spatial0/init2 both-rule failure is repaired (9022 both native success,260controls,new3decisions/old5). CPU arbitrary-prefix labels are implemented; real-launcher capture validation is next. Candidate catalog order is nonsemantic; detailed source receipts remain last3. Function profiles locate route search/cloud-IK/sweep and repeated perception costs. Microwave task recovery remains incomplete; no freeze or training.
Codex2/Codex1 source: {source}; commit c916ab11f0f97e591f6094d80db7f03f4f1264f4; interpreter {root}/.venv/bin/python; archive SHA {prep['archive_sha256']}. Public bounded-skills/3 and public-request-legal/2 unchanged. Exact file hashes: {json.dumps(hashes, sort_keys=True)}.
Private API: robots.libero.bounded_offline_labels.capture_annotation_state / save_annotation_state / load_annotation_state / annotate_prefix(state,request,prefix). Private version libero-offline-prefix-label/1. legal comes from public legal_after without planner; rule_acceptable uses the same oracle on that model-selected prefix's conditional predicted state. No physics/RPC/camera in annotate; CPU collision/IK computation remains. New synchronous probe rows contain private_prefix_annotation_state, never in public request. Explicit terminal/infeasible/no-option states stay explicit. Historical simulator pickles alone lack measured masks/routes/bindings and cannot honestly fill every unknown. Prefetched states are not mislabeled from later snapshots. CLI: python -m scripts.label_bounded_prefix --state STATE.pkl.gz --state-sha256 SHA --request REQUEST.json --prefix PREFIX.json --output LABEL.json. Codex2 may wire the interface now; first real snapshot validation is pending and will be delivered separately.
CPU tests:243 passed129.34s(adapter/payload/offline),53 passed51.49s(overlapping offline/screen/probe/chunk);Ruff/CLI/diff pass. Saves/loads,nonoracle prefixes,oracle-path agreement,no live IO,immutability,invalid/mismatched/terminal prefixes and corrupt hashes covered. No confirmation reruns; permanent training exclusions remain.
Microwave9024 saved function profile:request46.782s;surface_contact_plan18.913/3calls,cloud_and_ik17.987/48,candidate15.691/58,prepare14.917/54,route_screen12.737/54,fixture_handle11.223/2,IKcheck6.711/900. Cumulative values overlap. Full refresh5.821-7.481s each,initial11RPC5.356s; repeated refresh/fixture measurements explain larger per-decision totals. Client profiles do not isolate SAM kernels. Shared IK warm starts/plans make candidate process parallelism order-dependent; not enabled under exact-output requirement. Existing exact-output caches/broad phases remain documented. Top15+hashes:{base}/reports/profile_saved9024_120_CPU_20261018.json.
9025 new microwave arm retained failure16decisions/772controls;legacy arm still running. Row7 target/finger30hits are all positive2.37-3.98mm margins,zero interiors. New code applies existing scene no-deeper-incursion escape rule to target pixels too:three1cm escape routes now pass geometry,three inward routes remain blocked(stub IK,not task success). CPU evidence:{base}/reports/microwave9025_target_margin_CPU_20261018.json. Runtime startup is being queued before expansion.
Full follow-up:{base}/progress_1005_offline_labels_20261018.md. Previous three-pair success9014 and bowl-init2 paired9022 are separate fixed-source development evidence; current180-state ff00387 cohort continues with its original SHA. No pooled/mixed-source qualification.
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
with path.open('rb') as stream:
    stream.seek(start)
    assert stream.read(len(raw)) == raw
receipt = {'path': str(path), 'start': start, 'end': end, 'bytes': len(raw),
    'sha256': hashlib.sha256(raw).hexdigest(), 'source_commit': prep['source_commit']}
(base/'reports/coord_1005_offline_labels_append_20261018.json').write_text(json.dumps(receipt, indent=2)+'\n')
print(json.dumps(receipt))
