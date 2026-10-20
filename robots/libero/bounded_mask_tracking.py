"""Propagate a measured instance mask using public RGB-D, with explicit recall."""
from __future__ import annotations

import numpy as np

VERSION = 'public-rgbd-mask-tracking/1-dev'


class TrackedSegmentation:
    """Own one episode's query/mask history; weak tracks use the same SAM RPC."""

    def __init__(self, rpc, state, history_owner, *, refresh_captures=3):
        self.rpc,self.state=rpc,state
        self.owner=history_owner
        self.refresh_captures=refresh_captures
        self.owner._mask_tracking_history={'entries':{},'frames':{}}
        self.full_queries=self.tracked_queries=self.exact_reuses=0
        self.events=[]

    @property
    def entries(self):
        # Scene snapshot/restore replaces this dictionary between branches.
        # Looking it up through its owner prevents sibling-cache leakage.
        return self.owner._mask_tracking_history['entries']

    @property
    def frames(self):
        return self.owner._mask_tracking_history['frames']

    def call(self, method, args=(), kwargs=None, **options):
        import base64
        import copy
        import hashlib
        import io

        import imageio.v3 as iio

        kwargs=kwargs or {}
        if method!='sam3.segment_all' or not getattr(self.owner,'rgbd_mask_tracking_v1',True):
            return self.rpc.call(method,args=args,kwargs=kwargs,**options)
        image_bytes=base64.b64decode(kwargs['image_base64'])
        digest=hashlib.sha256(image_bytes).hexdigest()
        camera=None
        for view in ('agentview','wrist'):
            if image_bytes==self.state.load_bytes(view+'_high.png'):
                camera=view
                break
        if camera is None:
            return self.rpc.call(method,args=args,kwargs=kwargs,**options)
        step=self.state.latest_step
        frame_key=(camera,step,digest)
        if frame_key not in self.frames:
            self.frames[frame_key]=(iio.imread(image_bytes),self.state.load(camera+'_world_high.npz'))
            while len(self.frames)>4:
                self.frames.pop(next(iter(self.frames)))
        rgb,world=self.frames[frame_key]
        key=(camera,kwargs.get('text_prompt'),kwargs.get('min_score'))
        previous=self.entries.get(key)
        reason='first_query'
        response=None
        if previous is not None:
            if previous['digest']==digest:
                self.exact_reuses+=1
                previous.update(step=step,rgb=rgb,world=world)
                self.events.append({'step':step,'camera':camera,'prompt':kwargs.get('text_prompt'),
                    'reason':'identical_image_mask_reuse','instances':len(previous['instances']),
                    'full_segmentation':False})
                return copy.deepcopy(previous['response'])
            reason='periodic_segmentation_refresh'
            if 0<step-previous['step']<=1 and (self.refresh_captures is None
                    or step-previous['full_step']<self.refresh_captures):
                instances=[]
                reason='previous_instances_missing'
                for item,mask in previous['instances']:
                    tracked,evidence=track_mask(previous['rgb'],rgb,previous['world'],world,mask)
                    if tracked is None:
                        reason=evidence['reason']
                        break
                    rows,cols=np.nonzero(tracked)
                    buf=io.BytesIO()
                    iio.imwrite(buf,tracked.astype(np.uint8)*255,extension='.png')
                    instances.append({**copy.deepcopy(item),'mask_png_base64':base64.b64encode(buf.getvalue()).decode(),
                        'mask_shape':list(tracked.shape),'box':[float(cols.min()),float(rows.min()),
                            float(cols.max()+1),float(rows.max()+1)],
                        'guidance':{'source':'current_rgbd_mask_tracking','tracking':evidence}})
                else:
                    if instances:
                        response={**copy.deepcopy(previous['response']),'instances':instances}
                        reason='tracked_current_rgbd_surface'
        if response is None:
            response=self.rpc.call(method,args=args,kwargs=kwargs,**options)
            self.full_queries+=1
            full_step=step
        else:
            self.tracked_queries+=1
            full_step=previous['full_step']
        instances=[]
        for item in response.get('instances',[]):
            raw=base64.b64decode(item['mask_png_base64'])
            instances.append((copy.deepcopy(item),np.asarray(iio.imread(raw))>0))
        self.entries[key]={'digest':digest,'step':step,'full_step':full_step,'rgb':rgb,'world':world,
            'response':copy.deepcopy(response),'instances':instances}
        while len(self.entries)>64:
            self.entries.pop(next(iter(self.entries)))
        self.events.append({'step':step,'camera':camera,'prompt':kwargs.get('text_prompt'),
            'reason':reason,'instances':len(instances),'full_segmentation':full_step==step})
        return response


def track_mask(previous_rgb, current_rgb, previous_world, current_world, previous_mask):
    """Return a current mask or request segmentation when evidence is weak.

    No task instruction, object class, simulator state or learned weight is
    read. Sparse bidirectional image flow proposes motion; paired current
    depth, RGB agreement and retained surface pixels decide acceptance.
    The result is tracking evidence, never an exact SAM output claim.
    """
    import cv2

    before, after = np.asarray(previous_rgb), np.asarray(current_rgb)
    old_world, new_world = np.asarray(previous_world), np.asarray(current_world)
    mask = np.asarray(previous_mask, dtype=bool)
    if (before.shape != after.shape or before.ndim != 3 or before.shape[2] != 3
            or old_world.shape != before.shape or new_world.shape != before.shape
            or mask.shape != before.shape[:2]):
        raise ValueError('paired RGB, world-depth and mask shapes must agree')
    evidence = {'version': VERSION, 'accepted': False, 'requires_segmentation': True,
        'source': 'previous_measured_mask_and_bidirectional_rgb_flow_current_depth',
        'private_pose_used': False}

    def reject(reason, **detail):
        return None, {**evidence, **detail, 'reason': reason}

    valid_old = np.isfinite(old_world).all(axis=2) & (np.abs(old_world).sum(axis=2) > 1e-6)
    mask = mask & valid_old
    if mask.sum() < 40:
        return reject('previous_measured_surface_missing')
    old_gray = cv2.cvtColor(before.astype(np.uint8), cv2.COLOR_RGB2GRAY)
    new_gray = cv2.cvtColor(after.astype(np.uint8), cv2.COLOR_RGB2GRAY)
    points = cv2.goodFeaturesToTrack(old_gray, maxCorners=128, qualityLevel=.01,
        minDistance=4, mask=mask.astype(np.uint8)*255, blockSize=5)
    if points is None or len(points) < 8:
        return reject('insufficient_measured_texture')
    forward, good_forward, _ = cv2.calcOpticalFlowPyrLK(old_gray,new_gray,points,None,
        winSize=(21,21),maxLevel=3)
    if forward is None:
        return reject('image_flow_missing')
    backward, good_backward, _ = cv2.calcOpticalFlowPyrLK(new_gray,old_gray,forward,None,
        winSize=(21,21),maxLevel=3)
    if backward is None:
        return reject('reverse_image_flow_missing')
    old_pixels = points[:,0]
    new_pixels = forward[:,0]
    cycle = np.linalg.norm(backward[:,0]-old_pixels,axis=1)
    valid = (good_forward[:,0] > 0) & (good_backward[:,0] > 0) & (cycle <= 1.5)
    height,width = mask.shape
    valid &= ((new_pixels >= 0) & (new_pixels < [width-1,height-1])).all(axis=1)
    if valid.sum() < 8 or valid.mean() < .6:
        return reject('bidirectional_flow_confidence_low',features=len(points),inliers=int(valid.sum()))
    old_pixels,new_pixels = old_pixels[valid],new_pixels[valid]
    design = np.c_[old_pixels,np.ones(len(old_pixels))]
    affine = np.linalg.lstsq(design,new_pixels,rcond=None)[0].T
    residual = np.linalg.norm(design@affine.T-new_pixels,axis=1)
    retained = residual <= 2.
    if retained.sum() < 8 or retained.mean() < .7:
        return reject('image_motion_not_one_surface')
    affine = np.linalg.lstsq(design[retained],new_pixels[retained],rcond=None)[0].T
    singular = np.linalg.svd(affine[:,:2],compute_uv=False)
    if singular.min() < .7 or singular.max() > 1.4 or np.linalg.det(affine[:,:2]) <= 0:
        return reject('image_surface_deformation_large')
    old_xy = np.rint(old_pixels[retained]).astype(int)
    new_xy = np.rint(new_pixels[retained]).astype(int)
    a = old_world[old_xy[:,1],old_xy[:,0]]
    b = new_world[new_xy[:,1],new_xy[:,0]]
    paired = np.isfinite(a).all(axis=1)&np.isfinite(b).all(axis=1)
    paired &= (np.abs(a).sum(axis=1)>1e-6)&(np.abs(b).sum(axis=1)>1e-6)
    if paired.sum() < 8:
        return reject('current_paired_depth_missing')
    shifts = b[paired]-a[paired]
    shift = np.median(shifts,axis=0)
    consistent = np.linalg.norm(shifts-shift,axis=1) <= .01
    if consistent.mean() < .7:
        return reject('current_depth_not_one_surface')
    new_mask = cv2.warpAffine(mask.astype(np.uint8),affine,(width,height),flags=cv2.INTER_NEAREST)>0
    predicted_rgb = cv2.warpAffine(before,affine,(width,height),flags=cv2.INTER_LINEAR)
    valid_depth = np.isfinite(new_world).all(axis=2)&(np.abs(new_world).sum(axis=2)>1e-6)
    bounds = np.quantile(old_world[mask],[.01,.99],axis=0)+shift
    supported = valid_depth&((new_world>=bounds[0]-.01)&(new_world<=bounds[1]+.01)).all(axis=2)
    color = np.max(np.abs(after.astype(float)-predicted_rgb.astype(float)),axis=2)/255.
    supported &= color <= .2
    retained_pixels = new_mask&supported
    retained_fraction = retained_pixels.sum()/max(1,new_mask.sum())
    if retained_pixels.sum() < 40 or retained_fraction < .7:
        return reject('current_depth_or_appearance_confidence_low',retained_fraction=float(retained_fraction))
    return retained_pixels,{**evidence,'accepted':True,'requires_segmentation':False,
        'reason':'tracked_current_rgbd_surface','features':len(points),'inliers':int(retained.sum()),
        'median_flow_cycle_error_px':float(np.median(cycle[valid])),
        'translation_m':shift.tolist(),'retained_fraction':float(retained_fraction),
        'current_pixels':int(retained_pixels.sum()),'affine_previous_to_current':affine.tolist()}
