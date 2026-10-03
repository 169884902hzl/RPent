"""Counterfactual replay wording and memory retain the verified goal identity."""

import hashlib
import json

import pytest

from scripts.expand_v5_original_rewrites import registered_rewrites
from scripts.rerender_v5_format118_20261002 import goal_card_key


def test_counterfactual_replay_does_not_reuse_original_goal_instructions(tmp_path):
    spec = tmp_path / 'spec.json'
    spec.write_text(json.dumps({'variant_bddl_sha256': 'a' * 64, 'rewrites': ['leave the bowl here']}))
    (tmp_path / 'config.json').write_text(json.dumps({'counterfactual_spec': str(spec)}))
    row = {'suite': 'libero_object', 'task_id': 1,
           'scene_id': 'original/libero_object/t1/init31/cf_aaaaaaaaaaaa/replay_identity_repair',
           'counterfactual_spec_sha256': hashlib.sha256(spec.read_bytes()).hexdigest()}
    bank = {'tasks': {'libero_object/1': {'rewrites': ['put the bowl in the basket']}}}
    inputs = {}
    goal, texts = registered_rewrites(row, bank, tmp_path / 'choices.jsonl', inputs)
    assert goal == goal_card_key(row) == 'libero_object/1/cf_aaaaaaaaaaaa'
    assert texts == ['leave the bowl here']
    assert str(spec) in inputs
    spec.write_text('{}')
    with pytest.raises(ValueError, match='specification changed'):
        registered_rewrites(row, bank, tmp_path / 'choices.jsonl', {})


def test_original_replay_uses_original_wording_and_task_card(tmp_path):
    row = {'suite': 'libero_object', 'task_id': 1,
           'scene_id': 'original/libero_object/t1/init31/replay_identity_repair'}
    bank = {'tasks': {'libero_object/1': {'rewrites': ['put the bowl in the basket']}}}
    goal, texts = registered_rewrites(row, bank, tmp_path / 'choices.jsonl', {})
    assert goal == goal_card_key(row) == 'libero_object/1'
    assert texts == ['put the bowl in the basket']
