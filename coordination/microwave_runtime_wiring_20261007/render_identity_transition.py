"""Render only explicitly indexed public RGB-D transition images for diagnosis."""

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw


def checked(record):
    path = Path(record['path'])
    if hashlib.sha256(path.read_bytes()).hexdigest() != record['sha256']:
        raise ValueError('public artifact changed')
    return path


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--summary', type=Path, required=True)
    parser.add_argument('--chunks', type=int, nargs='+', required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--camera', choices=('agentview', 'wrist'), default='agentview')
    args = parser.parse_args()
    summary = json.loads(args.summary.read_text())
    panels = []
    for chunks in args.chunks:
        sample = next(row for row in summary['samples'] if row['phase'] == 'probe' and row['chunks'] == chunks)
        image = Image.open(checked(sample['artifacts'][args.camera]['rgb'])).convert('RGB')
        moving = sample['views'][args.camera]['moving']
        if moving and moving.get('mask_artifact'):
            with np.load(checked(moving['mask_artifact']), allow_pickle=False) as saved:
                mask = saved[saved.files[0]].astype(bool)
            rgb = np.array(image)
            rgb[mask] = .7 * rgb[mask] + .3 * np.array([255, 0, 0])
            image = Image.fromarray(rgb)
        image = image.resize((512, 512))
        ImageDraw.Draw(image).text((12, 12), f'chunk {chunks}; current independent mask red' if moving
                                  else f'chunk {chunks}; current door unmeasured', fill='white', stroke_fill='black', stroke_width=1)
        panels.append(image)
    canvas = Image.new('RGB', (512 * len(panels), 512))
    for index, image in enumerate(panels):
        canvas.paste(image, (512 * index, 0))
    canvas.save(args.output)
    print(json.dumps({'path': str(args.output), 'sha256': hashlib.sha256(args.output.read_bytes()).hexdigest(),
                      'private_labels_used': False, 'controls': 0}))
