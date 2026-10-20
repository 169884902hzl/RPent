"""Render current robot depth from public joints, camera calibration and meshes."""
from functools import lru_cache
from pathlib import Path
import xml.etree.ElementTree as ET

import numpy as np
from numba import njit
from scipy.spatial import ConvexHull
from scipy.spatial.transform import Rotation

from robots.libero.v5_geometric_grasp import _rotation, _vector, stl_vertices


def _vertices(path):
    if path.suffix.lower()=='.obj':
        return np.array([line.split()[1:4] for line in path.read_text().splitlines()
                         if line.startswith('v ')],dtype=float)
    return stl_vertices(path)


@lru_cache(maxsize=4)
def _arm_triangles(xml_path):
    path = Path(xml_path)
    root = ET.parse(path).getroot()
    meshes = {m.get('name'):m for m in root.findall('asset/mesh')}
    node,body,result = 0,root.find('worldbody/body'),[]
    while body is not None:
        for geom in body.findall('geom'):
            if geom.get('group')!='1' or geom.get('type')!='mesh':
                continue
            mesh = meshes[geom.get('mesh')]
            vertices = _vertices(path.parent/mesh.get('file'))*_vector(mesh,'scale','1 1 1')
            vertices = vertices@_rotation(geom).T+_vector(geom,'pos','0 0 0')
            result.append((node,vertices[ConvexHull(vertices).simplices]))
        if body.get('name')=='right_hand':
            break
        node,body = node+1,body.find('body')
    return result


@lru_cache(maxsize=4)
def _hand_triangles(xml_path):
    path = Path(xml_path)
    root = ET.parse(path).getroot()
    meshes = {m.get('name'):path.parent/m.get('file') for m in root.findall('asset/mesh')}
    hand = root.find(".//body[@name='right_gripper']")
    eef = hand.find("body[@name='eef']")
    offset = _vector(eef,'pos','0 0 0')+_vector(eef.find("site[@name='grip_site']"),'pos','0 0 0')
    result = []
    for body,finger,sign in [(hand,-1,0),(hand.find("body[@name='leftfinger']"),0,1),
                             (hand.find("body[@name='rightfinger']"),1,-1)]:
        turn = _rotation(body) if sign else np.eye(3)
        position = _vector(body,'pos','0 0 0') if sign else np.zeros(3)
        slide = turn@_vector(body.find('joint'),'axis','0 1 0')*sign if sign else np.zeros(3)
        for geom in body.findall('geom'):
            if geom.get('group')!='1' or geom.get('type')!='mesh':
                continue
            vertices = _vertices(meshes[geom.get('mesh')])
            vertices = (vertices@_rotation(geom).T+_vector(geom,'pos','0 0 0'))@turn.T+position-offset
            result.append((finger,slide,vertices[ConvexHull(vertices).simplices]))
    return result


def current_robot_triangles(pose_screen,robot,gripper_xml):
    """Static convex visual shells in the same public FK world as the screen."""
    transforms,pose,joint = [],np.eye(4),0
    for fixed,axis in pose_screen.nodes:
        pose = pose@fixed
        if axis is not None:
            turn = np.eye(4)
            turn[:3,:3] = Rotation.from_rotvec(axis*pose_screen.joints[joint]).as_matrix()
            pose = pose@turn
            joint += 1
        transforms.append(pose.copy())
    triangles = []
    for node,mesh in _arm_triangles(pose_screen.reference['path']):
        pose = transforms[node]
        base = mesh@pose[:3,:3].T+pose[:3,3]
        triangles.append(base@pose_screen.world_rotation.T+pose_screen.world_offset)
    site = Rotation.from_quat(robot['eef_quat_xyzw']).as_matrix()@Rotation.from_euler('z',-np.pi/2).as_matrix()
    fingers = np.abs(robot['finger_positions_m'])
    for finger,slide,mesh in _hand_triangles(str(gripper_xml)):
        local = mesh+(slide*fingers[finger] if finger>=0 else 0.)
        triangles.append(local@site.T+robot['eef_xyz_m'])
    return np.concatenate(triangles)


@njit(cache=True)
def raster_depth(triangles,k,height,width):
    """Perspective-correct triangle depth; pixel centres match RGB-D maps."""
    depth = np.full((height,width),np.inf)
    for face in triangles:
        if np.min(face[:,2]) <= 1e-5:
            continue
        x = k[0,0]*face[:,0]/face[:,2]+k[0,2]
        y = k[1,1]*face[:,1]/face[:,2]+k[1,2]
        left,right = max(0,int(np.ceil(np.min(x)))),min(width-1,int(np.floor(np.max(x))))
        top,bottom = max(0,int(np.ceil(np.min(y)))),min(height-1,int(np.floor(np.max(y))))
        area = (y[1]-y[2])*(x[0]-x[2])+(x[2]-x[1])*(y[0]-y[2])
        if abs(area)<1e-12:
            continue
        for row in range(top,bottom+1):
            for col in range(left,right+1):
                a = ((y[1]-y[2])*(col-x[2])+(x[2]-x[1])*(row-y[2]))/area
                b = ((y[2]-y[0])*(col-x[2])+(x[0]-x[2])*(row-y[2]))/area
                c = 1.-a-b
                if min(a,b,c)>=-1e-10:
                    value = 1./(a/face[0,2]+b/face[1,2]+c/face[2,2])
                    depth[row,col] = min(depth[row,col],value)
    return depth


def rendered_robot_mask(world,metadata,triangles,*,margin_m=.012):
    """Remove only pixels agreeing with current rendered robot depth."""
    height,width = world.shape[:2]
    extrinsic = np.asarray(metadata['extrinsic_cam2world'])
    k = np.array(metadata['intrinsic_K'],dtype=float,copy=True)
    k[0] *= width/metadata.get('width',256)
    k[1] *= height/metadata.get('height',256)
    camera = (triangles-extrinsic[:3,3])@extrinsic[:3,:3]
    depth = raster_depth(camera,k,height,width)
    measured = (np.asarray(world)-extrinsic[:3,3])@extrinsic[:3,:3]
    mask = np.isfinite(depth)&np.isfinite(measured).all(axis=-1)&(np.abs(measured[...,2]-depth)<=margin_m)
    return mask,{'source':'static_visual_convex_meshes_public_joint_sensors_and_camera_calibration',
        'method':'rendered_robot_depth','margin_m':margin_m,'triangles':len(triangles),
        'removed_points':int(mask.sum()),'private_pose_used':False}
