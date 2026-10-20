"""Batched damped least squares over public static chains and calibrated FK.

No simulator calls; numerical failure does not prove infeasibility. Source
adapters can retain their original solver as a fallback and audit new solves.
"""
import numpy as np
from scipy.spatial.transform import Rotation


class BatchedDampedIK:
    def __init__(self, nodes, limits, site_offset, world_rotation, world_offset, *,
                 position_tolerance_m=.008, orientation_tolerance_rad=.05,
                 max_joint_step_rad=.35, iterations=64):
        self.nodes=[(np.asarray(t,float),None if axis is None else np.asarray(axis,float)) for t,axis in nodes]
        self.limits=np.asarray(limits,float)
        self.site_offset=np.asarray(site_offset,float)
        self.world_rotation=np.asarray(world_rotation,float)
        self.world_offset=np.asarray(world_offset,float)
        self.position_tolerance_m=position_tolerance_m
        self.orientation_tolerance_rad=orientation_tolerance_rad
        self.max_joint_step_rad=max_joint_step_rad
        self.iterations=iterations
        self.n=sum(axis is not None for _,axis in self.nodes)
        if self.limits.shape!=(self.n,2) or not (self.limits[:,0]<self.limits[:,1]).all():
            raise ValueError('joint limit shape/range invalid')
        if min(position_tolerance_m,orientation_tolerance_rad,max_joint_step_rad)<=0:
            raise ValueError('positive solve tolerances required')

    @classmethod
    def from_source(cls, source, **kwargs):
        return cls(source.nodes,source.limits,source.site_offset,
                   source.world_rotation,source.world_offset,**kwargs)

    def forward(self, joints, *, links=False):
        joints=np.asarray(joints,float).reshape(-1,self.n)
        batch=len(joints)
        pose=np.broadcast_to(np.eye(4),(batch,4,4)).copy()
        axes=[];origins=[];link_poses=[];index=0
        for fixed,axis in self.nodes:
            pose=pose@fixed
            if axis is not None:
                axes.append(pose[:,:3,:3]@axis)
                origins.append(pose[:,:3,3].copy())
                turn=np.broadcast_to(np.eye(4),(batch,4,4)).copy()
                axis=axis/np.linalg.norm(axis)
                x,y,z=axis
                cross=np.array([[0.,-z,y],[z,0.,-x],[-y,x,0.]])
                angle=joints[:,index]
                turn[:,:3,:3]=np.eye(3)+np.sin(angle)[:,None,None]*cross+(1-np.cos(angle))[:,None,None]*(cross@cross)
                pose=pose@turn;index+=1
            if links:link_poses.append(pose.copy())
        site=pose[:,:3,3]+pose[:,:3,:3]@self.site_offset
        axes=np.stack(axes,1);origins=np.stack(origins,1)
        jac=np.concatenate((np.cross(axes,site[:,None,:]-origins).transpose(0,2,1),
                            axes.transpose(0,2,1)),axis=1)
        xyz=self.world_offset+site@self.world_rotation.T
        rotation=self.world_rotation@pose[:,:3,:3]
        jac=np.concatenate((self.world_rotation@jac[:,:3],self.world_rotation@jac[:,3:]),1)
        if links:
            calibrated=[]
            for p in link_poses:
                w=p.copy();w[:,:3,:3]=self.world_rotation@p[:,:3,:3]
                w[:,:3,3]=self.world_offset+p[:,:3,3]@self.world_rotation.T
                calibrated.append(w)
            return xyz,rotation,jac,calibrated
        return xyz,rotation,jac

    def _evaluate(self, joints, xyz, desired):
        actual,rotation,jac=self.forward(joints)
        error=Rotation.from_matrix(desired@rotation.transpose(0,2,1)).as_rotvec()
        residual=np.concatenate((actual-xyz,.15*error),1)
        x,y,z=error.T
        skew=np.zeros((len(error),3,3))
        skew[:,0,1]=-z;skew[:,0,2]=y;skew[:,1,0]=z
        skew[:,1,2]=-x;skew[:,2,0]=-y;skew[:,2,1]=x
        angle=np.linalg.norm(error,axis=1)
        scale=np.full(len(angle),1/12.)
        mask=angle>=1e-5
        scale[mask]=(1-.5*angle[mask]/np.tan(.5*angle[mask]))/angle[mask]**2
        logjac=np.eye(3)[None,:,:]+.5*skew+scale[:,None,None]*(skew@skew)
        derivative=np.concatenate((jac[:,:3],-.15*logjac@jac[:,3:]),1)
        return residual,derivative

    def verify(self, joints, xyz, quat, reference, *, continuity=True):
        joints=np.asarray(joints,float).reshape(-1,self.n)
        xyz=np.asarray(xyz,float).reshape(-1,3)
        quat=np.asarray(quat,float).reshape(-1,4)
        reference=np.broadcast_to(np.asarray(reference,float),joints.shape)
        actual,rotation,_=self.forward(joints)
        p=np.linalg.norm(actual-xyz,axis=1)
        angle=Rotation.from_matrix(Rotation.from_quat(quat).as_matrix()@rotation.transpose(0,2,1)).magnitude()
        limits=((joints>=self.limits[:,0])&(joints<=self.limits[:,1])).all(1)
        step=np.abs(joints-reference).max(1)
        valid=np.isfinite(joints).all(1)&limits&(p<self.position_tolerance_m)&(angle<self.orientation_tolerance_rad)
        if continuity:valid&=step<=self.max_joint_step_rad+1e-12
        return {'solution_found':valid,'position_error_m':p,'orientation_error_rad':angle,
                'joint_limits_ok':limits,'joint_step_max_rad':step}

    def solve_batch(self, xyz, quat, reference, *, seeds=None, continuity=True):
        xyz=np.asarray(xyz,float).reshape(-1,3);quat=np.asarray(quat,float).reshape(-1,4)
        if len(xyz)!=len(quat) or not np.isfinite(xyz).all() or not np.isfinite(quat).all():
            raise ValueError('finite matching target poses required')
        reference=np.broadcast_to(np.asarray(reference,float),(len(xyz),self.n)).copy()
        lower=np.broadcast_to(self.limits[:,0]+1e-6,reference.shape).copy()
        upper=np.broadcast_to(self.limits[:,1]-1e-6,reference.shape).copy()
        if continuity:
            lower=np.maximum(lower,reference-self.max_joint_step_rad)
            upper=np.minimum(upper,reference+self.max_joint_step_rad)
        if not (lower<upper).all():raise ValueError('reference outside limits/continuation box')
        attempts=[reference] if seeds is None else [reference,*[np.broadcast_to(s,reference.shape) for s in seeds]]
        q=np.stack(attempts,1);k=q.shape[1]
        lower=np.repeat(lower,k,0);upper=np.repeat(upper,k,0)
        q=np.clip(q.reshape(-1,self.n),lower,upper)
        positions=np.repeat(xyz,k,0);quats=np.repeat(quat,k,0)
        target=Rotation.from_quat(quats).as_matrix()
        solved=np.zeros(len(q),bool);evaluations=np.zeros(len(q),int)
        damping=np.full(len(q),1e-5)
        for _ in range(self.iterations):
            active=np.flatnonzero(~solved)
            if not len(active):break
            # Once one seed has met tolerance, stop every seed for that pose.
            done=solved.reshape(-1,k).any(1)
            active=active[~np.repeat(done,k)[active]]
            if not len(active):break
            value,jac=self._evaluate(q[active],positions[active],target[active]);evaluations[active]+=1
            meets=(np.linalg.norm(value[:,:3],axis=1)<self.position_tolerance_m)&(np.linalg.norm(value[:,3:],axis=1)<.15*self.orientation_tolerance_rad)
            solved[active[meets]]=True
            move=~meets;ids=active[move]
            if not len(ids):continue
            value,jac=value[move],jac[move]
            system=jac@jac.transpose(0,2,1)+damping[ids,None,None]*np.eye(6)
            delta=-(jac.transpose(0,2,1)@np.linalg.solve(system,value[...,None]))[...,0]
            delta*=np.minimum(1.,.2/np.maximum(np.linalg.norm(delta,axis=1),1e-12))[:,None]
            updated=np.clip(q[ids]+delta,lower[ids],upper[ids])
            trial,_=self._evaluate(updated,positions[ids],target[ids]);evaluations[ids]+=1
            improved=np.sum(trial**2,1)<np.sum(value**2,1)
            q[ids[improved]]=updated[improved]
            damping[ids]=np.clip(damping[ids]*np.where(improved,.5,10.),1e-7,1.)
        # Independently re-evaluate accepted solutions at final joint values.
        verified=self.verify(q,positions,quats,np.repeat(reference,k,0),continuity=continuity)
        found=verified['solution_found'].reshape(-1,k)
        error=verified['position_error_m']+.15*verified['orientation_error_rad']
        selection=np.where(found,0.,1.)*1e3+error.reshape(-1,k)
        choice=np.argmin(selection,1);flat=np.arange(len(xyz))*k+choice
        return {'joint_positions_rad':q[flat],'solution_found':verified['solution_found'][flat],
            'position_error_m':verified['position_error_m'][flat],
            'orientation_error_rad':verified['orientation_error_rad'][flat],
            'joint_step_max_rad':verified['joint_step_max_rad'][flat],
            'function_evaluations':evaluations.reshape(-1,k).sum(1),
            'arm_collisions_checked':False,'numerical_failure_is_not_proof_of_infeasibility':True}

    def solve_route(self, poses, initial_joints, *, seeds=None):
        previous=np.asarray(initial_joints,float);results=[]
        for pose in poses:
            result=self.solve_batch([pose['xyz_m']],[pose['quat_xyzw']],previous,seeds=seeds)
            result={key:value[0].tolist() if isinstance(value,np.ndarray) else value for key,value in result.items()}
            results.append(result)
            if not result['solution_found']:break
            previous=np.asarray(result['joint_positions_rad'])
        return {'passed':len(results)==len(poses) and all(r['solution_found'] for r in results),
                'solves':results,'max_joint_step_rad':self.max_joint_step_rad,
                'arm_collisions_checked':False}


class SourceIKAdapter:
    """Use batch DLS only after the source cache; retain exact failed solves.

    The adapter changes no collision check. Every accepted DLS output is FK
    verified. A new DLS success may differ from a numerical source failure;
    callers audit those differences on the recorded corpus before opting in.
    """
    def __init__(self, source):
        self.source=source
        self.kernel=BatchedDampedIK.from_source(source)
        self.stats={'cache_hits':0,'dls_success':0,'source_fallback':0}

    def begin_route(self, **kwargs):return self.source.begin_route(**kwargs)

    def __getattr__(self,name):return getattr(self.source,name)

    def check(self, xyz, quat):
        source=self.source
        reference=source.last_solution if source.last_solution is not None else source.joints
        key=(*map(float,xyz),*map(float,quat))
        continuity=source.route_joint_step_rad is not None
        if continuity:key=(*key,*reference)
        if key in source.cache:
            self.stats['cache_hits']+=1
            return source.check(xyz,quat)
        if continuity:self.kernel.max_joint_step_rad=source.route_joint_step_rad
        result=self.kernel.solve_batch([xyz],[quat],reference,continuity=continuity)
        if not result['solution_found'][0]:
            self.stats['source_fallback']+=1
            return source.check(xyz,quat)
        q=result['joint_positions_rad'][0]
        self.stats['dls_success']+=1
        evidence={'version':'public-panda-batched-dls/1','solution_found':True,
            'source':'static_robot_description_and_public_proprioception',
            'robot_xml':source.reference,'solves':[{
                'solution_found':True,'position_error_m':float(result['position_error_m'][0]),
                'orientation_error_rad':float(result['orientation_error_rad'][0]),
                'joint_positions_rad':q.tolist(),'function_evaluations':int(result['function_evaluations'][0]),
                'joint_margin_min_rad':float(np.minimum(q-source.limits[:,0],source.limits[:,1]-q).min()),
                'method':'batched_damped_least_squares'}],
            'arm_collisions_checked':False,'servo_convergence_certified':False,
            'numerical_failure_is_not_proof_of_infeasibility':True}
        if source.warm_start or continuity:source.last_solution=q.copy()
        source.cache[key]=evidence
        if continuity:evidence['local_continuation']={'max_joint_step_rad':source.route_joint_step_rad,
             'from_joint_positions_rad':np.asarray(reference).tolist(),'numerical_search_bound_only':True}
        return evidence
