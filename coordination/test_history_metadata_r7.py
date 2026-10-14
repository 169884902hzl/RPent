"""Regressions for recorded metadata; no label or pose reconstruction."""

from coordination.enrich_grasp_history_metadata_r7_20261010 import metadata


def test_choice_category_and_initial_identity_use_saved_measurement_and_config():
    row = {'receipt': {'tool': 'grasp', 'object': 'e39', 'mode': 'direct'},
           'measurements': [{'id': 'e39', 'name': 'white yellow mug', 'src': 'perception'}]}
    result = metadata(row, row, {'source_manifests': [{'path': 'config.json'}]},
                      [{'suite': 'libero_10', 'task': 9, 'seed': 4}])
    assert result['category'] == 'cup'
    assert result['category_source'] == 'recorded_public_entity_name'
    assert result['original_episode_key'] == {'suite': 'libero_10', 'task': 9, 'seed': 4}
    assert result['state_identity'] is None
    assert result['method'] is None
    assert result['recorded_skill_mode']['mode'] == 'direct'


def test_first_attempt_uses_explicit_case_category_without_private_label_inference():
    stage = {'receipt': {'tool': 'grasp', 'object': 'e3', 'mode': 'analytic'}}
    row = {'case': {'category': 'bowl', 'condition': 'high_short160'},
           'first_attempt': stage, 'true_sustained_grasp': True}
    result = metadata(row, stage, {})
    assert result['category'] == 'bowl'
    assert result['method'] == 'high_short160'
    assert result['sample_count'] == 0
    assert result['full_integration_states_saved'] is False
    assert result['matching_model_evidence_saved'] is False


def test_missing_or_ambiguous_recorded_entity_name_stays_unknown():
    row = {'receipt': {'tool': 'grasp', 'object': 'e1'},
           'measurements': [{'id': 'e1', 'name': 'wine bottle'}, {'id': 'e1', 'name': 'black bowl'}],
           'true_sustained_grasp': True, 'private_final_target': 'wine_bottle_1'}
    result = metadata(row, row, {})
    assert result['category'] is None
    assert result['object_name_recorded'] is None
    assert result['state_identity'] is None


def test_legacy_sustained_hold_keeps_its_measured_window():
    row = {'receipt': {'tool': 'grasp'}, 'contact_samples': [{'sim_time': 1}],
           'sustained_hold': {'reference': {'lower_extent_m': .9},
                             'samples': [{'sim_time': 2+i*.05} for i in range(11)]}}
    result = metadata(row, row, {})
    assert result['sample_count'] == 11
    assert result['reference_saved'] is True
    assert result['full_integration_states_saved'] is False
