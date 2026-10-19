"""Separate recorded terminal buckets from observed contact/identity evidence."""
import hashlib
import json
from collections import Counter
from pathlib import Path

root = Path('/public/home/sunyihan/rpent_libero_eval')
base = root / 'coordination/bounded_skills_20261016'
records = []
for job in ('9611_120', '9611_140'):
    choices = next((root / f'results/bounded_skills/feasibility_20261017/job{job}').glob(
        '*oracle_k4/choices.jsonl'))
    rows = [json.loads(line) for line in choices.read_text().splitlines()]
    samples = []
    for index, row in enumerate(rows):
        surfaces, handles, associations = [], [], []
        for d in row.get('candidate_screen_diagnostics', []):
            if d.get('anchor_id') != 'e114':
                continue
            if d.get('stage') == 'fixture_contact_measurement':
                m = d['measurement']
                handles.append({'pose': m.get('pose'), 'reason': m.get('reason')})
            if d.get('stage') == 'measured_surface_contact':
                candidates = d['candidates']
                surfaces.append({'anchor_id': d['anchor_id'], 'contact_xyz_m': d['contact_xyz_m'],
                    'candidate_n': len(candidates),
                    'screen_reasons': dict(Counter((c.get('screen') or {}).get('reason',
                        'closure' if c.get('closure') else 'unscreened') for c in candidates))})
        for parent, fixture in row.get('fixture_measurement_evidence', {}).items():
            door = fixture.get('door_measurement', {})
            a = door.get('current_handle_association')
            if a is not None:
                associations.append({'parent': parent, 'source_step': door.get('source_step'),
                    'reason': a['reason'], 'selected_camera': a.get('selected_camera')})
        samples.append({'index': index, 'sim_steps_before': row.get('sim_steps_before'),
            'anchors': [{k: a[k] for k in ('id', 'label', 'cached')} for a in row['request']['anchors']
                if 'microwave' in a['label']], 'surfaces': surfaces, 'handles': handles,
            'handle_associations_in_accumulated_evidence': associations,
            'receipts': [{k: r.get(k) for k in ('skill', 'outcome', 'phase', 'stop_reason', 'steps_used')}
                for r in row.get('receipts', [])]})
    records.append({'job': job, 'choices': str(choices),
        'choices_sha256': hashlib.sha256(choices.read_bytes()).hexdigest(), 'samples': samples})
output = base / 'reports/microwave9611_stage_audit_CPU_20261019.json'
with output.open('x') as stream:
    json.dump({'scope': 'saved log inspection only; accumulated alias diagnostics are not public anchor changes',
        'source_commit': 'ede83b18', 'physics_steps': 0, 'rpc_calls': 0, 'gpu_used': False,
        'training': False, 'confirmation': False,
        'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), 'records': records}, stream, indent=2)
    stream.write('\n')
print(json.dumps({'output': str(output), 'last_nonterminal': [r['samples'][-2] for r in records]}))
