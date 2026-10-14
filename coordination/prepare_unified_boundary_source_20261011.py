"""Pin boundary refinement and exact broad-phase acceleration for development."""
import hashlib
import json
from pathlib import Path
import shutil
import tarfile

ROOT=Path('/public/home/sunyihan/rpent_libero_eval')
OLD=ROOT/'results/harness_v5/unified_route_paired_selection_20261011_r4'
OUT=ROOT/'results/harness_v5/unified_route_paired_selection_20261011_r5'
PATCH=ROOT/'coordination/unified_boundary_patch_20261011'


def pin(path):
    return {'path':str(path),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    previous=json.loads((OLD/'manifest.json').read_text())
    parent=Path(previous['source_snapshot']['path'])
    source=ROOT/'source_v5_unified_route_selection_20261011_r5'
    shutil.copytree(parent,source,symlinks=True,ignore=shutil.ignore_patterns('__pycache__'))
    changed=[]
    for relative in ('robots/libero/v5_grasp_route.py','robots/libero/v5_grasp_geometry.py',
                     'robots/libero/v5_grasp_public_tracking.py',
                     'tests/unit_tests/robots/libero/test_v5_grasp_geometry.py'):
        shutil.copyfile(PATCH/relative,source/relative)
        changed.append(pin(PATCH/relative))
    identity={**previous['source_snapshot'],'path':str(source),'snapshot_id':source.name,
        'parent_source_path':str(parent),'purpose':'recover omitted instance boundary pixels by measured depth continuity, retain exact obstacle membership',
        'changed_modules':changed,
        'CPU_validation':{'result':'35 passed; existing pytest timeout config warning',
            'command':'OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 .venv/bin/python -m pytest -q tests/unit_tests/robots/libero/test_v5_grasp_route.py tests/unit_tests/robots/libero/test_v5_grasp_geometry.py tests/unit_tests/robots/libero/test_v5_grasp_public_tracking.py'},
        'files':[{**pin(p),'relative_path':str(p.relative_to(source))} for p in sorted(source.rglob('*.py'))]}
    identity.pop('archive',None)
    (source/'source_identity_v3r9.json').write_text(json.dumps(identity,indent=2)+'\n')
    archive=source.with_suffix('.tar')
    with tarfile.open(archive,'x') as stream:
        for child in source.iterdir():stream.add(child,arcname=child.name)
    identity['archive']={**pin(archive),'archive_complete':True}
    OUT.mkdir(parents=True,exist_ok=False)
    entries=[]
    for entry in previous['registered_plans']:
        if entry['arm']=='locked':
            entries.append(entry);continue
        original=Path(entry['plan']['path'])
        if pin(original)!=entry['plan']:raise ValueError('parent plan changed')
        plan=json.loads(original.read_text())
        plan.update(source_path=str(source),source_snapshot=identity,corrected_parent_plan=pin(original),
            planner_correction='depth_continuous_instance_boundary_and_exact_broadphase',producer=pin(Path(__file__)))
        plan['producer_dependencies'] += [pin(Path(__file__)),*changed]
        destination=OUT/entry['category']/'unified/preparation/selection.json'
        destination.parent.mkdir(parents=True,exist_ok=False)
        destination.write_text(json.dumps(plan,indent=2)+'\n')
        entries.append({**entry,'plan':pin(destination),'physical_submitted':False,'CPU_preflight':'required_at_submission'})
    manifest={**previous,'registered_plans':entries,'source_snapshot':identity,'producer':pin(Path(__file__)),
        'paired_baseline_reused':True,'parent_manifest':pin(OLD/'manifest.json'),
        'r4_development_failures_preserved':True,'confirmation':False}
    (OUT/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    locked=[entry for entry in json.loads((OLD/'startup_manifest.json').read_text()) if entry['arm']=='locked']
    (OUT/'startup_manifest.json').write_text(json.dumps(locked,indent=2)+'\n')
    print(json.dumps({'archive':identity['archive'],'baseline_startups_reused':[entry['startup_job'] for entry in locked]}))


if __name__=='__main__':main()
