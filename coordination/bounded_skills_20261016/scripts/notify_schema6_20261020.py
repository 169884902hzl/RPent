"""Deliver the versioned schema6 interface and evidence to shared coordination."""
import argparse
import datetime
import fcntl
import hashlib
import json
from pathlib import Path
from zoneinfo import ZoneInfo


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,required=True)
    parser.add_argument('--commit',required=True)
    args=parser.parse_args();source=args.source.resolve(strict=True)
    files={name:{'path':str(source/name),'sha256':hashlib.sha256((source/name).read_bytes()).hexdigest()}
        for name in ('SKILL_PACKAGE_SPEC.md','rpent/skill_package/schema.json',
            'rpent/skill_package/contract.py','rpent/skill_package/__init__.py')}
    now=datetime.datetime.now(ZoneInfo('America/Los_Angeles')).isoformat()
    text=f'''
[Codex3 | {now} | schema6 CPU delivery; physical D remains open]
Source {args.commit}; snapshot {source}. Schema bounded-skills/6; legal public-request-legal/3. Files/SHA: {json.dumps(files)}.
Codex2: move_to now selects anchor only; other approach directions appear only after that anchor fails, and path is planner-owned. New finite skill guarded_move(anchor_id,axis,direction ±1). New anchor capture_step plus cached=true for reused measurements; request.progress={{version,stagnant_decisions,limit}}. New scopes planner_selected_variant_pending/reused_endpoint_ik/guarded_contact_increment preserve unknown full-path collision. Receipt may include measured advance_m. Existing legal/selected/rule_acceptable field names remain. Use shared legal_after for labels and decoding; guarded endpoints need actual receipt and stagnation permits only finish/ask_help. Do not header-migrate old requests/labels: candidate identities and legality changed; regenerate from matched source. A/B coding deferred by user. Candidate order remains nonsemantic.
CPU: original220 only selected N31, preserves all131 successes, saves0 historical wall seconds; smaller N cuts successes. Original24 incremental r1 retained (169/610 proposed caches differ>1cm), conservative dual-view r2 compares1289, caches56 with position/size differences0 and misses0. Saved3 registration JSON and6 plane masks byte-equal; batching alone gives little registration speedup. Related tests384 passed; final hybrid/guarded25 passed. No model training, no physical qualification claim.
Evidence {source}/coordination/bounded_skills_20261016/progress_schema6_20261020.md and reports/schema6_*.json. Prepared same-source D: move100 pairs, drawer open/close20 pairs each, fixed32 N1 versus both10698 arms, D2 forty×recovery0/1/2 (separate denominators/envelope/full replay). Every batch first requires real same-launcher startup. D2/confirmation remain excluded from training.
Resources:10688_2 cancelled with9 completed workers retained and one unfinished spatial_task_t4 registered for retry; C2 10749 started21:01:42 cluster time. Return latency1109s exceeds600s; violation retained. Failed CPU gate10748 retained;10699 now waits10698 because C2 trial has actually started. C3 keeps only10698 on node02; no c5/c6/rf/p3a5 or held changes. C1 D2 attribution originals remain under /public/home/sunyihan/rpent_libero_eval/results/bounded_skills/{{D2_public_binding_hybrid_20261020,D2_cached_binding_hybrid_20261020}}/3968bdb4/job1068*/N8/;10699/source6a2d6bb8 separate.
'''
    path=Path('/public/home/sunyihan/rd_instruction_20260923/COORDINATION.md');raw=text.encode()
    with path.open('ab') as stream:
        fcntl.flock(stream,fcntl.LOCK_EX);start=stream.tell();stream.write(raw);stream.flush();end=stream.tell()
    receipt={'start':start,'end':end,'sha256':hashlib.sha256(raw).hexdigest(),'files':files,'source_commit':args.commit}
    out=Path('/public/home/sunyihan/rpent_libero_eval/results/bounded_skills/schema6_20261020/interface_delivery.json')
    with out.open('x') as stream:json.dump(receipt,stream,indent=2)
    print(json.dumps(receipt))


if __name__=='__main__':main()
