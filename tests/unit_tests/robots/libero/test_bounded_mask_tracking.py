"""Public frame tracking declines occlusion/missing depth without stale masks."""
import numpy as np
import pytest

from robots.libero.bounded_mask_tracking import track_mask


def frames():
    rng=np.random.default_rng(63)
    image=rng.integers(0,256,(128,128,3),dtype=np.uint8)
    y,x=np.mgrid[:128,:128]
    world=np.stack([x*.001,y*.001,np.ones_like(x)],axis=-1)
    mask=(x>=30)&(x<95)&(y>=30)&(y<95)
    return image,world,mask


def test_static_current_frame_is_tracked_from_public_inputs():
    image,world,mask=frames()
    current,evidence=track_mask(image,image,world,world,mask)
    assert evidence['accepted'] and not evidence['requires_segmentation']
    assert evidence['private_pose_used'] is False
    np.testing.assert_array_equal(current,mask)


def test_image_and_depth_translation_are_measured_together():
    import cv2
    image,world,mask=frames()
    image=cv2.GaussianBlur(image,(5,5),0)
    affine=np.array([[1.,0.,5.],[0.,1.,3.]])
    shifted=cv2.warpAffine(image,affine,(128,128))
    current,evidence=track_mask(image,shifted,world,world,mask)
    expected=cv2.warpAffine(mask.astype(np.uint8),affine,(128,128))>0
    assert evidence['accepted']
    np.testing.assert_allclose(evidence['translation_m'],[.005,.003,0.],atol=.001)
    assert (current&expected).sum()/(current|expected).sum() > .95


def test_lost_texture_or_occlusion_requests_full_segmentation():
    image,world,mask=frames()
    for previous,current in ((np.zeros_like(image),np.zeros_like(image)),(image,np.zeros_like(image))):
        result,evidence=track_mask(previous,current,world,world,mask)
        assert result is None and evidence['requires_segmentation'] and not evidence['accepted']


def test_new_depth_cannot_reuse_stale_rgb_identity():
    image,world,mask=frames()
    changed=world.copy()
    changed[mask]=np.nan
    result,evidence=track_mask(image,image,world,changed,mask)
    assert result is None and evidence['requires_segmentation']


def test_mismatched_capture_shapes_are_rejected():
    image,world,mask=frames()
    with pytest.raises(ValueError,match='shapes'):
        track_mask(image,image[:1],world,world,mask)


def query_fixture():
    import base64
    import io
    from types import SimpleNamespace

    import cv2
    import imageio.v3 as iio

    from robots.libero.bounded_mask_tracking import TrackedSegmentation

    image,world,mask=frames()
    image=cv2.GaussianBlur(image,(5,5),0)
    def encode(array):
        buffer=io.BytesIO()
        iio.imwrite(buffer,array,extension='.png')
        return buffer.getvalue()
    owner=SimpleNamespace(rgbd_mask_tracking_v1=True)
    state=SimpleNamespace(latest_step=0,image=image,world=world)
    state.load_bytes=lambda name:encode(state.image) if name.startswith('agentview') else encode(np.zeros_like(image))
    state.load=lambda _:state.world
    calls=[]
    def call(method,**kwargs):
        calls.append((method,kwargs))
        return {'instances':[{'found':True,'score':.9,'box':[30.,30.,95.,95.],
            'mask_shape':list(mask.shape),'mask_png_base64':base64.b64encode(encode(mask.astype(np.uint8)*255)).decode()}]}
    proxy=TrackedSegmentation(SimpleNamespace(call=call),state,owner)
    def request():
        return proxy.call('sam3.segment_all',kwargs={'image_base64':base64.b64encode(state.load_bytes('agentview_high.png')).decode(),
            'text_prompt':'measured object','min_score':.5})
    return proxy,owner,state,calls,request


def test_query_proxy_uses_exact_images_then_tracks_and_recalls_on_occlusion():
    import cv2
    proxy,owner,state,calls,request=query_fixture()
    full=request()
    assert request()==full and len(calls)==1
    state.latest_step+=1
    state.image=cv2.warpAffine(state.image,np.array([[1.,0.,2.],[0.,1.,1.]]),(128,128))
    tracked=request()
    assert len(calls)==1 and proxy.tracked_queries==1
    assert tracked['instances'][0]['guidance']['source']=='current_rgbd_mask_tracking'
    state.latest_step+=1
    state.image[:]=0
    request()
    assert len(calls)==2 and proxy.full_queries==2


def test_query_history_follows_scene_snapshot_restore_instead_of_sibling_branch():
    import copy
    proxy,owner,state,calls,request=query_fixture()
    request()
    saved=copy.deepcopy(owner._mask_tracking_history)
    owner._mask_tracking_history={'entries':{},'frames':{}}
    request()
    assert len(calls)==2
    owner._mask_tracking_history=copy.deepcopy(saved)
    request()
    assert len(calls)==2
    owner.rgbd_mask_tracking_v1=False
    request()
    assert len(calls)==3  # An old snapshot's disabled mode uses its original RPC.
