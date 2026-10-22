"""Finite public VLA choices and cheap monitoring before final measurement."""
from dataclasses import replace

from rpent.skill_package.contract import validate
from rpent.skill_package.vla import VLABudget
from robots.libero.bounded_vla_options import instruction_clauses,render_variant
from tests.unit_tests.robots.libero.test_bounded_skills import adapter  # noqa: F401


def test_original_clause_keeps_drawer_interior_wording_and_resolves_pronoun():
    instruction = 'pick up the moka pot and place it inside the middle layer of the drawer'
    clauses = instruction_clauses(instruction)
    assert clauses[1] == 'place the moka pot inside the middle layer of the drawer'
    assert 'surface' not in clauses[1]
    assert render_variant(instruction,{'mode':'task'},None)==instruction
    assert render_variant(instruction,{'mode':'instruction','clause_id':1},None)==clauses[1]


def test_registered_preparations_and_unbound_instruction_choices_are_published(adapter):
    from rpent.skill_package import VERSION
    adapter.schema6_v1 = True
    adapter.allow_vla = True
    adapter.vla_options_v2 = True
    request = adapter.request()
    validate(request)
    calls = [c for c in request['candidates'] if c['skill']=='call_vla']
    picks = [c for c in calls if c['parameters'].get('anchor_id')=='e1']
    expected={'in_place','initial_pose'} | ({'measured_anchor'} if VERSION=='bounded-skills/7' else set())
    assert {c['parameters']['preparation'] for c in picks} == expected
    unbound=[c for c in calls if c['parameters']['mode'] in {'task','instruction'}]
    assert all(c['parameters']['preparation'] in {'in_place','initial_pose'} for c in unbound)
    assert any(c['parameters']['mode']=='task' and 'anchor_id' not in c['parameters'] for c in calls)
    assert any(c['parameters']['mode']=='instruction' for c in calls)
    assert request['instruction_clauses'] == instruction_clauses(adapter.ex.instruction)
    adapter._vla_failed_options = {('e1',None,'pick',None)}
    request = adapter.request()
    retries = [c for c in request['candidates'] if c['skill']=='call_vla'
        and c['parameters'].get('seed_variant')==1]
    assert {c['parameters']['prompt_style'] for c in retries} == {'original_clause','full_task','a1_description'}


def test_proprioceptive_block_checks_do_not_refresh_scene(adapter,monkeypatch):
    adapter.schema6_v1 = adapter.allow_vla = True
    adapter.vla_budget = VLABudget(controls_per_check=None,no_progress_blocks=5)
    refreshes = []
    monkeypatch.setattr(adapter,'refresh',lambda **kwargs:refreshes.append(kwargs))
    def fallback(**kwargs):
        assert kwargs['prepare']()=={'success':True,'steps_used':0,'mode':'in_place'}
        for _ in range(5):
            check = kwargs['observe']()
            assert not check['completed'] and not refreshes
        return {'outcome':'failure','stop_reason':'block_budget'}
    monkeypatch.setattr('robots.libero.bounded_skills.run_fallback',fallback)
    result = adapter.call_vla({'mode':'task','preparation':'in_place'})
    assert len(refreshes)==1 and result['outcome']=='failure'


def test_ambiguous_same_class_ids_remain_available_with_unbound_call(adapter):
    adapter.schema6_v1 = adapter.allow_vla = True
    adapter.vla_options_v2 = True
    adapter.scene.entities['peer'] = replace(adapter.scene.entities['e1'],id='peer')
    request = adapter.request()
    assert {a['id'] for a in request['anchors']}=={'e1','peer'}
    assert any(c['skill']=='call_vla' and c['parameters']['mode']=='instruction' for c in request['candidates'])


def test_new_vla_catalog_stays_disabled_until_three_consumers_sync(adapter):
    adapter.schema6_v1=adapter.allow_vla=True
    assert not adapter.vla_options_v2
    request=adapter.request()
    assert 'instruction_clauses' not in request
    assert all(c['parameters'].get('mode') not in {'task','instruction'}
        for c in request['candidates'] if c['skill']=='call_vla')
