"""Replay perception only on explicit saved camera frames, without simulation."""

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from types import SimpleNamespace

import numpy as np

from robots.libero.v5_runtime import MeasuredScene
from rpent.utils.rpc.http_rpc import HttpRpcClient


class SavedFrame:
    latest_step = 0

    def __init__(self, frame):
        self.frame = frame

    def load_bytes(self, name):
        assert name == 'agentview_high.png'
        return Path(self.frame['path']).read_bytes()

    def load(self, name):
        if name == 'agentview_metadata.json':
            return json.loads(Path(self.frame['metadata_path']).read_text())
        assert name == 'agentview_world_high.npz'
        with np.load(self.frame['world_path']) as data:
            return data['array']


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--endpoint', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    config = json.loads(args.manifest.read_text())
    args.output.mkdir(parents=True, exist_ok=False)
    client = HttpRpcClient(args.endpoint)
    records = []
    for index, frame in enumerate(config['frames']):
        queries = []

        def call(method, *, kwargs, timeout_s):
            response = client.call(method, kwargs=kwargs, timeout_s=timeout_s)
            queries.append({
                'text_prompt': kwargs['text_prompt'], 'min_score': kwargs['min_score'],
                'scores': [x['score'] for x in response['instances']],
            })
            return response

        scene = MeasuredScene(SimpleNamespace(_state=SavedFrame(frame)), SimpleNamespace(call=call), index)
        scene.refresh(config['public_scene_categories'])
        records.append({
            'frame': frame['key'], 'queries': queries,
            'visible_categories': dict(Counter(e.name for e in scene.entities.values() if e.visible)),
            'entities': [{'id': e.id, 'name': e.name, 'xyz': e.xyz, 'visible': e.visible,
                          'score': scene._scores[e.id]} for e in scene.entities.values()],
        })
        (args.output/'frames.json').write_text(json.dumps(records, indent=2)+'\n')
    report = {
        'purpose': 'Saved RGB-D perception cohort; no environment/VLA, labels, or episode replay',
        'manifest_sha256': hashlib.sha256(args.manifest.read_bytes()).hexdigest(),
        'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'frames': records,
    }
    (args.output/'report.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps({'output': str(args.output), 'visible_categories': [x['visible_categories'] for x in records]}))


if __name__ == '__main__':
    main()
