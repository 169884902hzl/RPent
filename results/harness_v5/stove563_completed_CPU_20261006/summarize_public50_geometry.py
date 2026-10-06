"""Descriptive original capture statistics; existing private labels score only."""

import csv
import hashlib
import json
from pathlib import Path

import numpy as np


def main():
    packet = Path(__file__).resolve().parent
    geometry = json.loads((packet/'public50_geometry.json').read_text())
    labels = json.loads((packet/'labels80_scoring_table.json').read_text())['records']
    by_capture = {(r['case'],r['phase'],r['stage']):r for r in labels}
    records = geometry['records']
    groups = {}
    for name, predicate in [('neutral',(False,False)),('true_on',(True,False)),('true_off',(False,True))]:
        rows = [r for r in records if (by_capture[(r['case'],r['phase'],r['stage'])]['true_on'],
                                     by_capture[(r['case'],r['phase'],r['stage'])]['true_off']) == predicate]
        baseline = [r['profiles'].get('64',[]) for r in rows]
        groups[name] = {'views':len(rows),'unique_components':sum(len(f)==1 for f in baseline),
            'unique_supported_base':sum(len(f)==1 and bool(f[0]['base'] and f[0]['base']['base_fit_supported']) for f in baseline),
            'candidate_angle':sum(r.get('candidate_angle_deg') is not None for r in rows)}
    unique_thresholds = []
    sigmas = []
    for row in records:
        profiles = [row['profiles'].get(key,[]) for key in ('40','64','80')]
        if all(len(fits)==1 and fits[0]['base'] and fits[0]['base']['base_fit_supported'] for fits in profiles):
            unique_thresholds.append({'frame':row['frame'],'centre_spread_m':row['threshold_centre_spread_m']})
        for fit in row['profiles'].get('64',[]):
            if fit['base'] and fit['base']['base_fit_supported']:
                sigmas.append(float(np.linalg.norm(fit['base']['bootstrap_centre_sigma_xy_m'])))

    def quantiles(values):
        return dict(zip(('median','p95','max'),np.quantile(values,[.5,.95,1]).tolist())) if values else None

    refs = []
    remote_root = Path('/public/home/sunyihan/rpent_libero_eval')
    for filename,expected in [('fit_full_frame_public_control_parts.py','17892bacf8df3c99f1543fef2795a4ee6557fd941e7f64bd2722019c5db1208b'),
                              ('measure_public_shell_reference.py','5e9c10b481cc290d7aa7d5b22c0bc7c28f67902dda66dda1b7d8895ea61c3cb2')]:
        local=packet.parent/'stove559_public_geometry_CPU_20261006'/filename
        actual=hashlib.sha256(local.read_bytes()).hexdigest()
        if actual!=expected:
            raise ValueError('original public helper changed')
        refs.append({'path':str(remote_root/'results/harness_v5/stove559_public_geometry_CPU_20261006'/filename),
                     'sha256':actual,'function':'circle_fit' if filename.startswith('fit_') else 'shell_edges'})
    report={'total':geometry['total'],'by_phase_stage_camera':geometry['by_phase_stage_camera'],
            'posthoc_private_scoring_groups':groups,'private_labels_used_for_geometry_selection':False,
            'private_labels_source':'Only previously authorized labels80_scoring_table.json, no additional private labels opened',
            'uncertainty':{'unique_supported_single_component_at_all_3_thresholds':len(unique_thresholds),
                           'unique_threshold_centre_spread_m':quantiles([r['centre_spread_m'] for r in unique_thresholds]),
                           'individual_base_conditional_bootstrap_sigma_count':len(sigmas),
                           'individual_base_conditional_bootstrap_sigma_m':quantiles(sigmas),
                           'scope':'Conditional fit noise is not total uncertainty; multiple-component identity switches are excluded from the unique-threshold summary'},
            'unique_threshold_examples':unique_thresholds,'known559_reproduction':geometry['known559_reproduction'],
            'known559_all_match':all(r['matches'] for r in geometry['known559_reproduction']),
            'pinned_public_helpers':refs,'thresholds_unchanged':True,'endpoint_qualified':False,
            'on_off_endpoints_calibrated':False,'runtime_changed':False,'GPU_submitted':False,'simulator_started':False}
    (packet/'public50_summary.json').write_text(json.dumps(report,indent=2)+'\n')
    with (packet/'public50_scoring_table.csv').open('w',newline='') as stream:
        writer=csv.writer(stream)
        writer.writerow(['frame','source_step','private_q_rad','true_on','true_off','component_count64','unique_supported_base64',
                         'candidate_angle_deg','endpoint_state','scope'])
        for row in records:
            label=by_capture[(row['case'],row['phase'],row['stage'])]
            fits=row['profiles'].get('64',[])
            base_supported=len(fits)==1 and bool(fits[0]['base'] and fits[0]['base']['base_fit_supported'])
            writer.writerow([row['frame'],row['source_step'],label['q_rad'],label['true_on'],label['true_off'],len(fits),
                             base_supported,row.get('candidate_angle_deg'),'unmeasured','private_scoring_only_not_runtime_or_training'])
    print(json.dumps({'by_private_group':groups,'all_10_known_views_match':report['known559_all_match'],
                      'centre_threshold_spread_m':report['uncertainty']['unique_threshold_centre_spread_m']}))


if __name__=='__main__':
    main()
