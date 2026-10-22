"""Register the unchanged forty D2 cases with the N1-qualified execution tree."""
import argparse
import copy
import hashlib
import json
from pathlib import Path


def ref(path):
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    root = args.root.resolve(strict=True)
    source = args.source.resolve(strict=True)
    revision = json.loads((source/'SOURCE_REVISION.json').read_bytes())['commit']
    evidence = root/'results/bounded_skills/execution_repairs_20261022/refresh_ablation/N1_30/partial29_verified/summary.json'
    qualification = json.loads(evidence.read_bytes())
    assert qualification['closed'] == 30 and qualification['after']['success'] >= 24
    assert qualification['all_complete_initial_hashes_match']
    previous = root/'results/bounded_skills/schema6_20261020/preparation_B2_variants_439ffcde'
    args.output.mkdir(parents=True, exist_ok=False)
    manifests = []
    for budget in (0, 1, 2):
        parent = previous/f'D2_recovery{budget}.json'
        plan = copy.deepcopy(json.loads(parent.read_bytes()))
        assert len(plan['jobs']) == 40 and plan['vla_options_v2']
        assert not plan['training'] and not plan['confirmation']
        assert len(plan['vla_variants']) == 3
        assert all(job['kind'] == 'd2' and job['recovery_budget'] == budget
                   for job in plan['jobs'])
        plan.update(source=str(source), source_commit=revision,
            parent_registration=ref(parent), qualified_N1=ref(evidence),
            development_repair='N1-qualified execution, native endpoint transport and unbound VLA fallback; canonical hash only acceleration',
            physical_denominator='new source; old results retained separately')
        path = args.output/f'D2_recovery{budget}.json'
        path.write_text(json.dumps(plan, indent=2)+'\n')
        manifests.append(ref(path))
        if budget == 2:
            for part, indices in [('a', range(20)), ('b', range(20, 40))]:
                shard = copy.deepcopy(plan)
                shard.update(parent_full_manifest=ref(path),
                    parent_case_indices=list(indices),
                    resume_unit='completed registered case; interrupted attempts retained')
                shard['jobs'] = [plan['jobs'][i] for i in indices]
                (args.output/f'D2_recovery2_{part}.json').write_text(json.dumps(shard, indent=2)+'\n')
    smoke = json.loads((root/'results/bounded_skills/execution_repairs_20261022/qualified90_9716b68c/preparation/smoke10.json').read_bytes())
    assert len(smoke['jobs']) == 10 and all(job['kind'] == 'smoke' for job in smoke['jobs'])
    smoke.update(source=str(source), source_commit=revision, qualified_N1=ref(evidence))
    (args.output/'smoke10.json').write_text(json.dumps(smoke, indent=2)+'\n')
    report = {'source': str(source), 'source_commit': revision,
        'qualified_N1': ref(evidence), 'manifests': manifests,
        'cases_per_recovery': 40, 'training': False, 'confirmation': False,
        'same_cases_and_sampling_variants': True,
        'smoke': ref(args.output/'smoke10.json'), 'registration_script': ref(Path(__file__))}
    (args.output/'registration.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(report), flush=True)


if __name__ == '__main__':
    main()
