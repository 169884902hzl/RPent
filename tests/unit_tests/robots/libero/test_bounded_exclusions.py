"""Permanent exclusions use state identities and domain-specific seeds."""
import hashlib
import json

import pytest

from scripts.bounded_state_exclusions import check_exclusions


def test_known_states_and_reserved_layouts_are_excluded_without_global_seed_ban(tmp_path):
    rows = [
        {'record_type': 'permanent_state_identity', 'identity_domain': 'official_original_libero_init_state',
         'suite': 'libero_10', 'task': 1, 'official_init_index': 15, 'state_sha256': 'a'*64},
        {'record_type': 'permanent_state_identity', 'identity_domain': 'generated_libero_skill_layout',
         'state_sha256': 'b'*64},
        {'record_type': 'permanent_seed_reservation', 'identity_domain': 'generated_moka_confirmation_layout_seed',
         'range_inclusive': [9200000, 9200999]}]
    path = tmp_path/'registry.jsonl'
    path.write_text(''.join(json.dumps(row)+'\n' for row in rows))
    ref = {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(), 'coverage_complete': False}
    case = {'name': 'development', 'episode': {'suite': 'libero_10', 'task': 2, 'seed': 15}, 'state_sha256': 'c'*64}
    report = check_exclusions([case], ref)
    assert report['overlap'] == 0 and report['coverage_complete'] is False
    assert report['training_admission'] is False
    for forbidden in [
        {**case, 'state_sha256': 'b'*64},
        {**case, 'episode': {**case['episode'], 'task': 1}},
        {**case, 'identity_domain': 'generated_moka_confirmation_layout_seed', 'layout_seed': 9200005}]:
        with pytest.raises(ValueError, match='permanently'):
            check_exclusions([forbidden], ref)
    assert check_exclusions([{**case, 'layout_seed': 9200005}], ref)['overlap'] == 0
