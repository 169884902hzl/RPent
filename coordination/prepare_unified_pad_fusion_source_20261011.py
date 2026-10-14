"""Pin synchronized dual-camera pad-fusion verifier for development only."""
import hashlib
import json
from pathlib import Path
import shutil
import tarfile

ROOT = Path('/public/home/sunyihan/rpent_libero_eval')
OLD = ROOT/'results/harness_v5/unified_route_paired_selection_20261011_r9'
OUT = ROOT/'results/harness_v5/unified_route_paired_selection_20261011_r10'
PATCH = ROOT/'coordination/unified_pad_fusion_patch_20261011'

def pin(path):
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}

def main():
    previous = json.loads((OLD/'manifest.json').read_text())
    parent = Path(previous['source_snapshot']['path'])
    source = ROOT/'source_v5_unified_route_selection_20261011_r10'
    shutil.copytree(parent, source, symlinks=True, ignore=shutil.ignore_patterns('__pycache__'))
    changed=[]
    for rel in ('robots/libero/v5_grasp_public_tracking.py',
                'tests/unit_tests/robots/libero/test_v5_opposed_pad_window.py'):
        dest=source/rel; shutil.copyfile(PATCH/rel,dest)
        changed.append({**pin(dest),'relative_path':rel})
    identity={**previous['source_snapshot'],'path':str(source),'snapshot_id':source.name,
        'parent_source_path':str(parent),
        'purpose':'synchronized agentview+wrist public pad-face union over two fresh frames',
        'changed_modules':changed,
        'CPU_validation':{'result':'5 passed; existing pytest timeout configuration warning',
            'tests':'opposed-pad verifier incl complementary dual-view fusion'},
        'files':[{**pin(p),'relative_path':str(p.relative_to(source))}
                 for p in sorted(source.rglob('*.py'))]}
    identity.pop('archive',None)
    (source/'source_identity_v3r9.json').write_text(json.dumps(identity,indent=2)+'\n')
    archive=source.with_suffix('.tar')
    with tarfile.open(archive,'x') as stream:
        for child in source.iterdir(): stream.add(child,arcname=child.name)
    identity['archive']={**pin(archive),'archive_complete':True}
    OUT.mkdir(parents=True,exist_ok=False)
    entries=[]
    config_path=Path(next(e for e in previous['registered_plans'] if e['arm']=='unified')['plan']['path'])
    old_plan=json.loads(config_path.read_text())
    config=Path(old_plan['base_config']['path'])
    if pin(config)!=old_plan['base_config']: raise ValueError('parent config changed')
    base_data=json.loads(config.read_text()); base=OUT/'common_base_config.json'
    base.write_text(json.dumps(base_data,indent=2)+'\n')
    for entry in previous['registered_plans']:
        if entry['arm']=='locked': entries.append(entry); continue
        old=Path(entry['plan']['path'])
        if pin(old)!=entry['plan']: raise ValueError('parent plan changed')
        plan=json.loads(old.read_text())
        plan.update(source_path=str(source),source_snapshot=identity,base_config=pin(base),
                    corrected_parent_plan=pin(old),planner_correction='dual_view_pad_face_union',
                    producer=pin(Path(__file__)))
        plan['producer_dependencies'] += [pin(Path(__file__)),*changed]
        dest=OUT/entry['category']/'unified/preparation/selection.json'; dest.parent.mkdir(parents=True)
        dest.write_text(json.dumps(plan,indent=2)+'\n')
        entries.append({**entry,'plan':pin(dest),'physical_submitted':False,'CPU_preflight':'required_at_submission'})
    (OUT/'manifest.json').write_text(json.dumps({**previous,'registered_plans':entries,
        'source_snapshot':identity,'base_config':pin(base),'producer':pin(Path(__file__)),
        'parent_manifest':pin(OLD/'manifest.json'),'paired_baseline_reused':True,
        'opening_force_and_simulation_budget_changed':False,'prior_development_failures_preserved':True,
        'confirmation':False},indent=2)+'\n')
    locked=[e for e in json.loads((OLD/'startup_manifest.json').read_text()) if e['arm']=='locked']
    (OUT/'startup_manifest.json').write_text(json.dumps(locked,indent=2)+'\n')
    print(json.dumps({'archive':identity['archive'],'config':pin(base),'paired_states_changed':False}))

if __name__=='__main__': main()
