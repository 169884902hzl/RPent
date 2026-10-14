"""Register the current-robot point filtering fix in a new development source."""
import hashlib
import json
from pathlib import Path
import shutil
import tarfile

ROOT=Path('/public/home/sunyihan/rpent_libero_eval')
OLD=ROOT/'results/harness_v5/unified_route_paired_selection_20261011_r3'
OUT=ROOT/'results/harness_v5/unified_route_paired_selection_20261011_r4'
PATCH=ROOT/'coordination/unified_arm_filter_patch_20261011'


def pin(path):
    return {'path':str(path),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    previous=json.loads((OLD/'manifest.json').read_text())
    parent=Path(previous['source_snapshot']['path'])
    source=ROOT/'source_v5_unified_route_selection_20261011_r4'
    shutil.copytree(parent,source,symlinks=True,ignore=shutil.ignore_patterns('__pycache__'))
    changed=[]
    for relative in ('robots/libero/v5_analytic_grasp.py','robots/libero/v5_grasp_kinematics.py',
                     'tests/unit_tests/robots/libero/test_v5_grasp_kinematics.py'):
        shutil.copyfile(PATCH/relative,source/relative)
        changed.append(pin(PATCH/relative))
    identity={**previous['source_snapshot'],'path':str(source),'snapshot_id':source.name,
              'parent_source_path':str(parent),'purpose':'remove current robot arm points from static scene using public joints and static meshes',
              'changed_modules':changed,'CPU_validation':{'result':'9 passed, 1 existing pytest timeout config warning',
              'command':'OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 .venv/bin/python -m pytest -q tests/unit_tests/robots/libero/test_v5_grasp_kinematics.py tests/unit_tests/robots/libero/test_v5_grasp_route.py'},
              'files':[{**pin(p),'relative_path':str(p.relative_to(source))}
                       for p in sorted(source.rglob('*.py'))]}
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
        p=Path(entry['plan']['path'])
        if pin(p)!=entry['plan']:raise ValueError('parent plan changed')
        plan=json.loads(p.read_text())
        plan.update(source_path=str(source),source_snapshot=identity,corrected_parent_plan=pin(p),
                    planner_correction='filter_current_arm_from_static_scene_using_public_fk',producer=pin(Path(__file__)))
        plan['producer_dependencies'] += [pin(Path(__file__)),*changed]
        destination=OUT/entry['category']/'unified/preparation/selection.json'
        destination.parent.mkdir(parents=True,exist_ok=False)
        destination.write_text(json.dumps(plan,indent=2)+'\n')
        entries.append({**entry,'plan':pin(destination),'physical_submitted':False,'CPU_preflight':'required_at_submission'})
    manifest={**previous,'registered_plans':entries,'source_snapshot':identity,'producer':pin(Path(__file__)),
              'paired_baseline_reused':True,'parent_manifest':pin(OLD/'manifest.json')}
    (OUT/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    starters=[entry for entry in json.loads((OLD/'startup_manifest.json').read_text()) if entry['arm']=='locked']
    (OUT/'startup_manifest.json').write_text(json.dumps(starters,indent=2)+'\n')
    print(json.dumps({'source':identity['archive'],'baseline_startups_reused':[entry['startup_job'] for entry in starters]}))


if __name__=='__main__':main()
