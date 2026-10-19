# Copyright 2026 Zhilun Hu.
# SPDX-License-Identifier: Apache-2.0
"""Profile unchanged SAM requests with CPU thread counts in an owned allocation."""

import argparse
import base64
import cProfile
import hashlib
import json
import os
import pstats
import sys
from pathlib import Path
from time import perf_counter


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--checkpoint', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--prefilter-benchmark', action='store_true',
        help='Compare the existing output cutoff applied before mask upsampling, in this process only')
    args = parser.parse_args()
    plan = json.loads(args.manifest.resolve(strict=True).read_bytes())
    if os.environ['SLURM_JOB_ID'] != plan['owned_job_raw_id']:
        raise ValueError('benchmark must reuse the registered owned allocation')
    if os.environ['CUDA_VISIBLE_DEVICES'] != plan['cuda_visible_devices']:
        raise ValueError('GPU differs from the registered owned allocation')
    requests = []
    for row in plan['requests']:
        raw = Path(row['path']).resolve(strict=True).read_bytes()
        if hashlib.sha256(raw).hexdigest() != row['sha256']:
            raise ValueError('registered original image changed')
        requests.append((base64.b64encode(raw).decode(), row['text_prompt']))
    sys.path.insert(0, str(args.source.resolve(strict=True)))
    import torch

    from robots.libero.v5_sam3_server import V5Sam3Facade

    args.output.mkdir()
    torch.set_num_threads(1)
    facade = V5Sam3Facade(str(args.checkpoint.resolve(strict=True)))
    for image, prompt in requests:
        facade.segment_all(image, prompt)
    torch.cuda.synchronize()
    modes = []
    cutoff = float(torch.nextafter(torch.tensor(.2, dtype=torch.bfloat16),
        torch.tensor(float('-inf'), dtype=torch.bfloat16)))
    configurations = ((1, 0.), (1, cutoff), (1, 0.)) if args.prefilter_benchmark else ((1, 0.), (4, 0.), (1, 0.))
    for ordinal, (threads, internal_cutoff) in enumerate(configurations):
        torch.set_num_threads(threads)
        facade._processor.confidence_threshold = internal_cutoff
        facade._image_digest = facade._image_state = None
        profiler = cProfile.Profile()
        rows = []
        for image, prompt in requests:
            torch.cuda.synchronize()
            start = perf_counter()
            profiler.enable()
            result = facade.segment_all(image, prompt)
            torch.cuda.synchronize()
            profiler.disable()
            rows.append({'wall_s': perf_counter()-start,
                'response_sha256': hashlib.sha256(json.dumps(result, sort_keys=True,
                    separators=(',', ':')).encode()).hexdigest(), 'instances': len(result['instances'])})
        profile = args.output/f'mode{ordinal}_threads{threads}.pstats'
        profiler.dump_stats(str(profile))
        stats = pstats.Stats(profiler)
        top = sorted(stats.stats.items(), key=lambda row: row[1][3], reverse=True)[:15]
        modes.append({'threads': torch.get_num_threads(), 'internal_cutoff': internal_cutoff,
            'published_min_score': .2, 'requests': rows,
            'total_request_s': sum(row['wall_s'] for row in rows), 'profile': str(profile),
            'top15_cumulative': [{'file': key[0], 'line': key[1], 'function': key[2],
                'calls': value[1], 'self_s': value[2], 'cumulative_s': value[3]} for key, value in top],
            'own_cuda_peak_allocated_bytes': torch.cuda.max_memory_allocated()})
    reference = [r['response_sha256'] for r in modes[0]['requests']]
    result = {'source': str(args.source), 'manifest': str(args.manifest),
        'slurm_job_raw_id': os.environ['SLURM_JOB_ID'], 'step_id': os.environ['SLURM_STEP_ID'],
        'cuda_visible_devices': os.environ['CUDA_VISIBLE_DEVICES'], 'modes': modes,
        'all_response_bytes_equal': all([r['response_sha256'] for r in m['requests']] == reference for m in modes),
        'training': False, 'physics_steps': 0, 'new_gpu_allocations': 0,
        'scope': 'temporary model profiling in an owned allocation; existing RPC services untouched; same original image requests; no independent episode throughput claim'}
    (args.output/'summary.json').write_text(json.dumps(result, indent=2))
    print(json.dumps({'total_request_s': [m['total_request_s'] for m in modes],
        'all_response_bytes_equal': result['all_response_bytes_equal'], 'output': str(args.output)}))


if __name__ == '__main__':
    main()
