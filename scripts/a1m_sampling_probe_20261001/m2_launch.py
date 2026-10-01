#!/usr/bin/env python3
"""Launch SGLang and reject an incomplete FP8-scale load."""
import json
import os
import sys

import torch
from sglang.srt.models.qwen3_5 import Qwen3_5ForConditionalGeneration


original_load = Qwen3_5ForConditionalGeneration.load_weights


def checked_load(self, weights):
    loaded = original_load(self, weights)
    scales = {name: param for name, param in self.named_parameters(remove_duplicate=False)
              if name.endswith('.weight_scale_inv')}
    missing = sorted(set(scales) - set(loaded))
    if missing or not scales:
        raise RuntimeError(f'FP8_scale_load_incomplete:{missing}')
    invalid = [name for name, param in scales.items()
               if not (torch.isfinite(param).all() and (param > 0).all()).item()]
    if invalid:
        raise RuntimeError(f'FP8_scale_invalid:{invalid}')
    print('M2_FP8_SCALE_AUDIT ' + json.dumps({'passed': True, 'scale_tensors': len(scales),
          'missing': missing, 'invalid': invalid}), flush=True)
    return loaded


Qwen3_5ForConditionalGeneration.load_weights = checked_load


if __name__ == '__main__':
    from sglang.launch_server import prepare_server_args, run_server
    from sglang.srt.utils import kill_process_tree
    try:
        run_server(prepare_server_args(sys.argv[1:]))
    finally:
        kill_process_tree(os.getpid(), include_parent=False)
