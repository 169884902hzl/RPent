"""Consume pinned permanent state identities without reading test contents."""
from __future__ import annotations

import json
from pathlib import Path

from scripts.v5_probe_preflight import pinned_file


def check_exclusions(cases, reference):
    checked = pinned_file(reference, 'permanent_confirmation_state_registry')
    rows = [json.loads(line) for line in Path(checked['path']).read_text().splitlines() if line.strip()]
    permanent = [row for row in rows if row.get('record_type') == 'permanent_state_identity']
    state_hashes = {row['state_sha256'] for row in permanent}
    originals = {(row['suite'], row['task'], row['official_init_index']) for row in permanent
                 if row.get('identity_domain') == 'official_original_libero_init_state'}
    reservations = [row for row in rows if row.get('record_type') == 'permanent_seed_reservation']
    for case in cases:
        ep = case['episode']
        if case['state_sha256'] in state_hashes or (ep['suite'], ep['task'], ep['seed']) in originals:
            raise ValueError(f"permanently excluded confirmation state: {case['name']}")
        # Layout seeds and official init indices occupy different domains.
        # Never globally ban an unrelated task just for an equal integer.
        for reservation in reservations:
            if case.get('identity_domain') != reservation['identity_domain'] or 'layout_seed' not in case:
                continue
            low, high = reservation['range_inclusive']
            if low <= case['layout_seed'] <= high:
                raise ValueError(f"permanently reserved confirmation layout: {case['name']}")
    return {'registry': checked, 'known_permanent_states': len(state_hashes),
            'known_reservations': len(reservations), 'checked_cases': len(cases),
            'overlap': 0, 'coverage_complete': reference.get('coverage_complete', False),
            'training_admission': False}
