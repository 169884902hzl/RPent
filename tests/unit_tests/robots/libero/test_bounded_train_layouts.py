"""Original-train admission, spatial exclusion and deterministic generation."""
import copy

import numpy as np
import pytest

from robots.libero.bounded_train_layouts import generate_layout,overlap,LayoutLimits,instruction_identity_check

PARENT={'split':'train','suite':'libero_object','task':0,'initial_state_sha256':'pinned-parent'}
OBJECTS=[{'id':name,'xyz_m':[x,0.,.05],'size_m':[.04,.05,.10],
    'yaw_rad':0.,'movable':True} for name,x in [('a',-.12),('b',.12)]]
SUPPORT={'lower_m':[-.4,-.3,-.05],'upper_m':[.4,.3,0.]}


def generate(**kwargs):
    return generate_layout(parent=PARENT,objects=OBJECTS,support=SUPPORT,seed=11020000,
        witness_check=lambda objects:{'native_predicates_satisfied':True,'source':'test-only fake native witness'},**kwargs)


def test_seeded_generator_is_deterministic_and_nonintersecting():
    before=copy.deepcopy(OBJECTS)
    a,b=generate(),generate()
    assert a==b and OBJECTS==before
    assert not overlap(*a['objects'],.01)
    assert a['predicate_witness']['native_predicates_satisfied']
    assert any(np.linalg.norm(np.array(x['xyz_m'])-y['xyz_m'])>.05 for x,y in zip(a['objects'],OBJECTS))


@pytest.mark.parametrize('field,value',[('split','init_holdout'),('PRO',True),('D2',True),('confirmation',True),('suite','libero_object_swap')])
def test_holdout_and_test_domains_are_rejected_before_sampling(field,value):
    parent={**PARENT,field:value}
    with pytest.raises(ValueError):
        generate_layout(parent=parent,objects=OBJECTS,support=SUPPORT,seed=11020000,witness_check=lambda _:None)


def test_permanent_layout_distance_and_native_witness_are_required():
    initial=generate()
    exclude={x['id']:x['xyz_m'] for x in initial['objects']}
    other=generate(confirmation_layouts=[exclude])
    assert all(np.linalg.norm(np.array(x['xyz_m'])-exclude[x['id']])>=.05 for x in other['objects'])
    with pytest.raises(ValueError,match='original_task_witness_failed'):
        generate_layout(parent=PARENT,objects=OBJECTS,support=SUPPORT,seed=11020000,
            limits=LayoutLimits(attempts=2),witness_check=lambda _:{'native_predicates_satisfied':False})


def test_confirmation_distance_cannot_be_bypassed_by_object_height():
    first = generate()
    # The registered rule compares settled world XY, not 3D centre distance.
    excluded = {x['id']: [*x['xyz_m'][:2], x['xyz_m'][2]+.2] for x in first['objects']}
    other = generate(confirmation_layouts=[excluded])
    assert other['confirmation_distance_metric'] == 'world_xy_euclidean'
    assert all(np.linalg.norm(np.asarray(x['xyz_m'])[:2]-excluded[x['id']][:2]) >= .05
        for x in other['objects'])


def test_confirmation_clusters_do_not_confine_proposals_to_parent_neighbourhood():
    # The actual registered pools exclude almost every +/-12 cm offset.
    # There is still free tabletop above/below this covered horizontal band.
    excluded = [{item['id']:[float(x),float(y),0.] for item in OBJECTS}
        for x in np.arange(-.26,.261,.04) for y in np.arange(-.16,.161,.04)]
    layout = generate(confirmation_layouts=excluded)
    assert layout['proposal_strategy'] == 'uniform_free_support'
    assert all(abs(item['xyz_m'][0]) > .26 or abs(item['xyz_m'][1]) > .16
        for item in layout['objects'])
    assert all(min(np.linalg.norm(np.asarray(item['xyz_m'])[:2]-old[item['id']][:2])
        for old in excluded) >= .05 for item in layout['objects'])


def test_confirmation_distance_uses_registered_body_origin_not_bounds_centre():
    objects = [{**item, 'local_centre_m':[.1,0.,0.]} for item in OBJECTS]

    def body_xy(item):
        angle = item['yaw_rad']
        c,s = np.cos(angle),np.sin(angle)
        return np.asarray(item['xyz_m'])[:2]-np.array([[c,-s],[s,c]]) @ [.1,0.]

    def sample(excluded=()):
        return generate_layout(parent=PARENT,objects=objects,support=SUPPORT,seed=11020000,
            confirmation_layouts=excluded,
            witness_check=lambda _: {'native_predicates_satisfied':True})

    first = sample()
    excluded = {item['id']:[*body_xy(item),0.] for item in first['objects']}
    following = sample([excluded])
    assert all(np.linalg.norm(body_xy(item)-excluded[item['id']][:2]) >= .05
        for item in following['objects'])


def test_layout_cannot_change_which_bowl_the_original_instruction_references():
    objects=[{'id':name,'xyz_m':[x,0.,.05],'size_m':[.03,.03,.03],
        'yaw_rad':0.,'movable':True} for name,x in
        [('akita_black_bowl_1',0.),('akita_black_bowl_2',.3),('plate_1',-.1),
         ('glazed_rim_porcelain_ramekin_1',.1)]]
    goals=[['on','akita_black_bowl_1','plate_1']]
    instruction='pick up the black bowl between the plate and the ramekin and place it on the plate'
    axes=((1.,0.,0.),(0.,-1.,0.))
    assert instruction_identity_check(objects,goals,instruction,axes)['instruction_identity_consistent']
    objects[0]['xyz_m'],objects[1]['xyz_m']=objects[1]['xyz_m'],objects[0]['xyz_m']
    checked=instruction_identity_check(objects,goals,instruction,axes)
    assert not checked['instruction_identity_consistent']
    assert checked['movable_sources'][0]['resolved']=='akita_black_bowl_2'


def test_native_goal_witness_does_not_override_changed_instruction_binding():
    with pytest.raises(ValueError,match='original_instruction_binding_changed'):
        generate_layout(parent=PARENT,objects=OBJECTS,support=SUPPORT,seed=11020000,
            limits=LayoutLimits(attempts=2),witness_check=lambda _:dict(
                native_predicates_satisfied=True,nonintersecting=True,
                instruction_identity_consistent=False))
