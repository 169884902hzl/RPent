"""Summarize public evidence limitations without changing closed labels."""
import hashlib
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent/'grasp_closed_measurement_diagnosis_20261011_r1'
SOURCE = ROOT/'verifier_fp_fn.jsonl'


def main():
    rows=[]
    for raw in map(json.loads,SOURCE.read_text().splitlines()):
        measured=(raw['verification_measurements'] or {}).get('independent_grasp') or {}
        checks=raw['private_final_checks'] or []
        failures=Counter()
        for check in checks:
            if check.get('clearance_m') is not None and check['clearance_m']<.03:
                failures['not_clear_of_original_support']+=1
            if check.get('dual_finger_contact') is False:
                failures['no_bilateral_target_contact']+=1
            if check.get('relative_com_displacement_m',0)>.01:
                failures['moves_in_gripper_window']+=1
        failed_public=sorted({key for frame in measured.get('frames',[]) for view in frame.get('per_view',{}).values()
                              for key,value in (view.get('conditions') or {}).items() if value is False})
        coupling=measured.get('coupled_lift_evidence') or {}
        if raw['error_direction']=='FP':
            limitation=('two_stationary_frames_do_not_measure_body_robot_comotion' if not coupling else
                        'rigid_body_comotion_does_not_establish_two_finger_contact')
        else:
            limitation='current_visible_surface_or_identity_does_not_measure_held_body'
        rows.append({key:raw[key] for key in ('case','group','layout_seed','state_sha256','input','line','error_direction')}|
                    {'private_failed_samples':dict(failures), 'public_false_conditions':failed_public,
                     'evidence_limitation':limitation,
                     'mechanical_cause_not_inferred_without_full_trace':True,
                     'closed_score_unchanged':True,'training_allowed':False})
    dest=ROOT/'verifier_causes.jsonl'
    dest.write_text(''.join(json.dumps(row)+'\n' for row in rows))
    report={'n':len(rows),'FP':sum(r['error_direction']=='FP' for r in rows),
            'FN':sum(r['error_direction']=='FN' for r in rows),
            'limitations':dict(Counter(r['error_direction']+'/'+r['evidence_limitation'] for r in rows)),
            'fn_condition_classes':dict(Counter(','.join(r['public_false_conditions']) for r in rows if r['error_direction']=='FN')),
            'input_sha256':hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
            'rows_sha256':hashlib.sha256(dest.read_bytes()).hexdigest(),
            'producer_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    (ROOT/'verifier_causes_summary.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))


if __name__=='__main__':
    main()
