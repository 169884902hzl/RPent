"""Audit public joint-limit traces and current oracle recovery on saved states."""
import hashlib
import json
import os
import platform
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path

os.environ.update(CUDA_VISIBLE_DEVICES='', OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='1')
ROOT = Path('/public/home/sunyihan/rpent_libero_eval')
SOURCE = ROOT / 'source_bounded_spawn_planning_20261019_7ffe2118'
sys.path.insert(0, str(SOURCE))

from robots.libero.bounded_offline_labels import annotate_prefix, load_annotation_state


def main():
    base = ROOT / 'coordination/bounded_skills_20261016'
    cohort_path = base / 'reports/original20_support_interim_r18_20261019.json'
    cohort = json.loads(cohort_path.read_bytes())
    xml = ROOT / '.venv/lib/python3.10/site-packages/robosuite/models/assets/robots/panda/robot.xml'
    limits = {joint.attrib['name']: [float(s) for s in joint.attrib['range'].split()]
              for joint in ET.parse(xml).findall('.//joint') if 'range' in joint.attrib}
    rows = []
    for episode in cohort['cohort']['rows']:
        if episode['success'] or not episode['report_category'].startswith('stove_'):
            continue
        choices, = Path(episode['record']).parent.glob('*oracle_k4/choices.jsonl')
        requests = [json.loads(line) for line in choices.open()]
        rotations = []
        for row in requests:
            for receipt in row.get('receipts', []):
                if receipt['skill'] != 'rotate_wrist':
                    continue
                detail = next(d['execution'] for d in row['execution_details']
                              if d.get('candidate_id') == receipt['candidate_id'])
                trace = detail.get('trace', [])
                joint7 = [point['after']['joint_positions_rad'][6] for point in trace]
                rotations.append({
                    'row': row['index'], 'outcome': receipt['outcome'],
                    'stop_reason': receipt['stop_reason'], 'steps_used': receipt['steps_used'],
                    'endpoint_error_m': detail.get('endpoint_error_m'),
                    'angular_error_rad': detail.get('angular_endpoint_error_rad'),
                    'trace_samples': len(trace),
                    'joint7_final_rad': joint7[-1] if joint7 else None,
                    'joint7_min_upper_margin_rad': min(limits['joint7'][1]-q for q in joint7) if joint7 else None,
                    'joint7_samples_within_0p01rad_of_upper_limit': sum(abs(q-limits['joint7'][1]) <= .01 for q in joint7),
                    'screen_passed': detail.get('screen', {}).get('passed'),
                    'screen_reason': detail.get('screen', {}).get('reason'),
                })
        terminal = requests[-1]
        ref = terminal['private_prefix_annotation_state']
        state = load_annotation_state(ref['path'], ref['sha256'])
        started = time.perf_counter()
        label = annotate_prefix(state, terminal['request'], [], workers=4)
        elapsed = time.perf_counter()-started
        selected = next((c for c in terminal['request']['candidates'] if c['id'] == label['selected']), None)
        record = {
            'case': episode['case'], 'source_commit': cohort['source_commit'],
            'choices': str(choices), 'choices_sha256': hashlib.sha256(choices.read_bytes()).hexdigest(),
            'rotations': rotations, 'saved_terminal_context': ref,
            'current_source_cpu_diagnosis': {'label': label, 'selected_public_option': selected, 'wall_s': elapsed},
        }
        rows.append(record)
        print(json.dumps({'case': episode['case']['name'], 'rotations': rotations,
                          'selected': selected, 'wall_s': elapsed}), flush=True)
    report = {
        'scope': 'cross-source CPU diagnosis; no replacement physical results or relabeled training rows',
        'diagnostic_source': str(SOURCE), 'host': platform.node(),
        'cohort': {'path': str(cohort_path), 'sha256': hashlib.sha256(cohort_path.read_bytes()).hexdigest()},
        'robot_xml': {'path': str(xml), 'sha256': hashlib.sha256(xml.read_bytes()).hexdigest()},
        'static_joint_limits_rad': limits, 'records': rows,
        'physics_steps': 0, 'rpc_calls': 0, 'gpu_used': False, 'training': False,
        'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    }
    with (base / 'reports/stove_recovery_CPU_20261019.json').open('x') as stream:
        json.dump(report, stream, indent=2)
        stream.write('\n')


if __name__ == '__main__':
    main()
