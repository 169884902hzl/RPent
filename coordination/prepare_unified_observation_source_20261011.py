"""Pin generic public observation recovery without increasing control budgets."""
import hashlib
import json
from pathlib import Path
import shutil
import tarfile


ROOT = Path('/public/home/sunyihan/rpent_libero_eval')
OLD = ROOT/'results/harness_v5/unified_route_paired_selection_20261011_r8'
OUT = ROOT/'results/harness_v5/unified_route_paired_selection_20261011_r9'
PATCH = ROOT/'coordination/unified_observation_patch_20261011'


def pin(path):
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    previous = json.loads((OLD/'manifest.json').read_text())
    parent = Path(previous['source_snapshot']['path'])
    source = ROOT/'source_v5_unified_route_selection_20261011_r9'
    shutil.copytree(parent, source, symlinks=True, ignore=shutil.ignore_patterns('__pycache__'))
    changed = []
    for relative in ('robots/libero/v5_grasp_observation.py', 'robots/libero/v5_analytic_grasp.py',
                     'robots/libero/v5_grasp_geometry.py',
                     'tests/unit_tests/robots/libero/test_v5_grasp_observation.py'):
        destination = source/relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(PATCH/relative, destination)
        changed.append({**pin(destination), 'relative_path': relative})
    identity = {**previous['source_snapshot'], 'path': str(source), 'snapshot_id': source.name,
        'parent_source_path': str(parent),
        'purpose': 'generic PCA flank RGB-D recovery; whole-route mesh/IK screening; existing 160-step viewpoint budget',
        'changed_modules': changed,
        'CPU_validation': {'result': '60 passed; existing pytest timeout configuration warning',
            'tests': 'observation, analytic grasp, route, geometry, public tracking, opposed-pad window'},
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
    entries = []
    exemplar = next(entry for entry in previous['registered_plans'] if entry['arm'] == 'unified')
    old_plan = json.loads(Path(exemplar['plan']['path']).read_text())
    parent_config = Path(old_plan['base_config']['path'])
    if pin(parent_config) != old_plan['base_config']:
        raise ValueError('parent config changed')
    config = json.loads(parent_config.read_text())
    config['geometric_grasp_active_views_v1'] = True
    base = OUT/'common_base_config.json'
    base.write_text(json.dumps(config, indent=2)+'\n')
    for entry in previous['registered_plans']:
        if entry['arm'] == 'locked':
            entries.append(entry)
            continue
        original = Path(entry['plan']['path'])
        if pin(original) != entry['plan']:
            raise ValueError('parent plan changed')
        plan = json.loads(original.read_text())
        plan.update(source_path=str(source), source_snapshot=identity, base_config=pin(base),
            corrected_parent_plan=pin(original), planner_correction='generic_budgeted_observation_views',
            producer=pin(Path(__file__)))
        plan['producer_dependencies'] += [pin(Path(__file__)), *changed]
        destination = OUT/entry['category']/'unified/preparation/selection.json'
        destination.parent.mkdir(parents=True, exist_ok=False)
        destination.write_text(json.dumps(plan, indent=2)+'\n')
        entries.append({**entry, 'plan': pin(destination), 'physical_submitted': False,
                        'CPU_preflight': 'required_at_submission'})
    (OUT/'manifest.json').write_text(json.dumps({**previous, 'registered_plans': entries,
        'source_snapshot': identity, 'producer': pin(Path(__file__)), 'base_config': pin(base),
        'paired_baseline_reused': True, 'parent_manifest': pin(OLD/'manifest.json'),
        'opening_force_and_simulation_budget_changed': False,
        'prior_development_failures_preserved': True, 'confirmation': False}, indent=2)+'\n')
    locked = [entry for entry in json.loads((OLD/'startup_manifest.json').read_text())
              if entry['arm'] == 'locked']
    (OUT/'startup_manifest.json').write_text(json.dumps(locked, indent=2)+'\n')
    print(json.dumps({'archive': identity['archive'], 'config': pin(base),
                      'paired_states_changed': False}))


if __name__ == '__main__':
    main()
