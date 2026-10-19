# Copyright 2026 The RPent Authors.
# SPDX-License-Identifier: Apache-2.0
"""Test the existing measured-handle entry routes on one measured door surface."""
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

choices,=(root/'results/bounded_skills/feasibility_20261017/job9611_120').glob('*oracle_k4/choices.jsonl')
row=[json.loads(line) for line in choices.read_text().splitlines()][1]
ref=row['private_prefix_annotation_state'];saved=load_annotation_state(ref['path'],ref['sha256'])
adapter=saved['adapter'];adapter.failed_contact_poses={}
entity=adapter.scene.entities['e114']
diagnostic,=(d for d in row['candidate_screen_diagnostics'] if d.get('stage')=='measured_surface_contact' and d.get('anchor_id')=='e114')
candidate=diagnostic['candidates'][0]
plan={k:candidate[k] for k in ('xyz_m','quat_xyzw','approach_xyz_m')}
plan.update(width_m=None,contact_kind='surface')
started=time.perf_counter();result=adapter._screen_fixture_approaches(entity,plan);elapsed=time.perf_counter()-started
report={'scope':'CPU new route proposal using existing handle-route screen on measured surface; no physical result',
 'source_commit':'ede83b18','context':ref,'choices_sha256':hashlib.sha256(choices.read_bytes()).hexdigest(),
 'row':1,'original_surface_candidate':candidate,'new_route':result,'cpu_s':elapsed,
 'diagnostics':adapter.candidate_diagnostics,'physics_steps':0,'rpc_calls':0,'gpu_used':False,'training':False,
 'failed_pose_history':'empty at this original row: prior actions are successful free moves, no failed contact',
 'script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
out=root/'coordination/bounded_skills_20261016/reports/microwave9611_entry_routes_CPU_20261019.json'
with out.open('x') as f:json.dump(report,f,indent=2);f.write('\n')
print(json.dumps({'output':str(out),'new_route_found':result is not None,'cpu_s':elapsed}))
