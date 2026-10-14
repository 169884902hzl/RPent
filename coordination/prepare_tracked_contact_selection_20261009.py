"""Compare identity-preserving analytic contact on the registered selection pool."""

import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess

ROOT = Path('/public/home/sunyihan/rpent_libero_eval')
SOURCE = ROOT / 'source_v5_grasp_public_tracking_20261009_r3'
ADAPTER = ROOT / 'coordination/perturb_contact_methods_adapter_20261009_r5'
OUTPUT = ROOT / 'results/harness_v5/perturb_contact_identity_selection_20261009_r1'


def ref(path):
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--category', choices=('bottle', 'bowl', 'box', 'cup', 'frypan'),
                        action='append', required=True)
    parser.add_argument('--source', type=Path, default=SOURCE)
    parser.add_argument('--output-root', type=Path, default=OUTPUT)
    parser.add_argument('--method', default='analytic_identity_active100')
    parser.add_argument('--side-route', action='store_true')
    args = parser.parse_args()
    source = args.source.resolve(strict=True)
    snapshot = json.loads((source / 'source_snapshot.json').read_text())
    if ref(Path(snapshot['archive']['path'])) != snapshot['archive']:
        raise ValueError('registered tracking source changed')
    for category in args.category:
        cell = f'grasp_{category}_{args.method}'
        prep = args.output_root / cell / 'preparation'
        if (prep / 'startup_submission.json').exists():
            print(json.dumps({'cell': cell, 'status': 'startup_already_registered'}), flush=True)
            continue
        prior_root = 'perturb_contact_methods_selection_20261009_r5' if category in ('cup', 'frypan') else 'perturb_contact_methods_selection_20261009_r2'
        suffix = 'analytic_v2' if category in ('cup', 'frypan') else 'analytic'
        previous = ROOT / f'results/harness_v5/{prior_root}/grasp_{category}_{suffix}/preparation/selection.json'
        plan = json.loads(previous.read_text())
        if (plan['confirmation'] or plan['training_allowed'] or plan['PRO_files_read']
                or len(plan['cases']) != 100
                or len({c['state_sha256'] for c in plan['cases']}) != 100):
            raise ValueError('exactly 100 unique original-layout selection states required')
        for case in plan['cases']:
            state = Path(case['registered_layout_state']['path'])
            if ref(state) != case['registered_layout_state']:
                raise ValueError('registered layout changed')
        condition = copy.deepcopy(next(iter(plan['conditions'].values())))
        condition['overrides']['grasp_public_tracking_v1'] = True
        if args.side_route:
            condition['overrides']['analytic_side_route_v1'] = True
        method = args.method
        cases = [{**c, 'name': c['name'] + '_identity100', 'condition': method}
                 for c in plan['cases']]
        prep.mkdir(parents=True, exist_ok=False)
        producer = prep / 'producer.py'
        producer.write_bytes(Path(__file__).read_bytes())
        dependencies = [ref(ADAPTER / 'scripts' / name) for name in (
            'probe_v5_skill501_original.py', 'probe_v5_perturb_skill_20261009.py',
            'v5_perturb_goal_diagnostic.py', 'v5_perturb_public_reference.py')]
        plan.update(source_path=str(source), source_snapshot=snapshot,
            source_commit=snapshot['commit'], adapter_path=str(ADAPTER), cases=cases,
            conditions={method: condition}, method=method, producer=ref(producer),
            producer_dependencies=[ref(producer), *dependencies],
            references=[*plan['references'], ref(previous)],
            purpose='same100 selection layouts; public precontact identity plus active RGB-D verification; no Pi0.5 parameter tuning',
            layout_states=100, diagnostic_contact_trajectory=True,
            private_labels_used_for_control=False, truth_may_override_runtime=False,
            active_verification_translation_m=.04, confirmation=False, training_allowed=False)
        manifest = prep / 'selection.json'
        manifest.write_text(json.dumps(plan, indent=2) + '\n')
        env = {'PERTURB_SKILL_PLAN': str(manifest), 'PERTURB_SKILL_PLAN_SHA': ref(manifest)['sha256'],
            'PERTURB_SKILL_SOURCE': str(source), 'PERTURB_SKILL_ADAPTER': str(ADAPTER),
            'PERTURB_SKILL_OUTPUT': str(args.output_root / cell), 'PERTURB_SKILL_STARTUP': '1'}
        launcher = ADAPTER / 'scripts/run_v5_perturb_skill_selection_20261009.sbatch'
        cpu = subprocess.run(['bash', str(launcher)], cwd='/tmp', env={**os.environ, **env,
            'PERTURB_SKILL_CPU_ONLY': '1'}, capture_output=True, text=True)
        (prep / 'CPU_preflight.log').write_text(cpu.stdout + cpu.stderr)
        cpu.check_returncode()
        command = ['sbatch', '--parsable', '--array=0', '--nice=0',
            '--export=ALL,' + ','.join(k + '=' + v for k, v in env.items()), str(launcher)]
        job = subprocess.check_output(command, cwd='/tmp', text=True).strip()
        record = {'job': job, 'command': command, 'environment': env,
            'manifest': ref(manifest), 'launcher': ref(launcher), 'physical_startup': 'pending',
            'confirmation': False, 'training_allowed': False}
        (prep / 'startup_submission.json').write_text(json.dumps(record, indent=2) + '\n')
        print(json.dumps({'cell': cell, 'job': job, 'registered': 100,
                         'manifest': ref(manifest)}), flush=True)


if __name__ == '__main__':
    main()
