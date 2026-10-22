"""Rendered layout starts must not inherit CPU sensor buffers or admit PRO."""
import copy
from types import SimpleNamespace

import pytest

from robots.libero.bounded_generated_start import materialize_original_layout


def setup():
    parent = {'split': 'train', 'suite': 'libero_object', 'task': 0, 'seed': 10}
    generated = {'layout': {'parent': parent, 'layout_seed': 11020300,
        'identity_domain': 'own_original_train_layout', 'PRO': False, 'D2': False,
        'confirmation': False}, 'sim_state': [1., 2.],
        'actuator_state': {'integration': {'sha256': 'authored'}, 'rng': {'numpy': [1]},
            'observation_state': {'CPU_proprioception_only': True},
            'native_data': {'CPU_buffers': True}}}
    initial = {'task': {k: parent[k] for k in ('suite', 'task', 'seed')},
        'bddl_sha256': 'original', 'sim_state': [0.], 'counters': {'steps': 0},
        'native_success_event_count': 0, 'actuator_state': {'integration': {'sha256': 'fresh'}}}
    restored = []
    state = {'value': initial}

    def restore(value):
        restored.append(copy.deepcopy(value))
        state['value'] = value | {'actuator_state': value['actuator_state'] | {
            'observation_state': {'fresh_rendered_camera': True},
            'native_data': {'fresh_rendered_buffers': True}}}
        return {'public_eef': [0., 0., 1.]}

    facade = SimpleNamespace(snapshot=lambda: copy.deepcopy(state['value']), restore=restore)
    observations = []
    primitives = SimpleNamespace(env=SimpleNamespace(terminated=True, truncated=True),
        set_obs=observations.append)
    return generated, facade, primitives, restored, observations, state


def authored_setup(tmp_path):
    import hashlib
    from robots.libero.bounded_layout_distractors import add_distractors
    parent = {'split': 'train', 'suite': 'libero_spatial', 'task': 0, 'seed': 10}
    text = '''(define (problem LIBERO_Tabletop_Manipulation)
    (:domain robosuite) (:language Put the bowl on the plate)
    (:fixtures main_table - table) (:regions) (:objects bowl_1 - bowl plate_1 - plate)
    (:obj_of_interest bowl_1 plate_1) (:init) (:goal (And (On bowl_1 plate_1))))'''
    original = tmp_path/'original.bddl';original.write_text(text)
    value, world = add_distractors(text, parent=parent,
        distractors=[{'id':'rd_extra_1','asset':'alphabet_soup'}], support_symbol='main_table',
        ranges=[-.3,-.3,.3,.3], available_assets={'alphabet_soup'})
    added = tmp_path/'added.bddl';added.write_text(value)
    world['bddl'] = {'path':str(added),'sha256':hashlib.sha256(added.read_bytes()).hexdigest()}
    generated = {'layout': {'parent':parent,'layout_seed':11020400,
        'predicate_witness': {'native_predicates_satisfied':True,
            'nonintersecting':True,'instruction_identity_consistent':True}}, 'authored_world':world}
    return generated, original, added, {key:parent[key] for key in ('suite','task','seed')}


def test_authored_bootstrap_uses_the_validated_added_model(tmp_path):
    from robots.libero.bounded_generated_start import authored_world_path
    generated, original, added, episode = authored_setup(tmp_path)
    assert authored_world_path(generated, original, episode) == added
    added.write_text(added.read_text().replace('alphabet_soup', 'ketchup'))
    with pytest.raises(ValueError, match='changed after CPU'):
        authored_world_path(generated, original, episode)


@pytest.mark.parametrize('change', ['parent', 'goal', 'witness'])
def test_authored_bootstrap_rejects_other_parent_changed_goal_and_missing_witness(tmp_path, change):
    import hashlib
    from robots.libero.bounded_generated_start import authored_world_path
    generated, original, added, episode = authored_setup(tmp_path)
    if change == 'parent':
        episode['seed'] += 1
    elif change == 'witness':
        generated['layout']['predicate_witness']['nonintersecting'] = False
    else:
        added.write_text(added.read_text().replace('(On bowl_1 plate_1)', '(On bowl_1 main_table)'))
        value = hashlib.sha256(added.read_bytes()).hexdigest()
        generated['authored_world']['bddl']['sha256'] = value
        generated['authored_world']['authored_bddl_sha256'] = value
    with pytest.raises(ValueError):
        authored_world_path(generated, original, episode)


def test_materialization_keeps_integration_and_refreshes_cameras_before_branching():
    generated, facade, primitives, restored, observations, _ = setup()
    original = copy.deepcopy(generated)
    audit = materialize_original_layout(facade, primitives, generated, bddl_sha256='original')
    assert generated == original
    assert restored[0]['sim_state'] == generated['sim_state']
    assert restored[0]['actuator_state'] == {
        'integration': {'sha256': 'authored'}, 'rng': {'numpy': [1]}}
    assert restored[0]['counters'] == {'steps': 0}
    assert observations == [primitives.env.last_obs] and not primitives.env.terminated
    assert not primitives.env.truncated and not audit['constructor_full_state_identity_reused']
    assert audit['integration_sha256'] == 'authored' and audit['canonical_physics_sha256']


@pytest.mark.parametrize('field,value', [('PRO', True), ('D2', True),
    ('confirmation', True), ('suite', 'libero_object_swap'), ('split', 'init_holdout')])
def test_evaluation_domains_are_rejected_before_touching_a_simulator(field, value):
    generated, facade, primitives, restored, _, _ = setup()
    generated['layout']['parent'][field] = value
    facade.snapshot = lambda: pytest.fail('evaluation input reached simulator')
    with pytest.raises(ValueError, match='original train'):
        materialize_original_layout(facade, primitives, generated, bddl_sha256='original')
    assert not restored


def test_different_task_and_seed_cannot_reuse_an_authored_state():
    generated, facade, primitives, restored, _, state = setup()
    with pytest.raises(ValueError, match='another original task'):
        materialize_original_layout(facade, primitives, generated, bddl_sha256='other')
    state['value']['task']['seed'] = 11
    with pytest.raises(ValueError, match='parent and original runtime differ'):
        materialize_original_layout(facade, primitives, generated, bddl_sha256='original')
    assert not restored


def test_materialization_does_not_claim_identity_when_integration_changes():
    generated, facade, primitives, restored, observations, state = setup()
    original_restore = facade.restore
    def altered(value):
        observed = original_restore(value)
        state['value']['actuator_state']['integration']['sha256'] = 'changed'
        return observed
    facade.restore = altered
    with pytest.raises(RuntimeError, match='integration state changed'):
        materialize_original_layout(facade, primitives, generated, bddl_sha256='original')


def test_pilot_keeps_authoring_geometry_out_of_the_public_request(tmp_path, monkeypatch):
    from contextlib import contextmanager, nullcontext
    import time
    from coordination.bounded_skills_20261016.scripts import run_own_layout_pi_pilot_20261022 as pilot
    from robots.libero import bounded_offline_labels
    from scripts import probe_bounded_hybrid_d2 as probe

    generated = {'private_geometry': 'not public'}
    construction = {'layout': {'layout_seed': 11020300}}
    monkeypatch.setattr(pilot, 'validate_job', lambda *_: (generated, construction))
    request = {'candidates': [{'id': 'public_task', 'skill': 'call_vla',
        'parameters': {'mode': 'task', 'preparation': 'in_place'}}]}
    facade = SimpleNamespace(goal_status=lambda: {'goals': [['on', 'private_symbol', 'plate']]})
    adapter = SimpleNamespace(request=lambda **_: request, ex=SimpleNamespace(instruction='original exact text'))
    timings = SimpleNamespace(started=time.perf_counter(), measure=lambda *_: nullcontext(),
        summary=lambda wall_s: {'wall_s': wall_s})

    @contextmanager
    def runtime(*args, **kwargs):
        assert kwargs['domain'] == 'original' and kwargs['constructed_start'] is generated
        yield facade, adapter, object(), timings

    def trial(*args, **kwargs):
        assert args[8] is request and 'private_symbol' not in repr(request)
        assert kwargs['vla_parameters'] == {
            'mode': 'task', 'preparation': 'in_place', 'prompt_style': 'full_task'}
        return {'success': True, 'sim_steps': 5, 'vla_inference_calls': 1}, {}

    monkeypatch.setattr(probe, 'runtime', runtime)
    monkeypatch.setattr(probe, 'trial', trial)
    monkeypatch.setattr(probe, 'save_checkpoint', lambda *_: ({}, {'physics_sha256': 'canonical'}))
    monkeypatch.setattr(bounded_offline_labels, 'capture_annotation_state', lambda *_: {})
    monkeypatch.setattr(bounded_offline_labels, 'save_annotation_state', lambda *_: {'sha256': 'private'})
    row = {'case': {}, 'vla_budget': {}, 'trial_seed': 42,
        'construction_report': {'sha256': 'construction'}, 'generated_state': {'sha256': 'generated'}}
    result = pilot.run_case(row, {'source_commit': 'pilot'}, {}, tmp_path/'episode', startup=True)
    assert result['sim_steps'] == 5 and result['success'] is True
    assert result['requested_task_text'] == 'original exact text'
    assert not result['training_admission'] and result['canonical_branchpoint']['physics_sha256'] == 'canonical'
