"""Locate measured sweep-rejection points in the saved RGB-D pixels."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import xml.etree.ElementTree as ET

import numpy as np
from PIL import Image, ImageDraw
from scipy.spatial import ConvexHull
from scipy.spatial.transform import Rotation

sys.path.insert(0,os.environ['GRASP_ROUTE_SOURCE'])
from robots.libero.v5_geometric_grasp import panda_geometry, remove_measured_hand, stl_vertices, _rotation, _vector


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('ledger',type=Path)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    raw=json.loads(args.ledger.read_text().splitlines()[0])
    first=raw['first_attempt']; receipt=first['receipt']
    screen=receipt['refinement_view_route_screen']
    segment=next(s for s in screen['segments'] if s.get('collision'))
    collision=segment['collision']; position=np.asarray(collision['xyz'])
    reference=raw['private_grasp_phase']['reference']
    # The logged robot site pose is used only to locate the diagnostic pixels;
    # no target or fixture private pose is used by this CPU report.
    rotation=np.asarray(reference['tcp_rotation_world'])
    body=rotation@Rotation.from_euler('z',np.pi/2).as_matrix()
    start=np.asarray(first['public_before']['robot']['eef_xyz'])
    opening=first['public_before']['robot']['gripper_opening']
    path=Path('/public/home/sunyihan/rpent_libero_eval/.venv/lib/python3.10/site-packages/robosuite/models/assets/grippers/panda_gripper.xml')
    geometry=panda_geometry(str(path)); inflate=segment['mesh_inflation_m']
    root=ET.fromstring(path.read_bytes())
    palm=root.find(".//body[@name='right_gripper']/geom[@name='hand_visual']")
    mesh=next(m for m in root.findall('asset/mesh') if m.get('name')==palm.get('mesh'))
    vertices=stl_vertices(path.parent/mesh.get('file'))@_rotation(palm).T+_vector(palm,'pos','0 0 0')-geometry['site_offset_in_gripper_m']
    hull=ConvexHull(vertices).equations
    directory=Path(raw['output_dir']); rows=[]
    args.output.mkdir(parents=True,exist_ok=False)
    for camera in ('agentview','wrist'):
        cloudpath=directory/(camera+'_world_high.npz')/'00.npz'
        loaded=np.load(cloudpath); cloud=loaded[loaded.files[0]]
        flat=cloud.reshape(-1,3)
        _, count=remove_measured_hand(flat,start,Rotation.from_matrix(body).as_quat(),geometry,opening)
        local=(flat-position)@rotation
        inside=np.zeros(len(flat),dtype=bool)
        for box in geometry['boxes']:
            slide=np.asarray(box.get('slide_per_half_opening',[0,0,0]))*.04
            broad=((local>=np.asarray(box['lower'])+slide-inflate)&(local<=np.asarray(box['upper'])+slide+inflate)).all(axis=1)
            equations=np.asarray(box['convex_halfspaces'])
            broad[broad]=(((local[broad]-slide)@equations[:,:3].T+equations[:,3])<=inflate).all(axis=1)
            inside|=broad
        # Reproduce current hand removal while preserving original pixel indices.
        current=(flat-start)@rotation
        occupied=np.zeros(len(flat),dtype=bool)
        for box in geometry['boxes']:
            slide=np.asarray(box.get('slide_per_half_opening',[0,0,0]))*opening/2
            occupied|=((current>=np.asarray(box['lower'])+slide-.006)&(current<=np.asarray(box['upper'])+slide+.006)).all(axis=1)
        ids=np.flatnonzero(inside&~occupied)
        p=current[ids]
        visual_distance=(p@hull[:,:3].T+hull[:,3]).max(axis=1) if len(ids) else np.array([])
        pixels=np.stack(np.unravel_index(ids,cloud.shape[:2]),axis=1)
        image=Image.open(directory/(camera+'_high.png')/'00.png').convert('RGB')
        draw=ImageDraw.Draw(image)
        for y,x in pixels:draw.ellipse((int(x)-6,int(y)-6,int(x)+6,int(y)+6),outline='red',width=2)
        image.save(args.output/(camera+'_collision_pixels.png'))
        rows.append({'camera':camera,'removed_hand_points':count,'collision_points':flat[ids].tolist(),
                     'pixels_yx':pixels.tolist(),'distance_to_visual_hand_convex_hull_m':visual_distance.tolist(),
                     'cloud':{'path':str(cloudpath),'sha256':hashlib.sha256(cloudpath.read_bytes()).hexdigest()}})
    report={'ledger':{'path':str(args.ledger),'sha256':hashlib.sha256(args.ledger.read_bytes()).hexdigest()},
            'collision':collision,'segment':segment,'views':rows,'diagnostic_only':True,
            'target_truth_coordinates_used':False,'training_allowed':False}
    (args.output/'manifest.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'views':rows},indent=2))


if __name__=='__main__':main()
