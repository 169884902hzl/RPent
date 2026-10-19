"""Audit door identity losses against the exact recorded public RGB-D pixels."""
# ruff: noqa: E402 -- pinned helper and CPU-only diagnostics
import hashlib
import json
import os
import sys
from collections import Counter
from pathlib import Path

os.environ.update(CUDA_VISIBLE_DEVICES='', OPENBLAS_NUM_THREADS='1')
root = Path('/public/home/sunyihan/rpent_libero_eval')
base = root / 'coordination/bounded_skills_20261016'
prep_path = base / 'reports/chunk_v3_panel_joint_room_20261018_preparation.json'
prep = json.loads(prep_path.read_bytes())
sys.path.insert(0, prep['snapshot'])
import numpy as np
from PIL import Image, ImageDraw

from robots.libero.v5_microwave_capture import points_mask

directory, = (root / 'results/bounded_skills/feasibility_20261017/job9600_140').glob('*oracle_k4')
choices = directory / 'choices.jsonl'
rows = [json.loads(line) for line in choices.read_bytes().splitlines()]
reasons, records, inputs, outputs = Counter(), [], [choices, prep_path], []
for index, row in enumerate(rows):
    fixtures = {}
    for parent, fixture in row.get('fixture_measurement_evidence', {}).items():
        door = fixture.get('door_measurement')
        if door is None:
            continue
        fixtures[parent] = door
        for instance in door.get('instances', []):
            reason = instance.get('reason')
            tracking = instance.get('identity_tracking', {})
            if reason:
                reasons[reason] += 1
            if tracking.get('reason'):
                reasons['tracking:' + tracking['reason']] += 1
    request = row['request']
    candidates = {candidate['id']: candidate for candidate in request['candidates']}
    chosen = row.get('decision', {}).get('candidate_ids', [])
    records.append({'index': index, 'anchors': [a for a in request['anchors']
        if 'microwave' in a['label']], 'selected_skills': [candidates[key]['skill'] for key in chosen],
        'receipts': [{key: receipt.get(key) for key in ('skill', 'stop_reason')}
                     for receipt in row.get('receipts', [])], 'door_measurements': fixtures})

def load(path):
    with np.load(path, allow_pickle=False) as saved:
        assert len(saved.files) == 1
        return saved[saved.files[0]]

for index, parent in ((4, 'e54'), (10, 'e54'), (14, 'e98'), (26, 'e98'), (26, 'e54')):
    evidence = records[index]['door_measurements'].get(parent)
    if evidence is None:
        continue
    step = evidence['source_step']
    for camera in ('agentview', 'wrist'):
        image_path = directory / (camera + '_high.png') / f'{step:02d}.png'
        world_path = directory / (camera + '_world_high.npz') / f'{step:02d}.npz'
        image = Image.open(image_path).convert('RGB')
        world = load(world_path)
        draw = ImageDraw.Draw(image)
        components = []
        for instance in evidence.get('instances', []):
            cloud = instance.get('candidate_cloud')
            if instance.get('camera') != camera or cloud is None:
                continue
            path = Path(cloud['path'])
            assert hashlib.sha256(path.read_bytes()).hexdigest() == cloud['sha256']
            assert cloud['source_step'] == step
            mask = points_mask(world, load(path))
            color = 'orange' if instance.get('reason') else 'cyan'
            y, x = np.where(mask)
            for px, py in zip(x, y):
                draw.point((int(px), int(py)), fill=color)
            components.append({'reason': instance.get('reason'), 'points': cloud['points'],
                               'matched_pixels': int(mask.sum()), 'color': color})
            inputs.append(path)
        draw.rectangle((0, 0, image.width, 32), fill='black')
        draw.text((3, 2), f'row {index}, capture {step}, {parent}, {camera}', fill='white')
        draw.text((3, 17), 'cyan=accepted; orange=rejected; exact public depth pixels', fill='white')
        output = base / 'reports' / f'microwave9600_identity_r{index}_{parent}_{camera}_CPU_20261019.png'
        assert not output.exists()
        image.save(output)
        inputs.extend((image_path, world_path))
        outputs.append({'path': str(output), 'sha256': hashlib.sha256(output.read_bytes()).hexdigest(),
                        'row': index, 'parent': parent, 'camera': camera,
                        'source_step': step, 'clouds': components})

report = {'source': prep['source_commit'], 'records': records, 'instance_reasons': dict(reasons),
          'outputs': outputs, 'inputs': [{'path': str(path),
              'sha256': hashlib.sha256(path.read_bytes()).hexdigest()} for path in dict.fromkeys(inputs)],
          'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
          'scope': 'same-source public measurement audit; request and post-action evidence times remain distinct',
          'physics_steps': 0, 'rpc_calls': 0, 'gpu_used': False, 'private_labels_used': False,
          'training': False, 'confirmation': False}
output = base / 'reports/microwave9600_identity_audit_CPU_20261019.json'
with output.open('x') as stream:
    json.dump(report, stream, indent=2)
    stream.write('\n')
print(json.dumps({'output': str(output), 'instance_reasons': dict(reasons), 'images': len(outputs)}))
