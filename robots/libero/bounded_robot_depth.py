"""Render current robot depth from public joints, camera calibration and meshes."""
from functools import lru_cache
from pathlib import Path
import xml.etree.ElementTree as ET

import numpy as np
from numba import njit
from scipy.spatial.transform import Rotation

from robots.libero.v5_geometric_grasp import _rotation, _vector, stl_vertices


def _mesh_triangles(path):
    if path.suffix.lower()=='.obj':
        vertices,faces=[],[]
        for line in path.read_text().splitlines():
            fields=line.split()
            if not fields:continue
            if fields[0]=='v':vertices.append([float(x) for x in fields[1:4]])
            elif fields[0]=='f':
                indices=[int(item.split('/')[0]) for item in fields[1:]]
                ids=[i-1 if i>0 else len(vertices)+i for i in indices]
                faces.extend((ids[0],ids[i],ids[i+1]) for i in range(1,len(ids)-1))
        return np.asarray(vertices)[np.asarray(faces,dtype=int)]
    return stl_vertices(path).reshape(-1,3,3)


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
            triangles = _mesh_triangles(path.parent/mesh.get('file'))*_vector(mesh,'scale','1 1 1')
            triangles = triangles@_rotation(geom).T+_vector(geom,'pos','0 0 0')
            result.append((node,triangles))
        if body.get('name')=='right_hand':
            break
        node,body = node+1,body.find('body')
    return result


@lru_cache(maxsize=4)
def _hand_triangles(xml_path):
    path = Path(xml_path)
    root = ET.parse(path).getroot()
    meshes = {m.get('name'):m for m in root.findall('asset/mesh')}
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
            mesh=meshes[geom.get('mesh')]
            triangles = _mesh_triangles(path.parent/mesh.get('file'))*_vector(mesh,'scale','1 1 1')
            triangles = (triangles@_rotation(geom).T+_vector(geom,'pos','0 0 0'))@turn.T+position-offset
            result.append((finger,slide,triangles))
    return result


def current_robot_triangles(pose_screen,robot,gripper_xml):
    """Actual visual faces in the same public FK world as the screen.

    Convex hull faces bridge visual recesses and render depth ahead of the
    true surface. Their depth must not be used as a robot segmentation mask.
    """
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
def _face_distance_squared(point,face):
    a,b,c=face
    u,v,w=b-a,c-a,point-a
    uu,uv,vv=np.dot(u,u),np.dot(u,v),np.dot(v,v)
    determinant=uu*vv-uv*uv
    if determinant>1e-24:
        wu,wv=np.dot(w,u),np.dot(w,v)
        s=(wu*vv-wv*uv)/determinant
        t=(wv*uu-wu*uv)/determinant
        if s>=0 and t>=0 and s+t<=1:
            offset=w-s*u-t*v
            return np.dot(offset,offset)
    distance=np.inf
    for left,right in ((a,b),(b,c),(c,a)):
        edge=right-left
        fraction=min(1.,max(0.,np.dot(point-left,edge)/max(np.dot(edge,edge),1e-30)))
        offset=point-left-fraction*edge
        distance=min(distance,np.dot(offset,offset))
    return distance


@njit(cache=True)
def _raster_surfaces(triangles,k,height,width,observed_camera,margin_m):
    depth = np.full((height,width),np.inf)
    matches = np.zeros((height,width),np.bool_)
    for face in triangles:
        if np.min(face[:,2]) <= 1e-5:
            continue
        x = k[0,0]*face[:,0]/face[:,2]+k[0,2]
        y = k[1,1]*face[:,1]/face[:,2]+k[1,2]
        left,right = max(0,int(np.ceil(np.min(x)-1.))),min(width-1,int(np.floor(np.max(x)+1.)))
        top,bottom = max(0,int(np.ceil(np.min(y)-1.))),min(height-1,int(np.floor(np.max(y)+1.)))
        area = (y[1]-y[2])*(x[0]-x[2])+(x[2]-x[1])*(y[0]-y[2])
        if abs(area)<1e-12:
            continue
        da=(abs(y[1]-y[2])+abs(x[2]-x[1]))/abs(area)
        db=(abs(y[2]-y[0])+abs(x[0]-x[2]))/abs(area)
        dc=(abs(y[0]-y[1])+abs(x[1]-x[0]))/abs(area)
        for row in range(top,bottom+1):
            for col in range(left,right+1):
                a = ((y[1]-y[2])*(col-x[2])+(x[2]-x[1])*(row-y[2]))/area
                b = ((y[2]-y[0])*(col-x[2])+(x[0]-x[2])*(row-y[2]))/area
                c = 1.-a-b
                if min(a,b,c)>=-1e-10:
                    value = 1./(a/face[0,2]+b/face[1,2]+c/face[2,2])
                    depth[row,col] = min(depth[row,col],value)
                    if abs(observed_camera[row,col,2]-value)<=margin_m:
                        matches[row,col] = True
                elif (a+da>=0 and b+db>=0 and c+dc>=0
                        and not matches[row,col] and np.isfinite(observed_camera[row,col]).all()
                        and _face_distance_squared(observed_camera[row,col],face)<=margin_m**2):
                    # Cover the one-pixel fringe between integer RGB-D
                    # backprojection and GPU pixel-centre edge coverage.
                    # A fringe pixel must still lie within the unchanged
                    # 3-D band of an ACTUAL face, never a filled depth gap.
                    matches[row,col] = True
    return depth,matches


def raster_depth(triangles,k,height,width):
    """Perspective-correct nearest depth on the caller's pixel grid."""
    return _raster_surfaces(triangles,k,height,width,np.full((height,width,3),np.nan),0.)[0]


def rendered_robot_mask(world,metadata,triangles,*,margin_m=.012):
    """Remove only pixels agreeing with current rendered robot depth."""
    height,width = world.shape[:2]
    extrinsic = np.asarray(metadata['extrinsic_cam2world'])
    k = np.array(metadata['intrinsic_K'],dtype=float,copy=True)
    k[0] *= width/metadata.get('width',256)
    k[1] *= height/metadata.get('height',256)
    # MuJoCo/OpenGL samples depth at pixel centres. Saved RGB-D backprojection
    # uses integer array indices, so render at (col+.5,row+.5) in that grid.
    # This changes sampling, not the camera's measured calibration.
    k[0,2] -= .5
    k[1,2] -= .5
    camera = (triangles-extrinsic[:3,3])@extrinsic[:3,:3]
    measured = (np.asarray(world)-extrinsic[:3,3])@extrinsic[:3,:3]
    # At a projected mesh edge, CPU and GPU coverage can select different
    # front fragments. Match a measured sample to any finite robot face at
    # that pixel; do not fill the depth interval between separate surfaces.
    _,mask = _raster_surfaces(camera,k,height,width,measured,margin_m)
    mask &= np.isfinite(measured).all(axis=-1)
    return mask,{'source':'static_visual_mesh_triangles_public_joint_sensors_and_camera_calibration',
        'method':'rendered_robot_depth','surface_layers':'all_finite_visual_faces',
        'edge_guard_px':1.,'edge_guard_requires_actual_3d_surface_agreement':True,
        'pixel_sample_offset_xy':[.5,.5],
        'margin_m':margin_m,'triangles':len(triangles),
        'removed_points':int(mask.sum()),'private_pose_used':False}
