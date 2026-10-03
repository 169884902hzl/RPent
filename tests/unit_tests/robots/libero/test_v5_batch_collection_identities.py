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


def test_missing_registration_can_be_repaired_without_changing_scene_or_budget():
    from types import SimpleNamespace

    import numpy as np

    from scripts.pin_v5_collection_inits import pin

    states = np.arange(100, dtype=np.float64).reshape(50, 2)
    benchmarks = {"libero_object": SimpleNamespace(get_task_init_states=lambda task: states)}
    episode = {"suite": "libero_object", "task": 1, "seed": 35}
    original = {"libero_type": "standard", "budget": {"max_decisions": 100}, "episodes": [episode]}
    repaired = pin(original, benchmarks)
    validate_collection_identities(repaired["episodes"])
    assert repaired["budget"] == original["budget"]
    assert {k: repaired["episodes"][0][k] for k in episode} == episode
    assert "init_state_sha256" not in episode
    assert pin(repaired, benchmarks) == repaired
    benchmarks["libero_object"].get_task_init_states = lambda task: states + 1
    with pytest.raises(ValueError, match="differs from installed asset"):
        pin(repaired, benchmarks)


@pytest.mark.parametrize("suite,init", [("libero_spatial_swap", 10), ("libero_object", 9),
                                      ("libero_object", 40), ("libero_object", 41)])
def test_registration_repair_cannot_admit_pro_or_evaluation_inits(suite, init):
    from scripts.pin_v5_collection_inits import pin

    with pytest.raises(ValueError):
        pin({"libero_type": "standard", "episodes": [
            {"suite": suite, "task": 1, "seed": init}
        ]}, {})
