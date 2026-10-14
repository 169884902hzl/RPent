"""Pin alternate pregrasp orientation and complete public pad calibration."""
import copy
import hashlib
import json
from pathlib import Path
import shutil
import sys
import tarfile

import numpy as np

ROOT=Path('/public/home/sunyihan/rpent_libero_eval')
OLD=ROOT/'results/harness_v5/unified_route_paired_selection_20261011_r5'
OUT=ROOT/'results/harness_v5/unified_route_paired_selection_20261011_r6'
PATCH=ROOT/'coordination/unified_low_orientation_patch_20261011'


def pin(path):
    return {'path':str(path),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    previous=json.loads((OLD/'manifest.json').read_text())
    parent=Path(previous['source_snapshot']['path'])
    source=ROOT/'source_v5_unified_route_selection_20261011_r6'
    shutil.copytree(parent,source,symlinks=True,ignore=shutil.ignore_patterns('__pycache__'))
    changed=[]
    for relative in ('robots/libero/v5_grasp_route.py','robots/libero/v5_runtime.py',
                     'tests/unit_tests/robots/libero/test_v5_grasp_route.py',
                     'tests/unit_tests/robots/libero/test_v5_opposed_pad_window.py'):
        shutil.copyfile(PATCH/relative,source/relative)
        changed.append(pin(PATCH/relative))
    sys.path.insert(0,str(source))
    from scripts.probe_v5_gripper513_calibration_cpu import panda_static_geometry
    OUT.mkdir(parents=True,exist_ok=False)
    base_path=ROOT/'results/harness_v5/unified_route_paired_selection_20261011_r2/common_base_config.json'
    config=json.loads(base_path.read_text())
    calibration=config['grasp_measurement_calibration']
    old_geometry=copy.deepcopy(calibration['grip_site_geometry'])
    xml=Path(old_geometry['xml']['path'])
    if pin(xml)!=old_geometry['xml']:raise ValueError('static robot geometry changed')
    geometry=panda_static_geometry(xml)
    # Reuse the same rigid transform and scalar calibration. Only the missing
    # individual pad descriptors are added; no threshold is fitted here.
    for key,value in old_geometry.items():
        if isinstance(value,list):
            if not np.allclose(value,geometry[key],atol=1e-12,rtol=0):
                raise ValueError('existing static geometry differs: '+key)
        elif value!=geometry[key]:
            raise ValueError('existing static geometry differs: '+key)
    calibration['grip_site_geometry']=geometry
    calibration['static_pad_geometry_enrichment']={
        'version':'same-public-robot-xml-individual-pads/1-dev',
        'source':pin(source/'scripts/probe_v5_gripper513_calibration_cpu.py'),
        'xml':pin(xml),'parent_config':pin(base_path),
        'previous_rigid_transform_and_opening_calibration_preserved':True,
        'private_object_truth_used':False}
    new_config=OUT/'common_base_config.json'
    new_config.write_text(json.dumps(config,indent=2)+'\n')
    identity={**previous['source_snapshot'],'path':str(source),'snapshot_id':source.name,
        'parent_source_path':str(parent),'purpose':'screen alternate lower-pregrasp wrist rotation; reject enabled pad verifier with missing static geometry',
        'changed_modules':changed,
        'CPU_validation':{'result':'40 passed; existing pytest timeout config warning',
            'command':'focused grasp route, geometry, public tracking and opposed pad window tests'},
        'files':[{**pin(p),'relative_path':str(p.relative_to(source))} for p in sorted(source.rglob('*.py'))]}
    identity.pop('archive',None)
    (source/'source_identity_v3r9.json').write_text(json.dumps(identity,indent=2)+'\n')
    archive=source.with_suffix('.tar')
    with tarfile.open(archive,'x') as stream:
        for child in source.iterdir():stream.add(child,arcname=child.name)
    identity['archive']={**pin(archive),'archive_complete':True}
    entries=[]
    for entry in previous['registered_plans']:
        if entry['arm']=='locked':
            entries.append(entry);continue
        original=Path(entry['plan']['path'])
        if pin(original)!=entry['plan']:raise ValueError('parent plan changed')
        plan=json.loads(original.read_text())
        plan.update(source_path=str(source),source_snapshot=identity,corrected_parent_plan=pin(original),
            base_config=pin(new_config),planner_correction='alternate_lower_wrist_orientation_and_required_pad_geometry',
            producer=pin(Path(__file__)))
        plan['producer_dependencies'] += [pin(Path(__file__)),pin(new_config),*changed]
        destination=OUT/entry['category']/'unified/preparation/selection.json'
        destination.parent.mkdir(parents=True,exist_ok=False)
        destination.write_text(json.dumps(plan,indent=2)+'\n')
        entries.append({**entry,'plan':pin(destination),'physical_submitted':False,'CPU_preflight':'required_at_submission'})
    manifest={**previous,'registered_plans':entries,'source_snapshot':identity,'producer':pin(Path(__file__)),
        'paired_baseline_reused':True,'parent_manifest':pin(OLD/'manifest.json'),
        'base_config':pin(new_config),'opening_force_and_simulation_budget_changed':False,
        'prior_development_failures_preserved':True,'confirmation':False}
    (OUT/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    locked=[entry for entry in json.loads((OLD/'startup_manifest.json').read_text()) if entry['arm']=='locked']
    (OUT/'startup_manifest.json').write_text(json.dumps(locked,indent=2)+'\n')
    print(json.dumps({'archive':identity['archive'],'new_config':pin(new_config),
        'individual_finger_pads':len(geometry['finger_pads'])}))


if __name__=='__main__':main()
