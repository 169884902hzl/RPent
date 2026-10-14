"""Replace only the development planner snapshot; retain the paired baseline."""
import hashlib
import json
from pathlib import Path
import shutil
import tarfile

ROOT = Path('/public/home/sunyihan/rpent_libero_eval')
OLD = ROOT/'results/harness_v5/unified_route_paired_selection_20261011_r2'
OUT = ROOT/'results/harness_v5/unified_route_paired_selection_20261011_r3'
PATCH = ROOT/'coordination/v5_grasp_route_20261011_r2.py'


def pin(path):
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    old = json.loads((OLD/'manifest.json').read_text())
    parent = Path(old['source_snapshot']['path'])
    source = ROOT/'source_v5_unified_route_selection_20261011_r3'
    shutil.copytree(parent, source, symlinks=True, ignore=shutil.ignore_patterns('__pycache__'))
    shutil.copyfile(PATCH, source/'robots/libero/v5_grasp_route.py')
    identity = {**old['source_snapshot'], 'path': str(source), 'snapshot_id': source.name,
                'parent_source_path': str(parent), 'changed_module': pin(PATCH),
                'purpose': 'paired selection with exact measured target membership before scene voxelisation',
                'files': [{**pin(p), 'relative_path': str(p.relative_to(source))}
                          for p in sorted(source.rglob('*.py'))]}
    identity.pop('archive', None)
    (source/'source_identity_v3r9.json').write_text(json.dumps(identity, indent=2)+'\n')
    archive = source.with_suffix('.tar')
    with tarfile.open(archive, 'x') as stream:
        for child in source.iterdir():
            stream.add(child, arcname=child.name)
    identity['archive'] = {**pin(archive), 'archive_complete': True}
    OUT.mkdir(parents=True, exist_ok=False)
    plans = []
    for entry in old['registered_plans']:
        if entry['arm']=='locked':
            plans.append(entry)
            continue
        path = Path(entry['plan']['path'])
        if pin(path) != entry['plan']:
            raise ValueError('parent selection plan changed')
        plan = json.loads(path.read_text())
        plan.update(source_path=str(source), source_snapshot=identity,
                    corrected_parent_plan=pin(path), planner_correction='exact_target_pixel_membership_before_voxel',
                    producer=pin(Path(__file__)))
        plan['producer_dependencies'] += [pin(Path(__file__)), pin(PATCH)]
        destination = OUT/entry['category']/'unified/preparation/selection.json'
        destination.parent.mkdir(parents=True, exist_ok=False)
        destination.write_text(json.dumps(plan, indent=2)+'\n')
        plans.append({**entry, 'plan': pin(destination), 'physical_submitted': False,
                      'CPU_preflight': 'required_at_submission'})
    manifest = {**old, 'registered_plans': plans, 'source_snapshot': identity, 'producer': pin(Path(__file__)),
                'paired_baseline_reused': True, 'parent_manifest': pin(OLD/'manifest.json')}
    (OUT/'manifest.json').write_text(json.dumps(manifest, indent=2)+'\n')
    startups = [entry for entry in json.loads((OLD/'startup_manifest.json').read_text()) if entry['arm']=='locked']
    (OUT/'startup_manifest.json').write_text(json.dumps(startups, indent=2)+'\n')
    print(json.dumps({'plans': len(plans), 'new_source': identity['archive'],
                      'baseline_startups_reused': [entry['startup_job'] for entry in startups]}))


if __name__ == '__main__':
    main()
