"""Describe original-train endpoint evidence; never replay or change a threshold."""
import argparse
from collections import Counter
import json
import math
from pathlib import Path


def agreement(counts):
    n=sum(counts.values());k=counts['TP']+counts['TN'];z=1.959963984540054
    c=(k/n+z*z/(2*n))/(1+z*z/n)
    h=z*math.sqrt(k*(n-k)/n**3+z*z/(4*n*n))/(1+z*z/n)
    return {'n':n,'correct':k,'agreement':k/n,'wilson95':[c-h,c+h]}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--rows',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    rows=json.loads(args.rows.read_bytes())
    assert len(rows)==285
    def evidence(row):
        hold=row.get('post_hold') or {}
        aperture=hold.get('aperture') or {}
        return (hold.get('relative_displacement_m'),hold.get('hand_displacement_m'),
            aperture.get('opening_m'),aperture.get('empty_closed_upper_m'))
    def coupled(row):
        relative,_,_,_=evidence(row)
        return relative is not None and relative<=.01
    def motion_ratio(row):
        relative,hand,_,_=evidence(row)
        return relative is not None and hand is not None and relative<=.5*hand
    def hand_motion(row):
        _,hand,_,_=evidence(row)
        return hand is not None and hand>=.01
    def aperture_margin(row,margin):
        _,_,opening,empty=evidence(row)
        return opening is not None and empty is not None and opening>empty+margin
    guards={'unchanged':lambda _:True, 'relative_10mm':coupled,
        'relative_at_most_half_hand_motion':motion_ratio,'hand_motion_10mm':hand_motion,
        'empty_upper_plus_1mm':lambda r:aperture_margin(r,.001),
        'empty_upper_plus_2mm':lambda r:aperture_margin(r,.002),
        'relative_10mm_and_half_hand_motion':lambda r:coupled(r) and motion_ratio(r),
        'relative_10mm_and_empty_plus_2mm':lambda r:coupled(r) and aperture_margin(r,.002)}
    reports={}
    for name,guard in guards.items():
        counts=Counter();by_category={};suppressed=[]
        for row in rows:
            accepted=row['public_completed'] and guard(row)
            truth=row['private_success']
            category=by_category.setdefault(row['category'],Counter())
            label=('TP' if truth else 'FP') if accepted else ('FN' if truth else 'TN')
            counts[label]+=1;category[label]+=1
            if row['public_completed'] and not accepted:
                suppressed.append({'case':row['case'],'seed':row['trial_seed'],
                    'original_class':row['classification'],'public_evidence':evidence(row)})
        reports[name]={'counts':dict(counts),**agreement(counts),
            'by_category':{key:{'counts':dict(value),**agreement(value)} for key,value in by_category.items()},
            'precision':counts['TP']/(counts['TP']+counts['FP']) if counts['TP']+counts['FP'] else None,
            'recall':counts['TP']/(counts['TP']+counts['FN']),'suppressed':suppressed}
    assert reports['unchanged']['counts']=={'TP':77,'TN':168,'FP':26,'FN':14}
    result={'positions_source':str(args.rows),'endpoints':len(rows),'variants':reports,
        'missing_public_measurement_retained_separately':3,
        'scope':'offline final-public-measurement guards only; not counterfactual policy stopping or physical outcomes',
        'thresholds_changed':False,'production_code_changed':False,
        'PRO':False,'D2':False,'confirmation':False,'training_executed':False}
    with args.output.open('x') as stream:json.dump(result,stream,indent=2)
    print(json.dumps({k:{q:v[q] for q in ('counts','agreement','precision','recall')} for k,v in reports.items()}))


if __name__=='__main__':main()
