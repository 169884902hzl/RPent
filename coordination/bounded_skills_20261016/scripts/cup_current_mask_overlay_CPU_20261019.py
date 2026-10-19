"""Inspect saved public mug masks without simulation or model requests."""
import hashlib
import json
from pathlib import Path

import numpy as np
from PIL import Image

root = Path('/public/home/sunyihan/rpent_libero_eval')
base = root / 'coordination/bounded_skills_20261016'
records = []
for job in ('9248_14', '9544_124'):
    choices = next((root / f'results/bounded_skills/feasibility_20261017/job{job}').glob(
        '*oracle_k4/choices.jsonl'))
    rows = [json.loads(line) for line in choices.read_text().splitlines()]
    row = rows[-2]
    anchor, = (a for a in row['request']['anchors'] if a['label'] == 'white yellow mug')
    ref = row['perception_evidence'][anchor['id']]['sam_mask_files']['agentview']
    mask_path = Path(ref['path'])
    assert hashlib.sha256(mask_path.read_bytes()).hexdigest() == ref['sha256']
    with np.load(mask_path, allow_pickle=False) as saved:
        mask = saved[saved.files[0]].astype(bool)
    image_path = choices.parent / 'agentview_high.png' / f"{ref['source_step']:02d}.png"
    rgb = np.asarray(Image.open(image_path).convert('RGB')).copy()
    assert mask.shape == rgb.shape[:2]
    overlay = rgb.copy()
    overlay[mask] = (.5 * overlay[mask] + .5 * np.array([0, 255, 255])).astype(np.uint8)
    pair = Image.new('RGB', (rgb.shape[1] * 2, rgb.shape[0]))
    pair.paste(Image.fromarray(rgb), (0, 0))
    pair.paste(Image.fromarray(overlay), (rgb.shape[1], 0))
    output = base / 'reports' / f'cup{job}_current_mask_CPU_20261019.png'
    pair.save(output)
    records.append({'job': job, 'row': len(rows) - 2, 'anchor': anchor,
        'mask': ref, 'source_cameras': row['perception_evidence'][anchor['id']]['source_cameras'],
        'choices': str(choices), 'choices_sha256': hashlib.sha256(choices.read_bytes()).hexdigest(),
        'image': str(image_path), 'image_sha256': hashlib.sha256(image_path.read_bytes()).hexdigest(),
        'overlay': str(output), 'overlay_sha256': hashlib.sha256(output.read_bytes()).hexdigest()})
output = base / 'reports/cup_current_mask_CPU_20261019.json'
output.write_text(json.dumps({'records': records, 'physics_steps': 0, 'rpc_calls': 0,
    'training': False, 'confirmation': False,
    'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}, indent=2) + '\n')
print(json.dumps({'output': str(output), 'overlays': [r['overlay'] for r in records]}))
