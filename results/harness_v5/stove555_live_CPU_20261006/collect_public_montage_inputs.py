"""Select public original4210 views explicitly; private labels are never opened."""

import hashlib
import json
from pathlib import Path


ROOT = Path('/public/home/sunyihan/rpent_libero_eval')
MANIFEST = ROOT / 'results/harness_v5/stove555_fixed_prefix_CPU_20261006/stove_control_sampling10.json'
RUN = ROOT / 'results/harness_v5/stove555_measurement10_original_20261006/probe_job4210'
plan = json.loads(MANIFEST.read_text())
# Selection is explicit original seed and fixed phase/stage, not private qpos.
selected = [(0, 'on', 'before_contact'), (0, 'on', 'post_recovery'),
            (0, 'off', 'before_contact'), (0, 'off', 'post_recovery'),
            (5, 'on', 'post_recovery'), (5, 'off', 'post_recovery')]
records = []
for index, phase, stage in selected:
    case = plan['cases'][index]
    directory = RUN / f'part{index % plan["shards"]}' / case['name'] / phase / stage
    path = directory / 'public_measurements.json'
    packet = json.loads(path.read_text())
    record = {'case': case['name'], 'phase': phase, 'stage': stage, 'source_step': packet['source_step'],
              'packet': {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()},
              'current_shell': packet['current_stove_shell'], 'views': {}}
    for camera in plan['capture_views']:
        view = packet['views'][camera]
        record['views'][camera] = {key: view[key] for key in ('files', 'queries', 'control_features')}
    records.append(record)
print(json.dumps({'manifest': {'path': str(MANIFEST), 'sha256': hashlib.sha256(MANIFEST.read_bytes()).hexdigest()},
                  'selected_public_views': records, 'private_labels_opened': False}))
