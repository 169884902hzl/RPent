"""Public camera projection removes only the rendered robot surface."""
import numpy as np

from robots.libero.bounded_robot_depth import raster_depth,rendered_robot_mask


def test_perspective_depth_raster_keeps_foreground_objects_and_other_pixels():
    face = np.array([[[-1.,-1.,1.],[1.,-1.,1.],[0.,1.,1.]]])
    k = np.array([[2.,0.,2.],[0.,2.,2.],[0.,0.,1.]])
    depth = raster_depth(face,k,5,5)
    assert depth[2,2] == 1. and not np.isfinite(depth[4,4])
    row,col = np.mgrid[:5,:5]
    world = np.stack([(col-2)/2,(row-2)/2,np.ones((5,5))],axis=-1)
    metadata = dict(extrinsic_cam2world=np.eye(4).tolist(),intrinsic_K=k.tolist(),width=5,height=5)
    mask,evidence = rendered_robot_mask(world,metadata,face)
    assert mask[2,2] and evidence['private_pose_used'] is False
    world[2,2] *= .7
    mask,_ = rendered_robot_mask(world,metadata,face)
    assert not mask[2,2]
