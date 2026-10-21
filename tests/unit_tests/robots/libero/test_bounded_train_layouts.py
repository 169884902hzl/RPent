"""Original-train admission, spatial exclusion and deterministic generation."""
import copy

import numpy as np
import pytest

from robots.libero.bounded_train_layouts import generate_layout,overlap,LayoutLimits

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
