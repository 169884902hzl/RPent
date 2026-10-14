from robots.libero.v5_public_transfer_reference import transfer_reference
from robots.libero.v5_state import Entity


def entity(eid, name, x, y=0, z=1.):
    return Entity(eid, name, (x,y,z), (x-.04,y-.04,z-.02), (x+.04,y+.04,z+.02))


def test_put_destination_relation_does_not_select_source_near_destination():
    scene = [entity('a','bowl',-.2), entity('b','bowl',.2), entity('p','plate',.2)]
    result = transfer_reference(scene, 'put the left bowl on the plate')
    assert result['source'] == 'a'
    assert result['target'] == 'p'
    assert result['source_phrase'] == 'put the left bowl'


def test_middle_is_measured_order_not_entity_list_order():
    scene = [entity('r','bowl',.2), entity('l','bowl',-.2), entity('m','bowl',0), entity('p','plate',.3)]
    assert transfer_reference(scene, 'place the middle bowl on the plate')['source'] == 'm'
    assert transfer_reference(list(reversed(scene)), 'place the middle bowl on the plate')['source'] == 'm'


def test_source_on_cabinet_and_destination_on_plate_are_distinct():
    cabinet = entity('c','cabinet',-.2,0,1.)
    scene = [cabinet, entity('a','bowl',-.2,0,1.04), entity('b','bowl',.2,0,.92), entity('p','plate',.1)]
    result = transfer_reference(scene, 'pick the akita black bowl on the top of the cabinet and place it on the plate')
    assert (result['source'],result['target'],result['mode']) == ('a','p','on')


def test_negated_between_is_not_bound_to_between_object():
    scene = [entity('a','bowl',0,0), entity('b','bowl',0,.2), entity('p','plate',-.2), entity('r','ramekin',.2)]
    result = transfer_reference(scene, 'pick the akita black bowl not between the plate and the ramekin and place it on the plate')
    assert result['source'] == 'b'


def test_near_tied_middle_is_unresolved():
    scene = [entity('a','bowl',0), entity('b','bowl',.01), entity('c','bowl',.2), entity('p','plate',.4)]
    assert transfer_reference(scene, 'put the middle bowl on the plate')['source'] is None


def test_one_visible_bowl_cannot_establish_middle_or_leftmost():
    scene = [entity('a', 'bowl', 0), entity('p', 'plate', .4)]
    assert transfer_reference(scene, 'put the middle bowl on the plate')['source'] is None
    assert transfer_reference(scene, 'put the leftmost bowl on the plate')['source'] is None
    assert transfer_reference(scene, 'put the bowl on the plate')['source'] == 'a'


def test_single_visible_source_still_requires_its_stated_support_relation():
    cabinet = entity('c', 'cabinet', -.2, 0, 1.)
    scene = [cabinet, entity('a', 'bowl', .2, 0, .92), entity('p', 'plate', .1)]
    instruction = 'pick the bowl on the top of the cabinet and place it on the plate'
    assert transfer_reference(scene, instruction)['source'] is None
    scene[1] = entity('a', 'bowl', -.2, 0, 1.04)
    assert transfer_reference(scene, instruction)['source'] == 'a'


def test_cabinet_source_macro_survives_six_option_cap():
    from robots.libero.v5_state import Candidate
    from robots.libero.v5_subtasks import subtask_candidates
    scene = [entity('c','cabinet',-.2,0,1.), entity('a','bowl',-.2,0,1.04),
             entity('b','bowl',.2,0,.92), entity('p','plate',.1)]
    instruction = 'pick the akita black bowl on the top of the cabinet and place it on the plate'
    before = subtask_candidates(scene, instruction, (.2,0,1.2), None)
    after = subtask_candidates(scene, instruction, (.2,0,1.2), None,
                              instruction_transfer_binding_v1=True)
    assert after[0] == Candidate('vla_subtask','a','p','on')
    assert len(after) <= 6
    assert before != after
