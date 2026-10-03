"""Collection must reject absent init identity before simulator execution."""

import pytest

from v5_batch_eval import validate_collection_identities


def test_original_and_counterfactual_episodes_require_registered_init_hashes():
    original = {"suite": "libero_object", "task": 1, "seed": 31, "init_state_sha256": "a" * 64}
    variant = {**original, "counterfactual_spec": "/original-only/spec.json"}
    validate_collection_identities([original, variant])
    with pytest.raises(ValueError, match="init_state_sha256"):
        validate_collection_identities([{k: v for k, v in variant.items() if k != "init_state_sha256"}])


@pytest.mark.parametrize("digest", [None, "", "unregistered", "a" * 63, "A" * 64])
def test_malformed_init_hash_is_rejected(digest):
    with pytest.raises(ValueError, match="init_state_sha256"):
        validate_collection_identities([
            {"suite": "libero_object", "task": 1, "seed": 31, "init_state_sha256": digest}
        ])
