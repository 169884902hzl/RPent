"""Contrast public noun phrases on measured instance crops without choosing IDs."""
import base64
import hashlib
import io
import re
from collections import defaultdict

import imageio.v2 as imageio
import numpy as np


def score_instance_crops(scene,state,instruction):
    groups = defaultdict(list)
    for entity in scene.entities.values():
        if entity.visible and not entity.part_of:
            groups[entity.name].append(entity)
    groups = {name:peers for name,peers in groups.items() if len(peers)>1}
    if not groups:
        return {}
    if not hasattr(state,'load_bytes'):
        return {e.id:{'status':'crop_input_not_captured','ambiguous':True}
            for peers in groups.values() for e in peers}
    rgb = np.asarray(state.load('agentview_high.png'))
    world = np.asarray(state.load('agentview_world_high.npz'))
    cache = getattr(scene,'_instance_crop_scores',{})
    result = {}
    for name,peers in groups.items():
        phrase = re.search(r'\bthe\s+((?:[a-z]+\s+){0,3}'+re.escape(name)+r')\b',instruction.lower())
        phrase = phrase[1] if phrase else name
        for entity in peers:
            if entity.source_step != state.latest_step:
                result[entity.id] = {'status':'current_instance_unmeasured','ambiguous':True}
                continue
            region = np.isfinite(world).all(axis=-1)&(world>=np.asarray(entity.lower)-.003).all(axis=-1)
            region &= (world<=np.asarray(entity.upper)+.003).all(axis=-1)
            rows,cols = np.nonzero(region)
            if not len(rows):
                result[entity.id] = {'status':'measured_crop_missing','ambiguous':True}
                continue
            y0,y1 = max(0,int(rows.min())-8),min(len(rgb),int(rows.max())+9)
            x0,x1 = max(0,int(cols.min())-8),min(rgb.shape[1],int(cols.max())+9)
            crop = rgb[y0:y1,x0:x1]
            digest = hashlib.sha256(crop.tobytes()).hexdigest()
            scores = {}
            for prompt in dict.fromkeys((name,phrase)):
                key = digest,prompt
                if key not in cache:
                    stream = io.BytesIO()
                    imageio.imwrite(stream,crop,format='png')
                    reply = scene.rpc.call('sam3.segment_all',kwargs={
                        'image_base64':base64.b64encode(stream.getvalue()).decode(),
                        'text_prompt':prompt,'min_score':0.},timeout_s=120)
                    cache[key] = max((float(i.get('score',0.)) for i in reply.get('instances',[])),default=0.)
                scores[prompt] = cache[key]
            result[entity.id] = {'status':'scored','ambiguous':True,'scores':scores,
                'contrast':scores[phrase]-scores[name],'crop_sha256':digest,
                'crop_box_xyxy':[x0,y0,x1,y1],'capture_step':state.latest_step,
                'source':'public_rgbd_crop_and_existing_text_segmentation_score'}
    # Scores are image-bound; another frame cannot inherit old crop evidence.
    scene._instance_crop_scores = {key:value for key,value in cache.items()
        if key[0] in {row.get('crop_sha256') for row in result.values()}}
    return result
