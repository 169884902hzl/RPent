"""Screen current noncontact approaches when the saved stove knob is unmeasured."""
import hashlib
import json
import os
import platform
import sys
import time
from pathlib import Path

os.environ.update(CUDA_VISIBLE_DEVICES='', OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='1')
ROOT = Path('/public/home/sunyihan/rpent_libero_eval')
SOURCE = ROOT / 'source_bounded_spawn_planning_20261019_7ffe2118'
sys.path.insert(0, str(SOURCE))

from robots.libero.bounded_offline_labels import load_annotation_state


def main():
    records = []
    for job in ('9248_65', '9248_98'):
        choices, = (ROOT / f'results/bounded_skills/feasibility_20261017/job{job}').glob('*oracle_k4/choices.jsonl')
        row = [json.loads(line) for line in choices.open()][-1]
        ref = row['private_prefix_annotation_state']
        state = load_annotation_state(ref['path'], ref['sha256'])
        adapter = state['adapter']
        entity, = (e for e in adapter.scene.entities.values() if e.name == 'stove')
        assert entity.id not in adapter.plans and entity.visible
        started = time.perf_counter()
        options = []
        for approach in ('above', 'front', 'left', 'right'):
            for path in ('direct', 'over', 'around'):
                option = adapter._candidate('move_to', {'anchor_id': entity.id,
                                            'approach': approach, 'path': path})
                options.append(option)
        feasible = [c for c in options if c is not None
                    and c['consequences']['collision'] is False
                    and c['consequences']['ik_reachable'] is True]
        record = {'job': job, 'context': ref, 'entity': next(a for a in row['request']['anchors'] if a['id'] == entity.id),
                  'choices_sha256': hashlib.sha256(choices.read_bytes()).hexdigest(),
                  'options': options, 'screen_diagnostics': adapter.candidate_diagnostics,
                  'feasible': [c['id'] for c in feasible], 'wall_s': time.perf_counter()-started}
        records.append(record)
        print(json.dumps({'job': job, 'feasible': len(feasible), 'wall_s': record['wall_s']}), flush=True)
    report = {'diagnostic_source': str(SOURCE), 'host': platform.node(), 'records': records,
              'scope': 'cross-source public noncontact route screen, not a physical recovery or task label',
              'physics_steps': 0, 'rpc_calls': 0, 'gpu_used': False, 'training': False,
              'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    out = ROOT / 'coordination/bounded_skills_20261016/reports/stove_observation_routes_CPU_20261019.json'
    with out.open('x') as stream:
        json.dump(report, stream, indent=2)
        stream.write('\n')


if __name__ == '__main__':
    main()
