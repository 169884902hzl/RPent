"""A placement goal cannot supply object identity or hide a visible misplacement."""
from types import SimpleNamespace

import numpy as np
import pytest

from robots.libero.v5_runtime import MeasuredScene
from robots.libero.v5_state import Entity
from rpent.robots.components.sam3_client import Sam3Client


def scene_with_measurements(monkeypatch, centres, *, target_visible=True, class_count=1,
                            instance_limit=1, include_other=False):
    world = np.empty((12, 12 * max(1, len(centres)), 3))
    masks = []
    for index, centre in enumerate(centres):
        rows, cols = np.mgrid[:12, :12]
        world[:, index * 12:(index + 1) * 12] = np.stack(
            (centre[0] + cols * .0002, centre[1] + rows * .0002,
             centre[2] + rows * .0001), axis=-1)
        mask = np.zeros(world.shape[:2], dtype=bool)
        mask[:, index * 12:(index + 1) * 12] = True
        masks.append(mask)
    if not centres:
        world[:] = (0., 0., 1.)
    state = SimpleNamespace(latest_step=7, load_bytes=lambda _: b'RGB',
        load=lambda name: {'extrinsic_cam2world': np.eye(4)} if name.endswith('.json') else world)
    monkeypatch.setattr(Sam3Client, '_decode_result',
                        staticmethod(lambda item: SimpleNamespace(mask=item['mask'])))
    def segment(method, *, kwargs, **unused):
        return {'instances': [{'mask': mask, 'score': .9 - index * .1}
                              for index, mask in enumerate(masks)]}
    scene = MeasuredScene(SimpleNamespace(_state=state), SimpleNamespace(call=segment), 1,
                          dual_view_fusion_v1=False)
    placed = Entity('e1', 'butter', (-.2, -.2, .1), (-.23, -.23, .09), (-.17, -.17, .11),
                    source_step=2)
    target = Entity('e2', 'basket', (0., 0., .1), (-.1, -.1, .05), (.1, .1, .2),
                    visible=target_visible)
    scene.entities = {e.id: e for e in (placed, target)}
    for index in range(1, class_count):
        other = Entity(f'e{index + 2}', 'butter', (.4, .4, .1), (.37, .37, .09), (.43, .43, .11))
        scene.entities[other.id] = other
    if include_other:
        pan = Entity('e20', 'frypan', (.5, .5, .1), (.47, .47, .09), (.53, .53, .11))
        scene.entities[pan.id] = pan
    scene.instance_limits = {'butter': instance_limit}
    return scene, placed, target


@pytest.mark.parametrize('target_visible', [True, False])
@pytest.mark.parametrize('xy', [(0., 0.), (.3, .4)])
def test_unique_current_object_is_preserved_independently_of_target(monkeypatch, target_visible, xy):
    scene, placed, target = scene_with_measurements(monkeypatch, [(*xy, .12)],
                                                   target_visible=target_visible)
    scene.refresh(['butter'], placement=(placed, target))
    current = scene.entities[placed.id]
    assert current.visible and current.source_step == 7
    assert current.xyz[0] == pytest.approx(xy[0] + .0011)
    assert current.xyz[1] == pytest.approx(xy[1] + .0011)
    assert scene.entities[target.id] == target
    assert scene.measurement_views[placed.id]['wrist'].source_step == 7


@pytest.mark.parametrize('centres,class_count,instance_limit', [
    ([(0., 0., .12), (.4, .4, .12)], 1, 1),
    ([(0., 0., .12), (.05, .05, .12)], 1, 1),
    ([(0., 0., .12)], 2, 1),
    ([(0., 0., .12)], 1, 2),
    ([], 1, 1),
])
def test_ambiguous_or_missing_measurement_never_uses_goal_to_bind(
        monkeypatch, centres, class_count, instance_limit):
    scene, placed, target = scene_with_measurements(monkeypatch, centres,
        class_count=class_count, instance_limit=instance_limit)
    old_others = {key: value for key, value in scene.entities.items() if key != placed.id}
    scene.refresh(['butter'], placement=(placed, target))
    current = scene.entities[placed.id]
    assert not current.visible and current.source_step == 2
    assert current.xyz == placed.xyz
    assert scene.measurement_views[placed.id] == {}
    assert {key: value for key, value in scene.entities.items() if key != placed.id} == old_others


def test_supporting_query_keeps_its_normal_identity(monkeypatch):
    scene, placed, target = scene_with_measurements(monkeypatch, [(.5, .5, .12)], include_other=True)
    scene.refresh(['frypan'], placement=(placed, target))
    assert scene.entities['e20'].visible and scene.entities['e20'].source_step == 7
    assert set(scene.entities) == {placed.id, target.id, 'e20'}
    assert scene.entities[placed.id] == placed
