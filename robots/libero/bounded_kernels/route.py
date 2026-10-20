"""Optional wrappers for source exact geometry and public link distances.

Only a strictly clear sphere cover can bypass exact checks. Contact motion,
unknown voxels and near obstacles always use the unchanged source callback.
"""
from collections import Counter
import hashlib
import time

import numpy as np
from scipy.spatial.transform import Rotation

from .voxel import VoxelDistanceField, SphereCover, cover_boxes, cover_points, sphere_clearance


class CaptureFields:
    """One reusable field per immutable observed cloud, discarded at refresh."""
    def __init__(self, **config):
        self.config=config;self.fields={}

    def prepare_capture(self, clouds, *, lazy=False):
        self.capture_cloud=np.concatenate(clouds)
        self.fields={}
        if hasattr(self,'universal_field'):del self.universal_field
        if lazy:return None
        self.universal_field=VoxelDistanceField(self.capture_cloud,**self.config)
        self.fields={'capture_union':self.universal_field}
        return self.universal_field

    def get(self, cloud):
        if hasattr(self,'universal_field'):return self.universal_field
        if hasattr(self,'capture_cloud'):
            self.universal_field=VoxelDistanceField(self.capture_cloud,**self.config)
            self.fields={'capture_union':self.universal_field}
            return self.universal_field
        cloud=np.ascontiguousarray(cloud,dtype=np.float64).reshape(-1,3)
        key=hashlib.sha256(cloud.tobytes()).hexdigest()
        if key not in self.fields:self.fields[key]=VoxelDistanceField(cloud,**self.config)
        return self.fields[key]


class ConservativeGeometry:
    def __init__(self, source_screen, *, capture_fields=None, voxel_m=.004):
        self.screen=source_screen
        self.exact=source_screen._geometry_at
        capture_fields=capture_fields if capture_fields is not None else CaptureFields(voxel_m=voxel_m)
        cloud=np.concatenate((source_screen.points,source_screen.target))
        self.field=capture_fields.get(cloud)
        self.obstacles_covered=self.field.covers(cloud)
        self.hand=cover_boxes(source_screen.geometry['boxes'],opening=source_screen.opening)
        self.payload=cover_points(source_screen.payload)
        self.stats=Counter()

    def broadphase(self, poses):
        started=time.perf_counter()
        if not poses:return np.empty(0,bool),np.empty(0)
        positions=np.asarray([p['xyz_m'] for p in poses])
        rotation=Rotation.from_quat([p['quat_xyzw'] for p in poses]).as_matrix()
        # Source hand clearance is an L_inf box expansion. sqrt(3)*4 mm
        # covers its corners as well as the contained convex-shell margin.
        site=rotation@Rotation.from_euler('z',-np.pi/2).as_matrix()
        safe,lower=sphere_clearance(self.field,positions,site,self.hand,
                                   approximation_error_m=(np.sqrt(3)-1)*.004)
        if len(self.payload.centers):
            p_safe,p_lower=sphere_clearance(self.field,positions,rotation,self.payload)
            safe&=p_safe;lower=np.minimum(lower,p_lower)
        # A translating target uses a pose-dependent obstacle set. A static
        # capture field cannot certify it; retain all source contact checks.
        if getattr(self.screen,'contact_axis',None) is not None or not self.obstacles_covered:safe[:]=False
        self.stats['broadphase_ns']+=int((time.perf_counter()-started)*1e9)
        return safe,lower

    def prepare(self, poses):
        safe,lower=self.broadphase(poses)
        self.prepared={(*p['xyz_m'],*p['quat_xyzw']):(bool(s),float(d)) for p,s,d in zip(poses,safe,lower)}

    def check_batch(self, poses):
        safe,lower=self.broadphase(poses)
        return [self._result(pose,bool(safe[i]),float(lower[i])) for i,pose in enumerate(poses)]

    def _result(self, pose, safe, lower):

        if safe and self.screen.tree is not None:
            result=self._clearance_result(pose,lower)
            self.stats['fast_accept']+=1
            signature=(*pose['xyz_m'],*pose['quat_xyzw'])
            self.screen._pose_geometry_cache[signature]=result
        else:
            t=time.perf_counter();result=self.exact(pose)
            self.stats['exact_ns']+=int((time.perf_counter()-t)*1e9)
            self.stats['exact_fallback']+=1
        return result

    def _clearance_result(self, pose, lower):
        # A proof of pass must not silently change the public numeric
        # clearance consumed by subsequent route certificates/ranking.
        source=self.screen
        if lower>=.02:
            clearance=.02
        else:
            xyz=np.asarray(pose['xyz_m']);rotation=Rotation.from_quat(pose['quat_xyzw']).as_matrix()
            site=rotation@Rotation.from_euler('z',-np.pi/2).as_matrix()
            scene_ids=np.asarray(source.tree.query_ball_point(xyz,source.radius+.02),int)
            target_ids=(np.asarray(source.target_tree.query_ball_point(xyz,source.radius+.02),int)
                        if source.target_tree is not None else np.empty(0,int))
            clearance=.2
            target_boxes=[box for box in source.geometry['boxes']
                          if not source.contact_allowed or not box['name'].endswith('_pad')]
            for cloud,boxes in [(source.points[scene_ids],source.geometry['boxes']),
                                (source.target[target_ids],target_boxes)]:
                local=(cloud-xyz)@site
                for box in boxes:
                    shift=np.asarray(box.get('slide_per_half_opening',[0,0,0]))*source.opening/2
                    if len(local):
                        separation=np.maximum(np.maximum(np.asarray(box['lower'])+shift-local,
                                    local-(np.asarray(box['upper'])+shift)),0.)
                        clearance=min(clearance,float(np.linalg.norm(separation,axis=1).min()))
            clearance=min(clearance,.02)
            if len(source.payload):
                distances,_=source.tree.query(source.payload@rotation.T+xyz)
                clearance=min(clearance,float(distances.min()))
        result={'passed':True,'path_min_clearance_m':float(clearance)}
        if source.initial_margin:
            result.update(initial_margin_policy='positive_clearance_no_further_incursion',
                          initial_margin_pairs_retained=0)
        if source.initial_target_margin:
            result.update(initial_margin_policy='positive_clearance_no_further_incursion',
                          initial_target_margin_pairs_retained=0)
        return result

    def geometry_at(self, pose):
        signature=(*pose['xyz_m'],*pose['quat_xyzw'])
        cache=getattr(self.screen,'_pose_geometry_cache',{})
        if signature in cache:
            self.stats['source_geometry_cache_hits']+=1
            return cache[signature]
        prepared=getattr(self,'prepared',{})
        if signature in prepared:return self._result(pose,*prepared[signature])
        return self.check_batch([pose])[0]


def link_distance_query(field, ik, joints, link_hulls, *, clearance_m=.004):
    """Observed-cloud lower distances for every full-arm link at joint poses.

    A nonpositive/unknown result needs the caller's exact link geometry test.
    This adds a query interface, not an automatic full-arm collision claim;
    self-collision, unseen space and servo convergence are not certified.
    """
    joints=np.asarray(joints,float).reshape(-1,ik.n)
    _,_,_,poses=ik.forward(joints,links=True)
    values=[]
    for hull in link_hulls:
        cover=cover_boxes([hull],opening=0.)
        transform=poses[hull['node']]
        passed,lower=sphere_clearance(field,transform[:,:3,3],transform[:,:3,:3],cover,
            clearance_m=clearance_m,approximation_error_m=(np.sqrt(3)-1)*clearance_m)
        values.append({'name':hull['name'],'node':hull['node'],'distance_lower_m':[float(x) if np.isfinite(x) else None for x in lower],
                       'distance_known':np.isfinite(lower).tolist(),
                       'strictly_clear_of_observed_cloud':passed.tolist()})
    return {'per_link':values,'arm_distance_queries':True,'arm_collisions_checked':False,
            'scope':'observed obstacle clearance only; exact fallback/self collision not run'}


def source_route_samples(poses, radius):
    """The source's 4mm translation+rotation displacement sampling rule."""
    import math
    from scipy.spatial.transform import Slerp
    if not poses:return []
    dense=[poses[0]]
    for a,b in zip(poses[:-1],poses[1:]):
        p,q=np.asarray(a['xyz_m']),np.asarray(b['xyz_m'])
        rotations=Rotation.from_quat([a['quat_xyzw'],b['quat_xyzw']])
        angle=(rotations[1]*rotations[0].inv()).magnitude()
        n=max(1,math.ceil((np.linalg.norm(q-p)+radius*angle)/.004))
        slerp=Slerp([0.,1.],rotations)
        for t in np.linspace(0.,1.,n+1)[1:]:
            dense.append({'xyz_m':((1-t)*p+t*q).tolist(),'quat_xyzw':slerp(t).as_quat().tolist()})
    return dense


def screen_route(source_screen, poses, *, capture_fields):
    """Wrap one source route without changing any source file or global type.

    The shallow screen copy retains the caller's original IK/cache objects,
    so warm-route continuation and normal memoization remain source-owned.
    """
    import copy
    # In the captured unladen corpus the source's warm cache/certificates
    # already beat the cost of constructing an EDT. Amortize the field on a
    # payload route first; hand-only routes can then reuse it for free.
    if not len(source_screen.payload) and not hasattr(capture_fields,'universal_field'):
        return source_screen(poses),{'source_only_no_payload_before_field':1}
    local=copy.copy(source_screen)
    exact=local._geometry_at
    first_signature=(*poses[0]['xyz_m'],*poses[0]['quat_xyzw']) if poses else None
    first_cached=local._pose_geometry_cache.get(first_signature)
    if first_cached is not None and not first_cached['passed']:
        return local(poses),{'source_only_cached_first_rejection':1}
    if len(local.payload):
        kernel=ConservativeGeometry(local,capture_fields=capture_fields)
        kernel.prepare(source_route_samples(poses,local.radius))
        local._geometry_at=kernel.geometry_at
        return local(poses),dict(kernel.stats)
    kernel=None
    stats=Counter()

    def geometry_at(pose):
        nonlocal kernel
        signature=(*pose['xyz_m'],*pose['quat_xyzw'])
        if signature in local._pose_geometry_cache:
            stats['source_geometry_cache_hits']+=1
            return local._pose_geometry_cache[signature]
        if not stats['initial_exact_calls']:
            # The source often rejects its first pose/IK. Avoid constructing
            # an EDT and expanding an unused braking route in that case.
            stats['initial_exact_calls']+=1
            return exact(pose)
        if kernel is None:
            # Bind the unchanged callback before replacing it with this
            # wrapper, otherwise the fallback would recurse into itself.
            local._geometry_at=exact
            kernel=ConservativeGeometry(local,capture_fields=capture_fields)
            kernel.prepare(source_route_samples(poses,local.radius))
            local._geometry_at=geometry_at
        return kernel.geometry_at(pose)

    local._geometry_at=geometry_at
    result=local(poses)
    if kernel is not None:stats.update(kernel.stats)
    return result,dict(stats)
