from pathlib import Path
import hashlib,json,os,sys
os.environ.update(CUDA_VISIBLE_DEVICES='',OPENBLAS_NUM_THREADS='1')
root=Path('/public/home/sunyihan/rpent_libero_eval');sys.path.insert(0,str(root/'source_bounded_11a73af_20261017'))
import numpy as np
from PIL import Image
from scipy.spatial import cKDTree
from robots.libero.v5_grasp_geometry import complete_instance_boundary,complete_planar_boundary,clean_object_mask
from robots.libero.bounded_self_filter import gripper_at_measured_fingers,gripper_visual_boxes,remove_current_gripper,remove_visual_robot
from robots.libero.v5_geometric_grasp import panda_geometry
from robots.libero.v5_grasp_kinematics import PublicPoseScreen
p=next((root/'results/bounded_skills/feasibility_20261017/job8071_20').glob('*oracle*/choices.jsonl'));raw=p.read_bytes();rows=[json.loads(l) for l in raw.decode().splitlines()];row=rows[4];sensor=rows[3]['execution_details'][-1]['execution']['trace'][-1]['after'];refs=row['public_geometry_evidence']
def load(p):
 z=np.load(p);return z[z.files[0]]
target=load(refs['bounded_screen_e99_1_target']['path']);tree=cKDTree(target)
xml=root/'.venv/lib/python3.10/site-packages/robosuite/models/assets/grippers/panda_gripper.xml';geometry=panda_geometry(xml);geometry['visual_boxes']=gripper_visual_boxes(str(xml));hand=gripper_at_measured_fingers(geometry,sensor['finger_positions_m']);ik=PublicPoseScreen(xml.parent.parent/'robots/panda/robot.xml',sensor['joint_positions_rad'],sensor['eef_xyz_m'],sensor['eef_quat_xyzw'],geometry['site_offset_in_gripper_m'])
blockers=np.array([[-.12432544678449631,-.2916479706764221,.053421542048454285],[-.13610270619392395,-.22811535000801086,.03782866150140762]])
import importlib.util
module_path=root/'results/bounded_skills/feasibility_20261017/preparation/geometry_sparse_extent_CPU_20261018.py'
spec=importlib.util.spec_from_file_location('geometry_experiment',module_path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
records=[]
for camera in ('agentview','wrist'):
 world=load(p.parent/(camera+'_world_high.npz')/'05.npz').copy();flat=world.reshape(-1,3);valid=np.isfinite(flat).all(1);ids=np.flatnonzero(valid);current,_=remove_current_gripper(flat[ids],sensor['eef_xyz_m'],sensor['eef_quat_xyzw'],hand,sensor['gripper_opening_m']);current,_=ik.remove_measured_arm(current);current,_=remove_visual_robot(current,ik);filtered=np.full(flat.shape,np.nan);keep=cKDTree(current).query(flat[ids],distance_upper_bound=np.nextafter(1e-6,np.inf))[0]<=1e-6;filtered[ids[keep]]=flat[ids[keep]];world=filtered.reshape(world.shape);flat=world.reshape(-1,3);valid=np.isfinite(flat).all(1);ids=np.flatnonzero(valid);mask=np.zeros(len(flat),bool);mask[ids]=tree.query(flat[ids],distance_upper_bound=np.nextafter(1e-6,np.inf))[0]<=1e-6;mask=load(row['perception_evidence']['e99']['sam_mask_files'][camera]['path']).astype(bool);mask &= np.isfinite(world).all(axis=2);mask,_=clean_object_mask(world,mask)
 expanded,e=module.complete_sparse_instance_boundary(world,mask);plane=e['local_plane']
 valid_ids=np.flatnonzero(valid);dist,nearest=cKDTree(flat[valid]).query(blockers)
 memberships=[]
 for point,residual,index in zip(blockers,dist,valid_ids[nearest]):
  y,x=np.unravel_index(index,mask.shape);memberships.append({'point':point.tolist(),'nearest_residual_m':float(residual),'pixel_xy':[int(x),int(y)],'before':bool(mask[y,x]),'after':bool(expanded[y,x]),'old_neighbour_mask':mask[max(0,y-2):y+3,max(0,x-2):x+3].astype(int).tolist()})
 added=expanded&~mask;low=added&(world[:,:,2]<.001)
 ys,xs=np.nonzero(mask|added);box=(max(0,int(xs.min())-30),max(0,int(ys.min())-30),min(mask.shape[1],int(xs.max())+31),min(mask.shape[0],int(ys.max())+31))
 rgb=np.array(Image.open(p.parent/(camera+'_high.png')/'05.png').convert('RGB'))
 marked=rgb.copy();marked[added]=[255,230,0];marked[low]=[255,0,0]
 out=root/'coordination/bounded_skills_20261016/reports'/('box8071_'+camera+'_sparse_boundary_RGB_CPU_20261018.png')
 crop=Image.fromarray(marked).crop(box);crop.resize((crop.width*2,crop.height*2)).save(out)
 low_points=world[low]
 low_evidence={'count':len(low_points),'points':low_points.tolist(),'rgb':rgb[low].tolist(),'crop_path':str(out),'crop_box':box,'world_axes':'measured_world'}
 record={'low_z_evidence':low_evidence,'camera':camera,'input_points':int(mask.sum()),'added':int((expanded&~mask).sum()),'below_1mm_added':int(((expanded&~mask)&(world[:,:,2]<.001)).sum()),'boundary':e,'planar':plane,'blockers':memberships};records.append(record);print(json.dumps({'camera':camera,'added':int(added.sum()),'low_count':int(low.sum()),'crop_path':str(out)}),flush=True)
report={'scope':'saved original SAM mask and public RGB-D/static-mesh/proprioceptive boundary diagnostic; no crossview completion in this isolated comparison,no simulation controls,not a task result','module_sha256':hashlib.sha256(module_path.read_bytes()).hexdigest(),'private_truth_used':False,'training_allowed':False,'choices_sha256':hashlib.sha256(raw).hexdigest(),'rows':records};(root/'coordination/bounded_skills_20261016/reports/box8071_boundary_spacing_bounded_r4_RGB_CPU_20261018.json').write_text(json.dumps(report,indent=2)+'\n')
