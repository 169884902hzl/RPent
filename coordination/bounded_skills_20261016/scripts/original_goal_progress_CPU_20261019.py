"""Inspect saved private goal progress without executing or relabeling trials."""
import hashlib
import json
import os
import platform
import sys
from collections import Counter
from pathlib import Path

os.environ.update(CUDA_VISIBLE_DEVICES='', OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='1')
ROOT = Path('/public/home/sunyihan/rpent_libero_eval')
SOURCE = ROOT / 'source_bounded_spawn_planning_20261019_7ffe2118'
sys.path.insert(0, str(SOURCE))

from robots.libero.bounded_offline_labels import load_annotation_state


def entity_record(entity):
    if entity is None:
        return None
    return {key: getattr(entity, key, None) for key in
            ('id', 'name', 'visible', 'xyz', 'lower', 'upper', 'part_of')}


def main():
    base = ROOT / 'coordination/bounded_skills_20261016'
    source = base / 'reports/original20_support_interim_r18_20261019.json'
    cohort = json.loads(source.read_bytes())
    records = []
    for episode in cohort['cohort']['rows']:
        if episode['success']:
            continue
        choices, = Path(episode['record']).parent.glob('*oracle_k4/choices.jsonl')
        rows = [json.loads(line) for line in choices.open()]
        samples = []
        for row in rows if episode['report_category'] == 'cup_transfer' else rows[-1:]:
            ref = row.get('private_prefix_annotation_state')
            if ref is None:
                samples.append({'index': row['index'], 'missing_saved_state': True})
                continue
            state = load_annotation_state(ref['path'], ref['sha256'])
            adapter = state['adapter']
            status = state['private_status']
            bindings = state['binding'].get('_bindings', {})
            current = {anchor['id'] for anchor in row['request']['anchors']}
            samples.append({
                'index': row['index'], 'event': row.get('event'),
                'snapshot': ref, 'private_status': status, 'bindings': bindings,
                'bound_public_entities': {symbol: {
                    'in_request': ident in current,
                    'measured_entity': entity_record(adapter.scene.entities.get(ident)),
                    'cached_target': entity_record(adapter.target_cache.get(ident)),
                    'has_contact_plan': ident in adapter.plans,
                } for symbol, ident in bindings.items()},
                'held': adapter.held, 'active': adapter.active,
                'candidate_skill_counts': dict(Counter(c['skill'] for c in row['request']['candidates'])),
                'selected': row.get('decision'), 'receipts': row.get('receipts', []),
            })
        terminal = samples[-1]
        record = {'case': episode['case'], 'category': episode['report_category'],
                  'source_commit': cohort['source_commit'],
                  'choices': str(choices), 'choices_sha256': hashlib.sha256(choices.read_bytes()).hexdigest(),
                  'terminal_event': rows[-1].get('event'),
                  'private_status_scope': 'before recorded decision; not a new endpoint measurement',
                  'sim_steps': episode['sim_steps'], 'samples': samples}
        records.append(record)
        print(json.dumps({'case': episode['case']['name'], 'status': terminal.get('private_status'),
                          'held': terminal.get('held'), 'active': terminal.get('active')}, default=list), flush=True)
    report = {'scope': 'saved private diagnosis only; no physical rerun, no reclassification or training',
              'cohort': {'path': str(source), 'sha256': hashlib.sha256(source.read_bytes()).hexdigest()},
              'diagnostic_source': str(SOURCE), 'host': platform.node(), 'interpreter': sys.executable,
              'records': records, 'physics_steps': 0, 'rpc_calls': 0, 'gpu_used': False,
              'training': False, 'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    output = base / 'reports/original_goal_progress_CPU_20261019.json'
    with output.open('x') as stream:
        json.dump(report, stream, indent=2, default=list)
        stream.write('\n')


if __name__ == '__main__':
    main()
