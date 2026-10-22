"""CPU-only construction/validation of own original-train layouts.

Private geometry is used solely to construct a world and check its native
predicates. These records never enter the model-visible request. No PRO/MAX
assets, tasks or states are read. GPU pilot/label collection is separate.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import itertools
import json
import pickle
from pathlib import Path

import numpy as np
from scipy.spatial.transform import Rotation

from robots.libero.bounded_train_layouts import generate_layout, instruction_identity_check
from robots.libero.v5_branch_state import actuator_state, restore_actuators
from scripts.bounded_state_exclusions import check_exclusions


def pinned(ref):
    path=Path(ref['path'])
    raw=path.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=ref['sha256']:
        raise ValueError('registered original source changed: '+str(path))
    return raw


def confirmation_geometry(reference, original_geometry_reference=None):
    """Read only pinned private exclusion geometry, including reserve rows."""
    registry = json.loads(pinned(reference))
    layouts, sources = [], []
    for pool in registry['fiveclass_pool_reconciliation']['pool_metadata']:
        ref = pool['pool']
        data = json.loads(pinned(ref))
        if data.get('permanent_training_exclusion') is not True:
            raise ValueError('confirmation pool lost its permanent exclusion')
        for row in data['rows']:
            if row.get('permanent_training_exclusion') is not True:
                raise ValueError('confirmation row lost its permanent exclusion')
            positions = row['preparation_provenance']['settled_geometry']
            if not positions or any(len(xyz) != 3 or not np.isfinite(xyz).all()
                    for xyz in positions.values()):
                raise ValueError('confirmation pool has incomplete settled geometry')
            layouts.append(positions)
        sources.append({**ref, 'geometry_records': len(data['rows'])})
    moka_ref = registry['source_index']['moka100']
    data = json.loads(pinned(moka_ref))
    for row in data['records']:
        if row.get('permanent_training_exclusion') is not True:
            raise ValueError('Moka row lost its permanent exclusion')
        symbol = row['layout_parameters']['rule']['moved_object_symbol']
        xy = row['settled_moka_xy_m']
        if len(xy) != 2 or not np.isfinite(xy).all():
            raise ValueError('Moka exclusion requires settled world XY')
        layouts.append({symbol: [*xy, 0.]})
    sources.append({**moka_ref, 'geometry_records': len(data['records'])})
    original_count = 0
    if original_geometry_reference is not None:
        reconstruction = json.loads(pinned(original_geometry_reference))
        if reconstruction['registry'] != reference or reconstruction['controls_executed'] != 0:
            raise ValueError('original exclusion geometry does not match the pinned registry')
        expected = {row['state_sha256']
            for plan in registry['original665']['source_plans']
            for row in json.loads(pinned(plan))['cases']}
        rows = [json.loads(line) for line in pinned(reconstruction['data']).splitlines()]
        identities = [row['state_sha256'] for row in rows]
        if len(set(identities)) != len(identities) or set(identities) != expected:
            raise ValueError('original exclusion geometry is incomplete or duplicated')
        for row in rows:
            positions = row['body_origins_world_m']
            if (row['permanent_training_exclusion'] is not True or not positions
                    or any(len(xyz) != 3 or not np.isfinite(xyz).all() for xyz in positions.values())):
                raise ValueError('invalid original confirmation geometry')
            layouts.append(positions)
        original_count = len(rows)
        sources.append({**reconstruction['data'], 'geometry_records': original_count})
    # Complete known geometry does not establish exhaustive historical
    # registration or authorize training. Every registered reserve stays out.
    return layouts, {'registry': reference, 'sources': sources,
        'geometry_records_checked': len(layouts),
        'original_confirmation_geometry_records_missing': registry['counts']['official_original_confirmation_states']-original_count,
        'known_original_geometry_records_checked': original_count,
        'coverage_complete': False, 'training_admission': False,
        'distance_metric': 'world_xy_euclidean', 'minimum_distance_m': .05,
        'source_policy': 'private geometry exclusion only; no outcomes, instructions or labels consumed'}


def restore(env,snapshot):
    env.sim.set_state_from_flattened(snapshot['sim_state'])
    restore_actuators(env,snapshot['actuator_state'])


def object_box(env,name,obj):
    """Exact local bounds of the loaded static collision geometry."""
    sim=env.sim
    body=env.env.obj_body_id[name]
    origin=sim.data.body_xpos[body].copy()
    rotation=sim.data.body_xmat[body].reshape(3,3)
    cloud=[]
    for geom_name in obj.contact_geoms:
        geom=sim.model.geom_name2id(geom_name)
        kind=int(sim.model.geom_type[geom])
        size=sim.model.geom_size[geom]
        if kind==7:
            mesh=int(sim.model.geom_dataid[geom])
            start=int(sim.model.mesh_vertadr[mesh]);count=int(sim.model.mesh_vertnum[mesh])
            points=sim.model.mesh_vert[start:start+count]
        else:
            half=(np.repeat(size[0],3) if kind==2 else
                np.array([size[0],size[0],size[1]+size[0]]) if kind==3 else
                np.array([size[0],size[0],size[1]]) if kind==5 else size)
            points=np.array(list(itertools.product((-1,1),repeat=3)))*half
        world=points@sim.data.geom_xmat[geom].reshape(3,3).T+sim.data.geom_xpos[geom]
        cloud.append((world-origin)@rotation)
    points=np.concatenate(cloud)
    lower,upper=points.min(0),points.max(0)
    centre=(lower+upper)/2
    return {'id':name,'xyz_m':(origin+centre@rotation.T).tolist(),
        'size_m':(upper-lower).tolist(),'local_centre_m':centre.tolist(),
        'yaw_rad':float(Rotation.from_matrix(rotation).as_euler('xyz')[2]),
        'movable':bool(obj.joints and sim.model.jnt_type[sim.model.joint_name2id(obj.joints[0])]==0)}


def apply_layout(env,layout,*,skip=()):
    for item in layout:
        if not item['movable'] or item['id'] in skip:
            continue
        obj=env.env.objects_dict[item['id']]
        rotation=Rotation.from_euler('z',item['yaw_rad'])
        origin=np.asarray(item['xyz_m'])-rotation.apply(item['local_centre_m'])
        xyzw=rotation.as_quat()
        env.sim.data.set_joint_qpos(obj.joints[0],np.r_[origin,xyzw[3],xyzw[:3]])
        env.sim.data.set_joint_qvel(obj.joints[0],np.zeros(6))
    env.sim.forward()


def penetrations(env,moving):
    """List new-object penetrations; positive/touching contacts are legal."""
    bodies={env.env.obj_body_id[name] for name in moving}
    def owner(geom):
        body=int(env.sim.model.geom_bodyid[geom])
        while body and body not in bodies:
            body=int(env.sim.model.body_parentid[body])
        return body
    return [{'geoms':[int(c.geom1),int(c.geom2)],'depth_m':float(-c.dist)}
        for c in env.sim.data.contact[:env.sim.data.ncon]
        if c.dist < -1e-5 and (owner(c.geom1) or owner(c.geom2))
        and owner(c.geom1)!=owner(c.geom2)]


def generate_case(manifest,index,seed,output,confirmation_reference=None,original_geometry_reference=None):
    from libero.libero.envs.env_wrapper import ControlEnv
    case=manifest['cases'][index]
    episode=case['episode'];name=case['name'].split('_B2_')[0]
    parents=json.loads(pinned(manifest['frozen_parent_index']))['parents']
    # The original task/initial identity must already belong to frozen train.
    parent_id='original220/'+name+'/0'
    parent=parents[parent_id]
    if parent['split']!='train' or parent['status']!='ok':
        raise ValueError('parent is not an admitted original train position')
    choices=[json.loads(line) for line in pinned(parent['source_link']).decode().splitlines()]
    initial=pickle.loads(pinned(choices[0]['private_pre_execution_snapshot']))
    annotation=pickle.loads(gzip.decompress(pinned(parent['private_prefix_annotation_state'])))
    axes=annotation['adapter'].scene.view_axes
    check_exclusions([{'name':name,'episode':episode,
        'state_sha256':parent['initial_state_sha256']}],manifest['permanent_exclusions'])
    bddl=case['bddl'];pinned(bddl)
    # Build the predicate witness in a distinct CPU simulator by replaying the
    # final saved original-train control segment. Never infer it from success text.
    last=choices[-1]
    final=pickle.loads(pinned(last['private_pre_execution_snapshot']))
    actions=[row['action'] for d in last['execution_details']
        for row in d.get('execution',{}).get('trace',[])]
    options=dict(bddl_file_name=bddl['path'],use_camera_obs=False,
        has_offscreen_renderer=False,has_renderer=False,ignore_done=True)
    base,witness=ControlEnv(**options),ControlEnv(**options)
    try:
        base.reset();witness.reset();restore(base,initial);restore(witness,final)
        for action in actions:
            witness.step(np.asarray(action))
        if not witness.check_success():
            raise ValueError('CPU original control replay did not produce a native predicate witness')
        goal_state=witness.sim.get_state().flatten().copy()
        goals=base.env.parsed_problem['goal_state']
        goal_symbols={symbol for goal in goals for symbol in goal[1:]}
        destinations={goal[2] for goal in goals if len(goal)==3}
        objects=[object_box(base,n,o) for n,o in base.env.objects_dict.items()]
        objects.extend(object_box(base,n,o) | {'movable':False}
            for n,o in base.env.fixtures_dict.items() if o.contact_geoms)
        for item in objects:
            if any(symbol.startswith(item['id']) for symbol in destinations):
                item['movable']=False
        size=np.asarray(base.env.table_full_size)
        offset=np.asarray(base.env.workspace_offset)
        support={'lower_m':(offset-np.r_[size[:2]/2,size[2]]).tolist(),
            'upper_m':(offset+np.r_[size[:2]/2,0.]).tolist()}
        moving={x['id'] for x in objects if x['movable']}
        goal_bodies={name for name in base.env.objects_dict
            if any(symbol.startswith(name) for symbol in goal_symbols)}
        def validate(layout):
            restore(base,initial);apply_layout(base,layout)
            initial_bad=penetrations(base,moving)
            witness.sim.set_state_from_flattened(goal_state)
            apply_layout(witness,layout,skip=goal_bodies)
            bad=penetrations(witness,moving-goal_bodies)
            return {'native_predicates_satisfied':bool(witness.check_success()),
                'nonintersecting':not initial_bad and not bad,
                **instruction_identity_check(layout,goals,base.language_instruction,axes),
                'initial_penetrations':initial_bad,'witness_penetrations':bad,
                'source':'independent_CPU_native_original_task_predicates',
                'original_controls_replayed':len(actions)}
        exclusions, geometry_evidence = (confirmation_geometry(confirmation_reference, original_geometry_reference)
            if confirmation_reference is not None else ((), None))
        layout=generate_layout(parent={**episode,'split':'train',
            'initial_state_sha256':parent['initial_state_sha256']},objects=objects,
            support=support,seed=seed,witness_check=validate,confirmation_layouts=exclusions)
        restore(base,initial);apply_layout(base,layout['objects'])
        physics={'sim_state':base.sim.get_state().flatten(), 'actuator_state':actuator_state(base)}
        raw=pickle.dumps({**physics,
            'layout':layout,'parent_id':parent_id},protocol=5)
        output.mkdir(parents=True,exist_ok=False)
        (output/'private_generated_state.pkl').write_bytes(raw)
        report={'layout':layout,'state_sha256':hashlib.sha256(raw).hexdigest(),
            'parent_id':parent_id,'original_bddl':bddl,'CPU_only':True,
            'GPU_rollouts':0,'training_admission':False,
            'integration_sha256':physics['actuator_state']['integration']['sha256'],
            'native_data_sha256':physics['actuator_state']['native_data']['sha256'],
            'confirmation_geometry_exclusions':geometry_evidence,
            'pending':['historical confirmation inventory completeness',
                'additional asset distractor insertion','N1-qualified physical pilot']}
        (output/'manifest.json').write_text(json.dumps(report,indent=2)+'\n')
        return report
    finally:
        base.close();witness.close()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest',type=Path,required=True)
    parser.add_argument('--case',type=int,required=True)
    parser.add_argument('--seed',type=int,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--confirmation-reconciliation',type=Path)
    parser.add_argument('--confirmation-reconciliation-sha256')
    parser.add_argument('--original-confirmation-geometry', type=Path)
    parser.add_argument('--original-confirmation-geometry-sha256')
    args=parser.parse_args()
    if bool(args.confirmation_reconciliation) != bool(args.confirmation_reconciliation_sha256):
        parser.error('confirmation reconciliation requires both path and SHA256')
    if bool(args.original_confirmation_geometry) != bool(args.original_confirmation_geometry_sha256):
        parser.error('original confirmation geometry requires both path and SHA256')
    if args.original_confirmation_geometry and not args.confirmation_reconciliation:
        parser.error('original geometry must be associated with a pinned confirmation registry')
    reference = ({'path':str(args.confirmation_reconciliation),
        'sha256':args.confirmation_reconciliation_sha256} if args.confirmation_reconciliation else None)
    original = ({'path': str(args.original_confirmation_geometry),
        'sha256': args.original_confirmation_geometry_sha256} if args.original_confirmation_geometry else None)
    result=generate_case(json.loads(args.manifest.read_bytes()),args.case,args.seed,args.output,reference,original)
    print(json.dumps({'state_sha256':result['state_sha256'],
        'native_witness':result['layout']['predicate_witness'],'training_admission':False}))


if __name__=='__main__':
    main()
