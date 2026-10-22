"""Task identity and named-state transfer for private original-world authoring."""
import numpy as np
import pytest

from robots.libero.bounded_layout_distractors import add_distractors, section, transplant_named_state

TEXT = '''(define (problem LIBERO_Tabletop_Manipulation)
(:domain robosuite)
(:language Pick the bowl and place it on the plate)
(:regions (bowl_region (:target main_table) (:ranges ((-.1 -.1 .1 .1)))))
(:fixtures main_table - table)
(:objects bowl_1 - bowl plate_1 - plate)
(:obj_of_interest bowl_1 plate_1)
(:init (On bowl_1 main_table_bowl_region))
(:goal (And (On bowl_1 plate_1))))'''
PARENT = {'suite': 'libero_spatial', 'task': 0, 'seed': 0, 'split': 'train'}


def compose(**kwargs):
    return add_distractors(TEXT, parent=PARENT,
        distractors=[{'id': 'rd_extra_1', 'asset': 'alphabet_soup'}],
        support_symbol='main_table', ranges=[-.3, -.3, .3, .3],
        available_assets={'alphabet_soup'}, **kwargs)


def test_added_asset_does_not_rewrite_task_language_goal_or_object_interest():
    result, audit = compose()
    for name in ('language', 'goal', 'obj_of_interest'):
        assert result[slice(*section(result, name))] == TEXT[slice(*section(TEXT, name))]
    assert 'rd_extra_1 - alphabet_soup' in result
    assert '(On rd_extra_1 main_table_rd_extra_1_initial_region)' in result
    assert audit['task_language_and_goal_bytes_unchanged']
    assert not audit['training_admission']


@pytest.mark.parametrize('field,value', [('split', 'init_holdout'), ('PRO', True),
    ('D2', True), ('confirmation', True), ('suite', 'libero_spatial_swap')])
def test_evaluation_parent_cannot_author_distractors(field, value):
    with pytest.raises(ValueError, match='original train'):
        add_distractors(TEXT, parent={**PARENT, field: value}, distractors=[],
            support_symbol='main_table', ranges=[-.3, -.3, .3, .3], available_assets=set())


def test_unknown_asset_and_reused_identity_are_rejected():
    with pytest.raises(ValueError, match='installed original'):
        add_distractors(TEXT, parent=PARENT, distractors=[{'id':'extra','asset':'new_weight_asset'}],
            support_symbol='main_table', ranges=[-.3,-.3,.3,.3], available_assets=set())
    with pytest.raises(ValueError, match='already occurs'):
        add_distractors(TEXT, parent=PARENT, distractors=[{'id':'bowl_1','asset':'alphabet_soup'}],
            support_symbol='main_table', ranges=[-.3,-.3,.3,.3], available_assets={'alphabet_soup'})


def test_named_transfer_handles_inserted_joint_without_copying_original_state_vector():
    import mujoco
    original = '<mujoco><worldbody><body name="object"><freejoint name="object_joint"/><geom size=".03"/></body></worldbody></mujoco>'
    added = '<body name="extra" pos=".2 0 .1"><freejoint name="extra_joint"/><geom size=".02"/></body>'
    source = mujoco.MjModel.from_xml_string(original)
    target = mujoco.MjModel.from_xml_string(original.replace('<worldbody>', '<worldbody>'+added))
    a, b = mujoco.MjData(source), mujoco.MjData(target)
    a.qpos[:3] = [.1,.2,.3]; a.qvel[:] = np.arange(6)*.01; a.time = 2.
    extra = b.qpos[:7].copy()
    audit = transplant_named_state(source, a, target, b)
    np.testing.assert_array_equal(b.qpos[:7], extra)
    np.testing.assert_array_equal(b.qpos[7:], a.qpos)
    np.testing.assert_array_equal(b.qvel[6:], a.qvel)
    assert b.time == 2. and audit['joints'] == 1
    assert not audit['exact_original_fork'] and audit['new_complete_state_required']
