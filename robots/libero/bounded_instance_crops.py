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


def reclassify_duplicate_instances(scene, state):
    """Check each separate same-class instance against the fixed public vocabulary.

    The SAM minimum score remains the existing .35. No task, simulator name or
    source choice enters this contrast; unresolved crops stay unclassified.
    IDs and their point clouds remain separate and continue to be obstacles.
    """
    from dataclasses import replace
    from robots.libero.v5_runtime import PUBLIC_SEGMENTATION_PROMPTS
    groups = defaultdict(list)
    for entity in scene.entities.values():
        if entity.visible and not entity.part_of:
            groups[entity.name].append(entity)
    peers = [e for group in groups.values() if len(group) > 1 for e in group]
    if not peers or not hasattr(state, 'load_bytes'):
        return {}
    rgb = np.asarray(state.load('agentview_high.png'))
    world = np.asarray(state.load('agentview_world_high.npz'))
    cache = getattr(scene, '_duplicate_class_scores', {})
    evidence = {}
    for entity in peers:
        if entity.source_step != state.latest_step:
            continue
        region = np.isfinite(world).all(axis=-1) & (world >= np.asarray(entity.lower)-.003).all(axis=-1)
        region &= (world <= np.asarray(entity.upper)+.003).all(axis=-1)
        ref = scene.perception_evidence.get(entity.id, {}).get('sam_mask_files', {}).get('agentview')
        if ref and ref.get('source_step') == state.latest_step:
            from pathlib import Path
            raw_mask = Path(ref['path']).read_bytes()
            if hashlib.sha256(raw_mask).hexdigest() != ref['sha256']:
                raise ValueError('public instance-mask artifact changed')
            with np.load(io.BytesIO(raw_mask)) as stored:
                measured_mask = stored[stored.files[0]]
            if measured_mask.shape == region.shape:
                region = measured_mask.astype(bool)
        ys, xs = np.nonzero(region)
        if not len(xs):
            continue
        box = (max(0,int(xs.min())-8),max(0,int(ys.min())-8),
            min(rgb.shape[1],int(xs.max())+9),min(rgb.shape[0],int(ys.max())+9))
        crop = rgb[box[1]:box[3],box[0]:box[2]]
        stream = io.BytesIO();imageio.imwrite(stream,crop,format='png')
        raw = stream.getvalue();digest = hashlib.sha256(raw).hexdigest()
        if digest not in cache:
            scores = {}
            for name,prompt in PUBLIC_SEGMENTATION_PROMPTS.items():
                reply = scene.rpc.call('sam3.segment_all',kwargs={
                    'image_base64':base64.b64encode(raw).decode(),
                    'text_prompt':prompt,'min_score':0.},timeout_s=120)
                scores[name] = max((float(i.get('score',0.)) for i in reply.get('instances',[])),default=0.)
            cache[digest] = scores
        scores = cache[digest];best = max(scores.values(),default=0.)
        winners = [name for name,score in scores.items() if score == best and score >= .35]
        label = winners[0] if len(winners) == 1 else 'unclassified object'
        if entity.name != label:
            # The crop label is public semantics. Retain the segmentation
            # query class separately so the next frame reuses this instance ID.
            tracking=getattr(scene,'_tracking_query_labels',{})
            tracking.setdefault(entity.id,entity.name)
            scene._tracking_query_labels=tracking
            scene.entities[entity.id] = replace(entity,name=label)
        evidence[entity.id] = {'old_class':entity.name,'class':label,'scores':scores,
            'crop_sha256':digest,'capture_step':state.latest_step,'crop_box_xyxy':list(box),
            'source':'public_instance_crop_fixed_vocabulary','private_truth_used':False}
    scene._duplicate_class_scores = cache
    return evidence
