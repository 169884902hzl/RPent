# Copyright 2026 The RPent Authors.
# SPDX-License-Identifier: Apache-2.0
"""Distinguish sampled route failures from endpoint numerical IK failures."""
import copy
import hashlib
import json
import os
import sys
import time
from pathlib import Path

os.environ.update(CUDA_VISIBLE_DEVICES='', OPENBLAS_NUM_THREADS='1')
root=Path('/public/home/sunyihan/rpent_libero_eval')
source=root/'source_bounded_chunk_v3_current_handle_20261019_ede83b18'
sys.path.insert(0,str(source))
from robots.libero.bounded_offline_labels import load_annotation_state

records=[]
for job in ('9611_120','9611_140'):
    choices,= (root/f'results/bounded_skills/feasibility_20261017/job{job}').glob('*oracle_k4/choices.jsonl')
    rows=[json.loads(line) for line in choices.read_text().splitlines()]
    selected=[]
    for index,row in enumerate(rows):
        for d in row.get('candidate_screen_diagnostics',[]):
            if d.get('stage')=='measured_surface_contact' and d.get('anchor_id')=='e114':
                failed=[c for c in d['candidates'] if (c.get('screen') or {}).get('reason')=='numerical_ik_not_found']
                if failed: selected.append((index,row,d,failed))
    if not selected:
        records.append({'job':job,'no_matching_route_failure':True});continue
    index,row,diagnostic,candidates=selected[-1]
    ref=row['private_prefix_annotation_state']
    saved=load_annotation_state(ref['path'],ref['sha256'])
    adapter=saved['adapter']
    screen=adapter._cloud_and_ik('e114',contact=True)
    endpoint_rows=[]
    started=time.perf_counter()
    for number,candidate in enumerate(candidates):
        ik=copy.deepcopy(screen.ik)
        ik.route_joint_step_rad=None
        ik.last_solution=None
        ik.cache={}
        solved=ik.check(candidate['xyz_m'],candidate['quat_xyzw'])
        endpoint_rows.append({'index':number,'yaw_deg':candidate['yaw_deg'],'path':candidate['path'],
            'contact_xyz_m':candidate['contact_xyz_m'],'eef_target_xyz_m':candidate['xyz_m'],
            'approach_xyz_m':candidate['approach_xyz_m'],'normal_xyz':candidate['normal_xyz'],
            'recorded_route_reason':candidate['screen']['reason'],
            'endpoint_solution_found':solved['solution_found'],'endpoint_solves':solved['solves']})
    records.append({'job':job,'row':index,'choices_sha256':hashlib.sha256(choices.read_bytes()).hexdigest(),
        'context':ref,'robot':row['request']['robot'],
        'microwave_anchors':[a for a in row['request']['anchors'] if 'microwave' in a['label']],
        'route_failures':len(candidates),'endpoint_solutions':sum(r['endpoint_solution_found'] for r in endpoint_rows),
        'candidates':endpoint_rows,'cpu_s':time.perf_counter()-started})
report={'source_commit':'ede83b18','scope':'saved public pose and static robot endpoint IK diagnosis; global endpoint solve is NOT a screened continuous route',
    'physics_steps':0,'rpc_calls':0,'gpu_used':False,'training':False,'records':records,
    'script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
out=root/'coordination/bounded_skills_20261016/reports/microwave9611_endpoint_IK_CPU_20261019.json'
with out.open('x') as f:json.dump(report,f,indent=2);f.write('\n')
print(json.dumps({'output':str(out),'records':[{k:r.get(k) for k in ('job','row','route_failures','endpoint_solutions','cpu_s')} for r in records]}))
