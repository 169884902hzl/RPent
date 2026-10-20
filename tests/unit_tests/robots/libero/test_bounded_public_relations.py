"""Cached peers cannot introduce relationships outside the advertised anchors."""
from dataclasses import replace

from tests.unit_tests.robots.libero.test_bounded_skills import adapter  # noqa: F401


def test_held_scene_drops_relations_to_an_unadvertised_cached_peer(adapter):
    source = adapter.scene.entities['e1']
    peer = replace(source, id='occluded', xyz=(.11,.1,.9), visible=True)
    adapter.scene.entities['occluded'] = replace(peer,visible=False)
    adapter.target_cache['occluded'] = peer
    adapter.held = 'e1'
    request = adapter.request(k=1)
    assert {a['id'] for a in request['anchors']} == {'e1'}
    assert not request['relations']
