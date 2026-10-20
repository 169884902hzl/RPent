"""Measure saved blocker residuals to actual public robot mesh surfaces."""
import argparse
import json
from pathlib import Path
import sys

import numpy as np


def closest_surface(triangles,point):
    """Closest point on a triangle soup, including triangle-edge regions."""
    origin=triangles[:,0];u=triangles[:,1]-origin;v=triangles[:,2]-origin
    n=np.cross(u,v);n2=np.einsum('ij,ij->i',n,n)
    projection=point-n*(np.einsum('ij,ij->i',point-origin,n)/np.maximum(n2,1e-30))[:,None]
    w=projection-origin
    uu=np.einsum('ij,ij->i',u,u);uv=np.einsum('ij,ij->i',u,v);vv=np.einsum('ij,ij->i',v,v)
    wu=np.einsum('ij,ij->i',w,u);wv=np.einsum('ij,ij->i',w,v)
    determinant=uu*vv-uv*uv
    s=(wu*vv-wv*uv)/np.maximum(determinant,1e-30)
    t=(wv*uu-wu*uv)/np.maximum(determinant,1e-30)
    inside=(determinant>1e-24)&(s>=0)&(t>=0)&(s+t<=1)
    best=projection.copy();dist=np.where(inside,np.linalg.norm(projection-point,axis=1),np.inf)
    for i,j in ((0,1),(1,2),(2,0)):
        a=triangles[:,i];edge=triangles[:,j]-a
        scalar=np.clip(np.einsum('ij,ij->i',point-a,edge)/np.maximum(np.einsum('ij,ij->i',edge,edge),1e-30),0,1)
        candidate=a+edge*scalar[:,None];value=np.linalg.norm(candidate-point,axis=1)
        keep=value<dist;dist[keep]=value[keep];best[keep]=candidate[keep]
    index=int(dist.argmin())
    return float(dist[index]),best[index],index


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source',type=Path,required=True)
    p.add_argument('--panel',type=Path,required=True)
    p.add_argument('--audit',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();sys.path.insert(0,str(a.source))
    import robosuite
    from robots.libero.bounded_robot_depth import current_robot_triangles
    from robots.libero.v5_grasp_kinematics import PublicPoseScreen
    from robots.libero.v5_geometric_grasp import panda_geometry
    # Analytic face/edge/outside checks for this CPU diagnostic's distance.
    face=np.array([[[0.,0.,0.],[1.,0.,0.],[0.,1.,0.]]])
    assert abs(closest_surface(face,np.array([.2,.2,.1]))[0]-.1)<1e-12
    assert abs(closest_surface(face,np.array([1.,1.,0.]))[0]-np.sqrt(.5))<1e-12
    xml=Path(robosuite.__file__).parent/'models/assets/grippers/panda_gripper.xml'
    geometry=panda_geometry(xml);records=[]
    for audit in json.loads(a.audit.read_bytes())['rows']:
        loop=json.loads((a.panel/audit['case']/'loops.jsonl').open().readline())
        detail=next(d for d in loop['execution_details'] if d.get('candidate_id')==audit['candidate_id'])
        screen=detail['execution']['screen'];points=[]
        for key in ('public_scene_collision_points','public_target_collision_points'):
            points.extend(xyz for group in screen.get(key,{}).values() for xyz in group)
        arm=screen.get('arm_screen',{}).get('obstacle_point')
        if arm is not None:points.append(arm)
        robot=audit['public_robot']
        ik=PublicPoseScreen(xml.parent.parent/'robots/panda/robot.xml',robot['joint_positions_rad'],
            robot['eef_xyz_m'],robot['eef_quat_xyzw'],geometry['site_offset_in_gripper_m'])
        faces=current_robot_triangles(ik,robot,xml)
        samples=[]
        for point in points:
            distance,nearest,face=closest_surface(faces,np.asarray(point))
            samples.append({'point':point,'nearest_robot_surface_m':distance,'nearest_point':nearest.tolist(),
                'triangle_index':face,'triangle':faces[face].tolist()})
        records.append({'case':audit['case'],'skill':audit['skill'],'capture_step':audit['capture_step'],'samples':samples})
    with a.output.open('x') as f:json.dump({'records':records,'physics_steps':0,'rpc_calls':0,
        'private_object_coordinates_used':False,'scope':'public mesh distance; not independent collision truth'},f,indent=2)
    print(json.dumps({'output':str(a.output),'samples':sum(len(r['samples']) for r in records)}))


if __name__=='__main__':main()
