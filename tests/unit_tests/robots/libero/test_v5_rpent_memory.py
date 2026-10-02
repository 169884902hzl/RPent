"""An evaluation index keeps raw memory intact and rejects a changed source."""

import hashlib
import json

import pytest

from robots.libero.v5_rpent_memory import read_original_files


def test_original_memory_uses_only_declared_unchanged_files(tmp_path):
    original = tmp_path / "recipe.jsonl"
    original.write_text('{"action":"release"}\n')
    index = tmp_path / "index.json"
    index.write_text(json.dumps({"evaluation_only": True, "training_allowed": False,
                                "files": [{"name": "recipe.jsonl", "path": str(original),
                                           "sha256": hashlib.sha256(original.read_bytes()).hexdigest()}]}))
    text, evidence = read_original_files(index)
    assert text.endswith(original.read_text())
    assert evidence["content_transformed"] is False
    assert evidence["content_truncated"] is False
    original.write_text('{"action":"finish"}\n')
    with pytest.raises(ValueError, match="changed"):
        read_original_files(index)


def test_training_index_cannot_enable_original_rpent_memory(tmp_path):
    index = tmp_path / "index.json"
    index.write_text(json.dumps({"evaluation_only": True, "training_allowed": True, "files": []}))
    with pytest.raises(ValueError, match="evaluation-only"):
        read_original_files(index)
