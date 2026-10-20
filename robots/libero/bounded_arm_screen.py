"""Selected-route arm checks using public joints/static meshes/observed points."""
import math

import numpy as np
from scipy.spatial import cKDTree

from robots.libero.bounded_kernels.ik import BatchedDampedIK
from robots.libero.bounded_kernels.route import link_distance_query
from robots.libero.bounded_kernel_integration import capture_fields
from robots.libero.v5_grasp_kinematics import robot_link_hulls


def screen_arm_route(screen,checks):
    """Certify newly swept observed-point intrusion, not unseen/self collision."""
    ik = screen.ik
    kernel = BatchedDampedIK.from_source(ik)
    hulls = robot_link_hulls(ik.reference['path'])
    points = np.concatenate((screen.points,screen.target))
    tree = cKDTree(points)
    q0 = np.asarray(ik.joints)
    joint_route = [q0]
    for check in checks:
        joint_route.append(np.asarray(next(s['joint_positions_rad'] for s in check['solves'] if s['solution_found'])))
    reach = sum(np.linalg.norm(t[:3,3]) for t,_ in ik.nodes)+max(
        np.linalg.norm(np.maximum(np.abs(h['lower']),np.abs(h['upper']))) for h in hulls)
    samples = [q0]
    for first,last in zip(joint_route[:-1],joint_route[1:]):
        # Every link-surface point moves <=reach*L1(dq). A 2 mm bound is
        # finer than the unchanged 4 mm observed-cloud collision margin.
        n = max(1,math.ceil(reach*np.abs(last-first).sum()/.002))
        samples.extend(np.linspace(first,last,n+1)[1:])
    joints = np.asarray(samples)
    field_points = screen.capture_points if screen.capture_points is not None else points
    field = capture_fields(field_points,screen.capture_key).get(points)
    broad = link_distance_query(field,kernel,joints,hulls)
    covers = field.covers(points) and screen.contact_axis is None
    eef,_,_,poses = kernel.forward(joints,links=True)
    baselines,cache = {},{}
    exact_count,fast_count = 0,0
    for index in range(len(joints)):
        shift = np.zeros(3)
        if screen.contact_axis is not None:
            shift[screen.contact_axis] = eef[index,screen.contact_axis]-screen.contact_origin[screen.contact_axis]
        for h_index,hull in enumerate(hulls):
            transform = poses[hull['node']][index]
            signature = h_index,*transform.reshape(-1),*shift
            if signature in cache:
                continue
            if index and covers and broad['per_link'][h_index]['strictly_clear_of_observed_cloud'][index]:
                fast_count += 1
                cache[signature] = True
                continue
            centre = (hull['lower']+hull['upper'])/2
            centre = transform[:3,:3]@centre+transform[:3,3]
            radius = np.linalg.norm(hull['upper']-hull['lower'])/2+.008
            # A translated contact set cannot use the static tree query.
            if screen.contact_axis is not None:
                cloud = np.concatenate((screen.points,screen.target+shift))
                ids = np.flatnonzero(np.linalg.norm(cloud-centre,axis=1)<=radius)
            else:
                cloud = points
                ids = np.asarray(tree.query_ball_point(centre,radius),dtype=int)
            local = (cloud[ids]-transform[:3,3])@transform[:3,:3]
            near = ((local>=hull['lower']-.004)&(local<=hull['upper']+.004)).all(axis=1)
            ids,local = ids[near],local[near]
            equations = hull['equations']
            distances = np.empty(len(local))
            for batch in np.array_split(np.arange(len(local)),max(1,(len(local)+255)//256)):
                distances[batch] = (local[batch]@equations[:,:3].T+equations[:,3]).max(axis=1)
            exact_count += 1
            if index==0:
                baselines[h_index] = {int(i):float(d) for i,d in zip(ids,distances) if d<=.004}
            baseline = baselines.get(h_index,{})
            blocked = np.array([d<=.004 and (int(i) not in baseline or d<baseline[int(i)]-1e-9)
                for i,d in zip(ids,distances)],dtype=bool)
            if blocked.any():
                hit = int(np.flatnonzero(blocked)[0])
                return {'passed':False,'arm_collisions_checked':True,'reason':'measured_arm_sweep_collision',
                    'link':hull['name'],'joint_sample':index,'joint_positions_rad':joints[index].tolist(),
                    'obstacle_point':cloud[ids[hit]].tolist(),'margin_m':.004,
                    'max_link_sample_motion_m':.002,'link_exact_checks':exact_count,
                    'link_voxel_fast_clear':fast_count,'self_collisions_checked':False,
                    'scope':'public_observed_points_and_static_link_meshes;unseen_space_not_certified'}
            cache[signature] = True
    return {'passed':True,'arm_collisions_checked':True,'joint_samples':len(joints),
        'link_exact_checks':exact_count,'link_voxel_fast_clear':fast_count,'margin_m':.004,
        'max_link_sample_motion_m':.002,'self_collisions_checked':False,
        'scope':'public_observed_points_and_static_link_meshes;unseen_space_not_certified'}
