"""Register measured-anchor trials against the captured original/layout physics."""
import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import pickle
import sys

ROOT = Path('/public/home/sunyihan/rpent_libero_eval')
BASE = ROOT/'results/bounded_skills/execution_repairs_20261022/option_ceiling_20261022'


def reference(path):
    return {'path':str(path), 'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x') as stream:
        json.dump(value, stream, indent=2)


def prepare_n2(source, out, common):
    """Extract the N2 baseline's complete captured physics, without its adapter."""
    sys.path.insert(0, str(source))
    os.environ.setdefault('MUJOCO_GL','egl')
    os.environ.setdefault('PYOPENGL_PLATFORM','egl')
    import robots.libero.env_server
    from robots.libero.bounded_hybrid_diagnostic import snapshot_digest

    parent = BASE/'N2/after_fulltask/preparation/panel.json'
    panel = json.loads(parent.read_bytes())
    cases, registration = [], []
    for index, old in enumerate(panel['jobs']):
        case = copy.deepcopy(old['case'])
        closed = BASE/f'N2/after_fulltask/formal/closed_{index:03d}.json'
        summary_path = Path(json.loads(closed.read_bytes())['summary'])
        summary = json.loads(summary_path.read_bytes())
        checkpoint = summary_path.parent/'episode/private_branchpoint.pkl'
        saved = pickle.loads(checkpoint.read_bytes())
        physics = saved['physics']
        assert {'integration','native_data','observation_state'} <= physics['actuator_state'].keys()
        digest = snapshot_digest(physics)
        assert all(t['initial_physics_sha256']==digest for t in summary['trials'])
        target = out/f'N2_complete_initials/{index:03d}.pkl'
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open('xb') as stream:
            pickle.dump(physics, stream, protocol=5)
        case['diagnostic']['original_subtask_start']['physics'] = reference(target)
        case['diagnostic']['vla_variants'].append({'name':'measured_anchor',
            'parameters':{'preparation':'measured_anchor'}})
        cases.append(case)
        registration.append({'case':case['name'],'parent_summary':reference(summary_path),
            'complete_initial_physics_sha256':digest,'new_physics':reference(target)})
        del saved,physics
    manifest = {**common,'cases':cases,'parent_panel':reference(parent)}
    write(out/'preparation/N2_manifest.json',manifest)
    new_panel = {**common,'sam_entry':panel['sam_entry'],
        'jobs':[{'kind':'original_fork','case':c,'manifest':reference(out/'preparation/N2_manifest.json')}
            for c in cases]}
    write(out/'preparation/N2.json',new_panel)
    write(out/'N2_registration.json',{'states':12,'trials':168,'rows':registration,
        'legacy_trials':132,'measured_anchor_trials':36,'training':False})
    print(json.dumps({'N2_states':12,'trials':168,'output':str(out)}))


def prepare_d2(source, out, common):
    """Register evaluation only; submission follows the original/layout checks."""
    parent=BASE/'oracle_retry_fb9b3865/preparation/D2_recovery1.json'
    panel=json.loads(parent.read_bytes())
    assert len(panel['jobs'])==40 and all(j['recovery_budget']==1 for j in panel['jobs'])
    common={**common,'libero_config':reference(ROOT/'runtime_config/config.yaml')}
    panel.update(common,parent_registration=reference(parent),evaluation_only=True,
        runtime_change='public measured-anchor preparation and transport added; other invocation budgets unchanged',
        source_archive=reference(ROOT/'rd_measured_vla_v7_r4_20261023.tar.gz'),
        submission_condition='original90/layout65 and N1/N2 physical evidence assessed first')
    panel['vla_variants']=[
        {'name':'in_place','parameters':{'preparation':'in_place'}},
        {'name':'initial_pose','parameters':{'preparation':'initial_pose'}},
        {'name':'full_task','parameters':{'mode':'task','preparation':'in_place','prompt_style':'full_task'}},
        {'name':'measured_anchor','parameters':{'preparation':'measured_anchor'}}]
    write(out/'preparation/D2_recovery1.json',panel)
    for shard in range(2):
        write(out/f'preparation/D2_recovery1_shard{shard}.json',dict(panel,jobs=panel['jobs'][shard::2]))
    write(out/'preparation/D2_vla_startup.json',dict(panel,jobs=panel['jobs'][:1]))
    print(json.dumps({'D2_states':40,'recovery_budget':1,'variants':4,'submitted':False,'output':str(out)}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--n2', action='store_true')
    parser.add_argument('--d2', action='store_true')
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
    if args.n2:
        return prepare_n2(source,out,common)
    if args.d2:
        return prepare_d2(source,out,common)
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
