"""Public camera projection removes only the rendered robot surface."""
import numpy as np

from robots.libero.bounded_robot_depth import _arm_triangles,raster_depth,rendered_robot_mask


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


def test_visual_recess_uses_original_faces_and_retains_foreground(tmp_path):
    vertices=[[-1.,-1.,1.],[0.,-1.,1.],[-.5,1.,1.],
        [0.,-1.,1.],[1.,-1.,1.],[.5,1.,1.],
        [-1.,-1.,1.06],[1.,-1.,1.06],[0.,1.,1.06]]
    (tmp_path/'recess.obj').write_text(''.join('v '+' '.join(map(str,v))+'\n' for v in vertices)+
        'f 1 2 3\nf 4 5 6\nf 7 8 9\n')
    xml=tmp_path/'robot.xml'
    xml.write_text('<mujoco><asset><mesh name="shell" file="recess.obj"/></asset>'
        '<worldbody><body name="right_hand"><geom group="1" type="mesh" mesh="shell"/>'
        '</body></worldbody></mujoco>')
    [(node,faces)]=_arm_triangles(str(xml))
    assert node==0
    k=np.array([[2.,0.,2.],[0.,2.,2.],[0.,0.,1.]])
    assert raster_depth(faces,k,5,5)[2,2]==1.06
    row,col=np.mgrid[:5,:5]
    world=np.stack([(col-2)*1.06/2,(row-2)*1.06/2,np.full((5,5),1.06)],axis=-1)
    metadata=dict(extrinsic_cam2world=np.eye(4).tolist(),intrinsic_K=k.tolist(),width=5,height=5)
    assert rendered_robot_mask(world,metadata,faces)[0][2,2]
    world[2,2]=[0.,0.,.95]
    assert not rendered_robot_mask(world,metadata,faces)[0][2,2]


def test_libero_depth_sampling_uses_pixel_centres_without_changing_calibration():
    faces=np.array([[[.1,.1,1.],[.9,.1,1.],[.5,.9,1.]]])
    k=np.array([[1.,0.,2.],[0.,1.,2.],[0.,0.,1.]])
    row,col=np.mgrid[:5,:5]
    world=np.stack([col-2,row-2,np.ones((5,5))],axis=-1)
    metadata=dict(extrinsic_cam2world=np.eye(4).tolist(),intrinsic_K=k.tolist(),width=5,height=5)
    mask,evidence=rendered_robot_mask(world,metadata,faces)
    assert mask[2,2] and evidence['pixel_sample_offset_xy']==[.5,.5]
    assert metadata['intrinsic_K']==k.tolist()
    world[2,2]=[0.,0.,.8]
    assert not rendered_robot_mask(world,metadata,faces)[0][2,2]
