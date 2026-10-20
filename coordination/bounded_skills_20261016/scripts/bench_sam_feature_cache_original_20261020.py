"""Compare cached/uncached image features on pinned original RGB frames."""

import argparse
import base64
import gc
import hashlib
import importlib.util
import json
import os
import sys
from pathlib import Path
from time import perf_counter


def reference(path):
    path = Path(path).resolve(strict=True)
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--prototype', type=Path, required=True)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--preflight', action='store_true')
    args = parser.parse_args()
    plan = json.loads(args.manifest.read_bytes())
    assert not plan['training'] and plan['domain'] == 'original_only'
    assert reference(args.prototype) == plan['prototype']
    requests = []
    for row in plan['requests']:
        assert reference(row['path'])['sha256'] == row['sha256']
        raw = Path(row['path']).read_bytes()
        requests.append((base64.b64encode(raw).decode(), row))
    assert len(requests) == 26
    if args.preflight:
        print(json.dumps({'preflight': 'passed', 'manifest': reference(args.manifest),
            'requests': len(requests), 'prototype': plan['prototype'], 'physics_steps': 0}))
        return 0
    assert os.environ['SLURM_JOB_ID'] == plan['owned_job_raw_id']
    assert os.environ['CUDA_VISIBLE_DEVICES'] == plan['cuda_visible_devices']
    sys.path.insert(0, str(args.source.resolve(strict=True)))
    spec = importlib.util.spec_from_file_location('feature_cache_prototype', args.prototype)
    prototype = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(prototype)
    import torch

    from coordination.bounded_skills_20261016.scripts.sam3_output_filter_startup_20261020 import EarlyOutputFilter
    from robots.libero.v5_sam3_server import V5Sam3Facade

    class BenchmarkFacade(prototype.ImageFeatureCache, EarlyOutputFilter, V5Sam3Facade):
        cache_enabled = False

        def _state_for_image(self, image_bytes):
            if self.cache_enabled:
                return super()._state_for_image(image_bytes)
            return V5Sam3Facade._state_for_image(self, image_bytes)

    torch.set_num_threads(1)
    facade = BenchmarkFacade(plan['checkpoint']['path'], image_cache_entries=16)
    encoded = facade._processor.set_image
    image_encodes = 0

    def set_image(*args, **kwargs):
        nonlocal image_encodes
        image_encodes += 1
        return encoded(*args, **kwargs)

    facade._processor.set_image = set_image

    def call(image, row):
        if 'point' in row:
            return facade.segment(image, point=row['point'])
        return facade.segment_all(image, row['text_prompt'])

    # Warm both text and point heads before measuring the registered sequence.
    for image, row in requests:
        call(image, row)
    modes = []
    for enabled in (False, True, False):
        facade.cache_enabled = enabled
        facade._image_digest = facade._image_state = None
        facade._image_templates.clear()
        facade._image_cache_hits = facade._image_cache_misses = image_encodes = 0
        gc.collect()
        torch.cuda.empty_cache()
        torch.cuda.reset_peak_memory_stats()
        rows = []
        for image, row in requests:
            torch.cuda.synchronize()
            started = perf_counter()
            result = call(image, row)
            torch.cuda.synchronize()
            raw = json.dumps(result, sort_keys=True, separators=(',', ':')).encode()
            rows.append({'wall_s': perf_counter()-started,
                'response_sha256': hashlib.sha256(raw).hexdigest(), 'response_bytes': len(raw)})
        modes.append({'cache': enabled, 'image_encodes': image_encodes,
            'cache_hits': facade._image_cache_hits, 'cache_misses': facade._image_cache_misses,
            'total_request_s': sum(row['wall_s'] for row in rows), 'requests': rows,
            'own_cuda_peak_allocated_bytes': torch.cuda.max_memory_allocated()})
    baseline = [r['response_sha256'] for r in modes[0]['requests']]
    report = {'manifest': reference(args.manifest), 'prototype': plan['prototype'],
        'source': str(args.source), 'script': reference(__file__), 'modes': modes,
        'all_response_bytes_equal': all([r['response_sha256'] for r in mode['requests']]
            == baseline for mode in modes), 'slurm_job_raw_id': os.environ['SLURM_JOB_ID'],
        'step_id': os.environ['SLURM_STEP_ID'], 'physics_steps': 0,
        'training': False, 'new_gpu_allocations': 0,
        'scope': 'temporary model in existing owned allocation; existing services unchanged; not episode throughput'}
    with args.output.open('x') as stream:
        json.dump(report, stream, indent=2)
        stream.write('\n')
    print(json.dumps({k: report[k] for k in ('all_response_bytes_equal', 'slurm_job_raw_id', 'step_id')}
        | {'request_s': [m['total_request_s'] for m in modes],
           'image_encodes': [m['image_encodes'] for m in modes]}), flush=True)


if __name__ == '__main__':
    main()
