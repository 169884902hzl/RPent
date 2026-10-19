# Copyright 2026 Zhilun Hu.
# SPDX-License-Identifier: Apache-2.0
"""Label an arbitrary prefix from a trusted private snapshot, CPU only."""
import argparse
import json
import os
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--state', type=Path, required=True)
    parser.add_argument('--state-sha256', required=True)
    parser.add_argument('--request', type=Path, required=True)
    parser.add_argument('--prefix', type=Path, required=True, help='JSON list of candidate IDs')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--workers', type=int, default=1,
                        help='CPU consequence processes; default 1 preserves serial annotation')
    args = parser.parse_args()
    os.environ['CUDA_VISIBLE_DEVICES'] = ''
    os.environ['OPENBLAS_NUM_THREADS'] = '1'
    os.environ['OMP_NUM_THREADS'] = '1'
    from robots.libero.bounded_offline_labels import (
        annotate_prefix,
        load_annotation_state,
    )

    state = load_annotation_state(args.state, args.state_sha256)
    result = annotate_prefix(state, json.loads(args.request.read_text()), json.loads(args.prefix.read_text()),
                             workers=args.workers)
    with args.output.open('x') as stream:
        stream.write(json.dumps(result, ensure_ascii=False, allow_nan=False, indent=2)+'\n')


if __name__ == '__main__':
    main()
