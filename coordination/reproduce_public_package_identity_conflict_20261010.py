"""Reproduce cross-category reassociation using public image/depth inputs only."""
import argparse
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np

from robots.libero.v5_runtime import MeasuredScene
from rpent.robots.components.sam3_client import Sam3Client


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    yy, xx = np.mgrid[:10, :20]
    world = np.stack((np.where(xx < 10, xx * .002, .2 + xx * .002),
                      yy * .002, .92 + yy * .0002), axis=-1)
    left = xx < 10
    state = SimpleNamespace(latest_step=0, load_bytes=lambda _: b'public-test-RGB',
        load=lambda name: {'extrinsic_cam2world': np.eye(4)} if name.endswith('.json') else world)

    def segment(_, kwargs, **unused):
        butter = kwargs['text_prompt'] == 'small red box'
        mask = left if butter or state.latest_step == 1 else ~left
        return {'instances': [{'score': .64 if butter else .68, 'mask': mask}]}

    original_decode = Sam3Client._decode_result
    Sam3Client._decode_result = staticmethod(lambda item: SimpleNamespace(mask=item['mask']))
    try:
        scene = MeasuredScene(SimpleNamespace(_state=state), SimpleNamespace(call=segment), 1,
                              dual_view_fusion_v1=False)
        scene.instance_limits = {'butter': 1, 'chocolate pudding': 1}
        scene.refresh(['butter', 'chocolate pudding'])
        before = [{'id': e.id, 'name': e.name, 'xyz': e.xyz} for e in scene.entities.values()]
        state.latest_step = 1
        scene.refresh(['butter', 'chocolate pudding'])
        after = [{'id': e.id, 'name': e.name, 'xyz': e.xyz, 'visible': e.visible}
                 for e in scene.entities.values()]
    finally:
        Sam3Client._decode_result = original_decode
    visible = [e for e in after if e['visible']]
    duplicated = len(visible) == 2 and visible[0]['xyz'] == visible[1]['xyz']
    if not duplicated:
        raise AssertionError('expected registered cross-category duplicate to reproduce')
    args.output.mkdir(parents=True, exist_ok=False)
    report = {'before': before, 'after': after, 'regression_reproduced': duplicated,
              'reproduction': 'two existing IDs reassigned to the same public mask in the next frame',
              'inputs': 'synthetic RGB-D and segmentation replies; no simulator or private fields',
              'physical_validation': False, 'runtime_fix_verified': False,
              'runtime_sha256': hashlib.sha256(Path(__import__(MeasuredScene.__module__,
                  fromlist=['__file__']).__file__).read_bytes()).hexdigest(),
              'producer_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    (args.output / 'manifest.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report))


if __name__ == '__main__':
    main()
