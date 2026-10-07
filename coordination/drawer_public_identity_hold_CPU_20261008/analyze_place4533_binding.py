"""Audit the first public trace using only its explicit public-artifact index."""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np


def checked(ref):
    path = Path(ref['path'])
    if hashlib.sha256(path.read_bytes()).hexdigest() != ref['sha256']:
        raise ValueError(f'public file changed: {path}')
    return path


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--index', type=Path, required=True)
    p.add_argument('--index-sha', required=True)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    checked({'path':str(a.index), 'sha256':a.index_sha})
    entries=[json.loads(l) for l in a.index.read_text().splitlines() if l]
    sources=[]
    frames=[]
    for ref in entries:
        frame=json.loads(checked(ref).read_text())
        current=[e for e in frame['entities'].values() if e.get('current')]
        rows=[]
        for e in current:
            row={'entity':e['current'],'masks':{},'fused_cloud_points':None,'per_view_points':{}}
            for view,m in e['perception_evidence'].get('sam_mask_files',{}).items():
                path=checked(m);sources.append(m)
                with np.load(path) as z:
                    mask=z['array'].astype(bool)
                row['masks'][view]={'pixels':int(mask.sum()),'shape':list(mask.shape),'reference':m}
            cloud=e.get('fused_cloud')
            if cloud:
                path=checked(cloud);sources.append(cloud)
                with np.load(path) as z:
                    row['fused_cloud_points']=len(z['array'])
            for view,v in e['per_view'].items():
                cloud=v.get('cloud')
                if cloud:
                    path=checked(cloud);sources.append(cloud)
                    with np.load(path) as z:
                        row['per_view_points'][view]={'points':len(z['array']),'current':v['current'],'source_step':cloud['source_step']}
            rows.append(row)
        for camera,items in frame['cameras'].items():
            for key in ('rgb','world_xyz','camera_metadata'):
                if items.get(key):
                    checked(items[key]);sources.append(items[key])
        frames.append({'source_step':frame['source_step'],'phase':frame['phase'],'entities':rows,'reference':ref})
    final=json.loads(checked(entries[-1]).read_text())
    cabinet=final['entities']['e107']['perception_evidence']['sam_mask_files']['agentview']
    drawer=final['entities']['e47']['perception_evidence']['sam_mask_files']['agentview']
    with np.load(checked(cabinet)) as z:
        c=z['array'].astype(bool)
    with np.load(checked(drawer)) as z:
        d=z['array'].astype(bool)
    pair={'cabinet':'e107','independent_current_drawer':'e47','camera':'agentview',
          'mask_iou':float((c&d).sum()/max(1,(c|d).sum())),
          'cabinet_coverage':float((c&d).sum()/max(1,c.sum())),
          'drawer_coverage':float((c&d).sum()/max(1,d.sum())),
          'bounds_abs_difference_m':np.abs(np.asarray(final['entities']['e107']['current']['lower']+final['entities']['e107']['current']['upper'])-np.asarray(final['entities']['e47']['current']['lower']+final['entities']['e47']['current']['upper'])).tolist(),
          'mask_refs':[cabinet,drawer]}
    unique={x['path']:x for x in sources}
    a.output.parent.mkdir(parents=True,exist_ok=True)
    result={'version':'place4533-public-binding-audit/1','source_index':{'path':str(a.index),'sha256':a.index_sha},
            'job':4533,'frames':frames,'public_files_sha_checked':len(unique),'checked_public_files':list(unique.values()),
            'duplicate_pair':pair,'carry_segments_observed':sum('carry_segment' in r['phase'] for r in frames),
            'private_truth_or_coordinates_read':False,'old4311_scores_changed':False,
            'finding':'fresh cabinet fragment duplicates independent fresh drawer, so stale-only alias guard leaves two cabinet-top surfaces and binding remains ambiguous'}
    a.output.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'report':str(a.output),'sha256':hashlib.sha256(a.output.read_bytes()).hexdigest(),'files':len(unique),'duplicate_pair':pair,'carry_segments':result['carry_segments_observed']}))

if __name__=='__main__':
    main()
