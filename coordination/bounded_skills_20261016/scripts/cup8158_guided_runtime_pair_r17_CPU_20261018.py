"""Pair saved-public carry screening with a measured-pixel SAM refinement."""

import argparse
import copy
import hashlib
import json
from pathlib import Path

root = Path('/public/home/sunyihan/rpent_libero_eval')
parser = argparse.ArgumentParser()
parser.add_argument('--sam-report', type=Path, required=True)
parser.add_argument('--working-source', type=Path, required=True)
args = parser.parse_args()
setup = root/'coordination/bounded_skills_20261016/scripts/cup8158_current_membership_stages_CPU_20261018.py'
context = {}
exec(compile(setup.read_text().replace("source = 'bc160ff'", "source = '9cacb71'").split('stages = []', 1)[0], str(setup), 'exec'), context)
import numpy as np
from PIL import Image
from robots.libero.bounded_motion import MotionConfig, SmoothMotion, measured_derivatives
from robots.libero.v5_state import Entity

a, row, directory, load = (context[name] for name in ('a', 'row', 'directory', 'load'))
key, step = context['key'], context['step']
def load_frame(name):
    path = directory/name/(f'{step:02d}'+Path(name).suffix)
    return np.asarray(Image.open(path)) if path.suffix == '.png' else load(path)
a.ex.toolkit._state.load = load_frame
a._cloud_and_ik()
a.held = key
a.config = MotionConfig()
tail = context['rows'][15]['execution_details'][-1]['execution']['trace'][-4:]
assert len(tail) == 4
a.p._bounded_motion_samples = [(index, control['after']) for index, control in enumerate(tail)]
a.p._bounded_control_index = 3
a.scene.entities = {}
for anchor in row['request']['anchors']:
    centre, size = np.asarray(anchor['xyz_m']), np.asarray(anchor['size_m'])
    a.scene.entities[anchor['id']] = Entity(anchor['id'], anchor['label'], tuple(centre),
        tuple(centre-size/2), tuple(centre+size/2), True, step)
a.target_cache = a.scene.entities.copy()
reference = directory/'bounded_payload_reference_robot.json'/'11.json'
a.payload_reference = {'target': load(directory/'bounded_payload_reference_target.npz'/'11.npz'),
    'scene': load(directory/'bounded_payload_reference_scene.npz'/'11.npz'),
    'robot': json.loads(reference.read_text()), 'capture_step': 11}
original_views = copy.deepcopy(a.scene.measurement_clouds_by_view[key])
diagnostic_path = args.sam_report
diagnostic = json.loads(diagnostic_path.read_text())
import base64
import io
import importlib.util
import sys

def load_module(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec)
    sys.modules[name]=module
    spec.loader.exec_module(module)
    return module
working_source=args.working_source
payload_path=working_source/'robots/libero/bounded_payload.py'
adapter_path=working_source/'robots/libero/bounded_skills.py'
payload=load_module('robots.libero.bounded_payload',payload_path)
working=load_module('bounded_guided_adapter',adapter_path)
original_class=a.__class__
queries=[]
def saved_sam_reply(method,*,kwargs,timeout_s):
    assert method=='sam3.segment'
    raw=base64.b64decode(kwargs['image_base64'])
    cameras=[camera for camera in ('agentview','wrist')
        if raw==(directory/(camera+'_high.png')/(f'{step:02d}.png')).read_bytes()]
    assert len(cameras)==1
    camera=cameras[0]
    guided=next(r for r in diagnostic['results'] if r['camera']==camera and 'point' in r['query'])
    assert kwargs['point']==guided['query']['point'],(camera,kwargs['point'],guided['query']['point'])
    if not guided['found']:
        queries.append({'camera':camera,'point':kwargs['point'],'found':False,'reason':guided['reason']})
        return {'found':False,'reason':guided['reason']}
    assert hashlib.sha256(Path(guided['mask']).read_bytes()).hexdigest()==guided['sha256']
    with np.load(guided['mask']) as archive:
        mask=archive['mask']
    buffer=io.BytesIO();Image.fromarray(mask.astype('uint8')*255).save(buffer,format='PNG')
    queries.append({'camera':camera,'point':kwargs['point'],'found':True,'saved_mask_sha256':guided['sha256']})
    return {'found':True,'mask_png_base64':base64.b64encode(buffer.getvalue()).decode(),
        'mask_shape':list(mask.shape),'score':guided['score']}
a.scene.rpc=type('SavedSam',(),{'call':staticmethod(saved_sam_reply)})()
a.scene.calls=0
a.ex.toolkit._state.load_bytes=lambda name:(directory/name/(f'{step:02d}'+Path(name).suffix)).read_bytes()
results=[]
for method,cls in [('original',original_class),('working_runtime',working.MeasuredSkillAdapter)]:
    a.__class__=cls
    a.scene.measurement_clouds_by_view[key]=copy.deepcopy(original_views)
    a._instance_cache.clear();a._screen_cache.clear()
    screen=a._cloud_and_ik('e99')
    route=a._route('carry_to',{'target_id':'e99'})
    trajectory,_,_,check=SmoothMotion(a.p,screen,a.config).prepare(route)
    results.append({'method':method,'route':route,'duration_s':trajectory.duration,'check':check,
        'boundary':copy.deepcopy(a.instance_boundary_evidence[key])})
    print(method,check['passed'],check['reason'],flush=True)
report={'scope':'actual working adapter, exact saved raw RGB-D and genuine SAM responses at identical point prompts; zero controls',
    'snapshot_base':context['source'],'choices_sha256':hashlib.sha256(context['choices'].read_bytes()).hexdigest(),
    'working_source':str(working_source),
    'adapter_sha256':hashlib.sha256(adapter_path.read_bytes()).hexdigest(),
    'payload_sha256':hashlib.sha256(payload_path.read_bytes()).hexdigest(),
    'sam_report':{'path':str(diagnostic_path),'sha256':hashlib.sha256(diagnostic_path.read_bytes()).hexdigest()},
    'initial_derivatives':[d.tolist() for d in measured_derivatives(a.p,a.config.hz)],
    'private_truth_used':False,'training':False,'gpu_used':False,'queries':queries,'results':results}
output=root/'coordination/bounded_skills_20261016/reports/cup8158_guided_runtime_pair_r17_CPU_20261018.json'
output.write_text(json.dumps(report,indent=2)+'\n')
