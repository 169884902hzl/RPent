"""Permanent layout geometry is consumed without releasing unexecuted rows."""
import hashlib
import json

import pytest

from scripts.generate_bounded_train_layouts import confirmation_geometry


def pin(path, value):
    raw = json.dumps(value).encode()
    path.write_bytes(raw)
    return {'path':str(path), 'sha256':hashlib.sha256(raw).hexdigest()}


def registry(tmp_path):
    pool = pin(tmp_path/'pool.json', {'permanent_training_exclusion':True,
        'rows':[{'permanent_training_exclusion':True, 'status':status,
            'preparation_provenance':{'settled_geometry':{'bottle_1':[x,0.,.1]}}}
            for status,x in [('executed',0.),('unexecuted',.2),('invalid',.4)]]})
    moka = pin(tmp_path/'moka.json', {'records':[{'permanent_training_exclusion':True,
        'layout_parameters':{'rule':{'moved_object_symbol':'moka_pot_1'}},
        'settled_moka_xy_m':[.1,.2]}]})
    return pin(tmp_path/'registry.json', {
        'fiveclass_pool_reconciliation':{'pool_metadata':[{'pool':pool}]},
        'source_index':{'moka100':moka},
        'counts':{'official_original_confirmation_states':665}}), pool


def test_all_reserved_geometry_is_kept_and_partial_coverage_is_explicit(tmp_path):
    ref, _ = registry(tmp_path)
    layouts, evidence = confirmation_geometry(ref)
    assert layouts == [{'bottle_1':[0.,0.,.1]}, {'bottle_1':[.2,0.,.1]},
        {'bottle_1':[.4,0.,.1]}, {'moka_pot_1':[.1,.2,0.]}]
    assert evidence['geometry_records_checked'] == 4
    assert evidence['original_confirmation_geometry_records_missing'] == 665
    assert evidence['coverage_complete'] is False
    assert evidence['training_admission'] is False


def test_pool_bytes_cannot_change_under_a_registered_hash(tmp_path):
    ref, pool = registry(tmp_path)
    from pathlib import Path
    Path(pool['path']).write_text('{}')
    with pytest.raises(ValueError, match='registered original source changed'):
        confirmation_geometry(ref)
