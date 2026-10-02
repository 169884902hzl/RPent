"""Measured view association must not merge distinct same-category objects."""

import numpy as np

from robots.libero.v5_perception_geometry import fit_shape, fuse_cloud


def cloud(x=0):
    return np.array([(x+a,b,.9+c) for a in np.linspace(-.02,.02,6)
                     for b in np.linspace(-.02,.02,6) for c in (0,.03)])


def test_dual_view_combines_compatible_surfaces_without_overwriting_one_view():
    a, b = cloud(), cloud(.025)
    joined, index, evidence = fuse_cloud(a, [(b,.9)])
    assert index == 0 and evidence["fused"]
    assert joined[:,0].min() == a[:,0].min()
    assert joined[:,0].max() == b[:,0].max()


def test_ambiguous_view_binding_does_not_fuse_either_instance():
    a = cloud()
    joined, index, evidence = fuse_cloud(a, [(cloud(.01),.9),(cloud(-.01),.8)])
    assert index is None and not evidence["fused"]
    assert np.array_equal(joined,a)


def test_cylinder_fit_recovers_centre_from_a_visible_side_without_unseen_height():
    angles = np.linspace(-1.2,1.2,80)
    points = np.array([(.1+.035*np.cos(a),-.2+.035*np.sin(a),z)
                       for a in angles for z in (.9,.94,.98)])
    centre, lower, upper, evidence = fit_shape(points,"wine bottle")
    assert evidence["accepted"]
    assert np.allclose(centre[:2],(.1,-.2),atol=.001)
    assert lower[2] == .9 and upper[2] == .98


def test_one_flat_box_face_does_not_invent_hidden_thickness():
    points = np.array([(x,.1,z) for x in np.linspace(0,.04,10)
                       for z in np.linspace(.9,.94,10)])
    _,lower,upper,evidence=fit_shape(points,"cream cheese")
    assert not evidence["accepted"]
    assert lower[1] == upper[1] == .1


def test_scene_estimates_one_instance_from_both_calibrated_world_clouds(monkeypatch):
    from types import SimpleNamespace
    from robots.libero.v5_runtime import MeasuredScene
    from rpent.robots.components.sam3_client import Sam3Client
    primary=cloud().reshape(12,6,3)
    second=cloud(.025).reshape(12,6,3)
    state=SimpleNamespace(latest_step=3,load_bytes=lambda n:n.encode(),
        load=lambda n: {"extrinsic_cam2world":np.eye(4)} if n.endswith('.json') else
        second if n.startswith('wrist') else primary)
    monkeypatch.setattr(Sam3Client,'_decode_result',staticmethod(lambda item:SimpleNamespace(mask=np.ones((12,6),dtype=bool))))
    rpc=SimpleNamespace(call=lambda *a,**kw:{"instances":[{"score":.9}]})
    scene=MeasuredScene(SimpleNamespace(_state=state),rpc,1,dual_view_fusion_v1=True)
    scene.refresh(['cream cheese'])
    assert len(scene.entities)==1
    e=next(iter(scene.entities.values()))
    assert e.lower[0] < -.015 and e.upper[0] > .04
    assert scene.perception_evidence[e.id]['source_cameras']==['agentview','wrist']
    assert len(scene.measurement_clouds[e.id]) > len(primary.reshape(-1,3))
