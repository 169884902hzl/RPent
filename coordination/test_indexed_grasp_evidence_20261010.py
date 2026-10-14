"""Protect exact evidence identity across the two observed file formats."""

import hashlib
import json
import pytest

from coordination.load_indexed_grasp_evidence_20261010 import canonical_object_sha, load_indexed_row


def test_pretty_json_uses_document_pointer(tmp_path):
    value = {'first_attempt': {'receipt': {'grasp_verified': False}}}
    path = tmp_path / 'diagnostic.json'
    path.write_text(json.dumps([value], indent=2) + '\n')
    index = {'captured_path': str(path), 'input_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
             'source_format': 'json', 'json_pointer': '/0', 'line': None,
             'raw_object_sha256': canonical_object_sha(value)}
    assert load_indexed_row(index, {}) == value
    with pytest.raises(ValueError, match='not a line'):
        load_indexed_row({**index, 'line': 2}, {})


def test_jsonl_preserves_real_line_and_hash(tmp_path):
    path = tmp_path / 'episodes.jsonl'
    row = json.dumps({'receipt': {'grasp_verified': True}}).encode()
    path.write_bytes(b'{}\n' + row + b'\n')
    index = {'captured_path': str(path), 'input_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
             'line': 2, 'raw_row_sha256': hashlib.sha256(row).hexdigest()}
    assert load_indexed_row(index, {})['receipt']['grasp_verified'] is True
    with pytest.raises(ValueError, match='row differs'):
        load_indexed_row({**index, 'line': 1}, {})


def test_changed_capture_is_rejected(tmp_path):
    path = tmp_path / 'diagnostic.json'
    path.write_text('{}')
    index = {'captured_path': str(path), 'input_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
             'source_format': 'json', 'line': None, 'raw_object_sha256': canonical_object_sha({})}
    path.write_text('{"changed":true}')
    with pytest.raises(ValueError, match='evidence changed'):
        load_indexed_row(index, {})
