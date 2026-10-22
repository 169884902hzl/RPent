"""Register measured-anchor trials against the captured original/layout physics."""
import argparse
import copy
import hashlib
import json
from pathlib import Path

ROOT = Path('/public/home/sunyihan/rpent_libero_eval')
BASE = ROOT/'results/bounded_skills/execution_repairs_20261022/option_ceiling_20261022'


def reference(path):
    return {'path':str(path), 'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x') as stream:
        json.dump(value, stream, indent=2)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    args = parser.parse_args()
    source = args.source.resolve(strict=True)
    revision = json.loads((source/'SOURCE_REVISION.json').read_bytes())
    assert 'measured_anchor' in (source/'rpent/skill_package/schema.json').read_text()
    assert 'bounded-skills/7' in (source/'rpent/skill_package/__init__.py').read_text()
    version = 'bounded-skills/7'
    out = BASE/('measured_anchor_'+revision['commit'][:8])
    config = reference(ROOT/'runtime_config_original_20261023/config.yaml')
    common = {'schema_version':version, 'source':str(source),
        'source_commit':revision['commit'], 'source_revision':reference(source/'SOURCE_REVISION.json'),
        'schema':reference(source/'rpent/skill_package/schema.json'),
        'libero_config':config, 'training':False, 'confirmation':False, 'vla_options_v2':True}
    parents = BASE/'regression155_f6987f0d/preparation'
    sam = json.loads((parents/'all155.json').read_bytes())['sam_entry']
    jobs = []
    for domain in ('original90','measured_packet1','measured_packet2'):
        parent = parents/(domain+'_manifest.json')
        manifest = json.loads(parent.read_bytes())
        manifest.update(common, parent_manifest=reference(parent), sam_entry=sam,
            comparison_scope='legacy methods repeated and measured_anchor added; no historical label migration')
        for case in manifest['cases']:
            diagnostic = case['diagnostic']
            old = copy.deepcopy(diagnostic['vla_variants'])
            diagnostic['vla_variants'] = old + [{'name':'measured_anchor',
                'parameters':{'preparation':'measured_anchor'}}]
            diagnostic.update(vla_repeats=3, self_repeats=2, include_self=True)
            case['comparison_domain'] = domain
        target = out/'preparation'/(domain+'_manifest.json')
        write(target, manifest)
        jobs.extend({'kind':'original_fork','case':c,'manifest':reference(target)} for c in manifest['cases'])
    assert len(jobs) == 155
    panel = {**common, 'sam_entry':sam, 'jobs':jobs}
    write(out/'preparation/all155.json', panel)
    for shard in range(2):
        write(out/f'preparation/shard{shard}.json', {**panel,'jobs':jobs[shard::2]})
    # Existing held, empty-hand, and articulation states exercise the new
    # finite option. These are development probes, outside the formal counts.
    selected = [jobs[0], next(j for j in jobs if j['case']['comparison_domain']=='measured_packet1'),
        next(j for j in jobs if j['case']['category']=='drawer_open')]
    pilot = copy.deepcopy(panel)
    pilot['jobs'] = copy.deepcopy(selected)
    for job in pilot['jobs']:
        job['case']['diagnostic'].update(include_self=False,
            vla_variants=[{'name':'measured_anchor','parameters':{'preparation':'measured_anchor'}}])
    write(out/'preparation/pilot3.json', pilot)
    smoke_parent = BASE/'native_model_7f87b8ef/preparation/smoke10.json'
    old_smoke = json.loads(smoke_parent.read_bytes())
    smoke = {**common, 'sam_entry':sam, 'jobs':old_smoke['jobs'],
        'evaluation':'fixed10_startup_skill_chunks_only', 'parent_manifest':reference(smoke_parent),
        'allow_vla':False, 'task_success_evaluation':False}
    write(out/'preparation/smoke10.json', smoke)
    # Keep only the runner's current inputs; historical source descriptors
    # remain accessible through parent_manifest, never attached to the new source.
    n1_parent = BASE/'N1_native_complete_baseline_c752/preparation/manifest.json'
    old_n1 = json.loads(n1_parent.read_bytes())
    keys = ('version','parents','cases','paired_protocol','runtime_options','scene_options',
        'baseline_runtime_calibration','schema6_source','D2_evaluation_only')
    n1 = {k:copy.deepcopy(old_n1[k]) for k in keys if k in old_n1}
    n1.update(common, baseline_source=str(source), baseline_commit=revision['commit'],
        baseline_schema=version, parent_manifest=reference(n1_parent),
        initial_protocol='same canonical complete integration/native buffers/controller/RNG; own public reconstruction')
    write(out/'preparation/N1.json', n1)
    registration = {**common,'states':155,'legacy_trials':1165,'measured_anchor_trials':465,
        'formal_trials':1630,'pilot_states':3,'pilot_trials':9,'N1_physical_cases':30,
        'N1_indices':list(range(24))+list(range(26,32)),
        'N1_common_starts':str(BASE/'fulltask124c5654/native_complete_common_starts'),
        'legacy_seed_budget_repeats_unchanged':True,'new_v7_public_requests_rebuilt':True,
        'no_D2_PRO_confirmation_in_155':True,'source_archive_sha256':revision['archive_sha256']}
    write(out/'registration.json',registration)
    print(json.dumps({'output':str(out),'source':revision['commit'],'formal_trials':1630}))


if __name__ == '__main__':
    main()
