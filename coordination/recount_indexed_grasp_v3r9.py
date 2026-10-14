from pathlib import Path
import hashlib,json,collections,sys,datetime
ROOT=Path('/public/home/sunyihan/rpent_libero_eval')
INDEX=ROOT/'coordination/grasp_truth_registered_v3_history_20261010_r2'
manifest=json.loads((INDEX/'index_manifest.json').read_text())
expected=manifest['index_sha256'];raw=(INDEX/'input_rows.jsonl').read_bytes()
if hashlib.sha256(raw).hexdigest()!=expected:raise RuntimeError('immutable index changed')
sys.path.insert(0,str(ROOT/'source_v5_grasp_truth_v3r9_20261010_r1'))
from robots.libero.v5_grasp_truth import grasp_trace_summary_v3,sustained_grasp_v3
OUT=INDEX/'recount';OUT.mkdir(exist_ok=False)
records=[];last=None;input_rows=[]
for line in raw.splitlines():
 idx=json.loads(line)
 if idx['captured_path']!=last:
  captured=Path(idx['captured_path']);data=captured.read_bytes()
  if hashlib.sha256(data).hexdigest()!=idx['input_sha256']:raise RuntimeError('captured historical source changed')
  input_rows=data.splitlines();last=idx['captured_path']
 rowbytes=input_rows[idx['line']-1]
 if hashlib.sha256(rowbytes).hexdigest()!=idx['raw_row_sha256']:raise RuntimeError('indexed row changed')
 r=json.loads(rowbytes);fa=r.get('first_attempt') or {};phase=r.get('private_grasp_phase') or {};hold=fa.get('private_setup_hold') or {}
 samples=phase.get('samples') or hold.get('samples') or [];ref=phase.get('reference') or hold.get('reference')
 reasons=[];new=None;end=None
 if not ref or ref.get('original_support_plane_z_m') is None:
  reasons.append('missing_original_support_plane_identity')
 if not samples:reasons.append('missing_physical_contact_samples')
 if samples and not all('relative_com_tcp' in s and 'dual_finger_contact' in s for s in samples):reasons.append('missing_mass_weighted_com_tcp_or_dual_finger_samples')
 if samples and not all('integration_state' in s for s in samples):reasons.append('missing_full_integration_state')
 if samples and not any((s.get('counterfactual_support_evidence') or {}).get('version')=='isolated-target-gripper-removal/1' for s in samples):reasons.append('missing_registered_isolated_gripper_removal')
 if samples and ref:
  result=grasp_trace_summary_v3(ref,samples);new=result['true_sustained_grasp_during_skill'];end=result['true_sustained_grasp_at_end']
 records.append({**idx,'registered_v3_during':new,'registered_v3_end':end,'unknown_reasons':reasons if new is None else [],
   'historical_nonregistered_v3r8':(fa.get('private_hold_truth_v3') or {}).get('success'),
   'public_verifier':(fa.get('receipt') or r.get('receipt') or {}).get('grasp_verified'),
   'new_replay':False,'old_records_unchanged':True})
report={'generated_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'registration_id':'grasp_truth_v3_1153_20261009',
 'input_index_sha256':expected,'indexed_rows':len(records),'truth_source_sha256':hashlib.sha256((ROOT/'source_v5_grasp_truth_v3r9_20261010_r1/robots/libero/v5_grasp_truth.py').read_bytes()).hexdigest(),
 'coverage_exhaustive':manifest['exhaustive_claim'],'coverage_review_pending':True,
 'old_labels':dict(collections.Counter(str(r['old_label']) for r in records)),
 'registered_v3':dict(collections.Counter(str(r['registered_v3_during']) for r in records)),
 'unknown_reasons':dict(collections.Counter(reason for r in records for reason in r['unknown_reasons'])),
 'categories':dict(collections.Counter(str(r['category']) for r in records)),
 'methods':dict(collections.Counter(str(r['method']) for r in records)),
 'control_visibility':False,'old_values_not_overwritten':True}
(OUT/'rows.jsonl').write_text(''.join(json.dumps(r,sort_keys=True)+'\n' for r in records))
(OUT/'summary.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
