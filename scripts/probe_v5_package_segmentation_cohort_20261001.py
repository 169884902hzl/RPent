"""Compare package text queries on an explicit cohort of saved RGB frames."""

import argparse
import base64
import hashlib
import json
import time
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

from rpent.robots.components.sam3_client import Sam3Client
from rpent.utils.rpc.http_rpc import HttpRpcClient


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--endpoint', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    config = json.loads(args.manifest.read_text())
    args.output.mkdir(parents=True, exist_ok=False)
    client = HttpRpcClient(args.endpoint)
    results = []
    for frame in config['frames']:
        image_path = Path(frame['path'])
        encoded = base64.b64encode(image_path.read_bytes()).decode('ascii')
        original = Image.open(image_path).convert('RGB')
        queried = []
        for index, query in enumerate(config['queries']):
            started = time.perf_counter()
            response = client.call('sam3.segment_all', kwargs={
                'image_base64': encoded, 'text_prompt': query,
                'min_score': config['min_score'],
            }, timeout_s=120)
            elapsed = time.perf_counter() - started
            instances, masks = [], []
            panel = original.copy()
            draw = ImageDraw.Draw(panel)
            for instance in response['instances']:
                mask = Sam3Client._decode_result(instance).mask
                ys, xs = np.nonzero(mask)
                if not len(xs):
                    continue
                box = [int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())]
                score = float(instance['score'])
                instances.append({'score': score, 'pixels': int(mask.sum()), 'bbox_xyxy': box})
                masks.append(mask)
                draw.rectangle(box, outline='lime', width=3)
                draw.text((box[0], max(0, box[1]-12)), f'{score:.3f}', fill='lime')
            panel.thumbnail((384, 384))
            panel_name = frame['key'] + '_q' + str(index) + '.png'
            panel.save(args.output/panel_name)
            queried.append({'query': query, 'elapsed_s': elapsed, 'instances': instances, 'panel': panel_name})
            results.append({'frame': frame['key'], 'query': query, 'instances': instances, 'elapsed_s': elapsed})
        grid = Image.new('RGB', (384*len(queried), 414), 'white')
        draw = ImageDraw.Draw(grid)
        for index, result in enumerate(queried):
            grid.paste(Image.open(args.output/result['panel']), (384*index, 30))
            draw.text((384*index+4, 4), result['query'], fill='black')
        grid.save(args.output/(frame['key']+'_queries.png'))
    report = {
        'purpose': 'Read-only saved-frame segmentation cohort; no physical episode replay, no training labels',
        'manifest_sha256': hashlib.sha256(args.manifest.read_bytes()).hexdigest(),
        'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'frame_count': len(config['frames']), 'queries_per_frame': len(config['queries']),
        'rows': results,
    }
    (args.output/'report.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps({'frames': report['frame_count'], 'queries': len(results), 'output': str(args.output)}))


if __name__ == '__main__':
    main()
