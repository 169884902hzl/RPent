"""Original saved RGB-D dark-component inspection; no private state or SAM call."""

import hashlib
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage


REPO = Path('/home/agilex/cobot_magic/rpent_libero_eval')
PRIOR = REPO / 'results/harness_v5/stove555_live_CPU_20261006'
OUTPUT = Path(__file__).resolve().parent
REMOTE_ROOT = '/public/home/sunyihan/rpent_libero_eval/'


def local_ref(ref):
    if not ref['path'].startswith(REMOTE_ROOT): raise ValueError('outside recorded public inputs')
    path = PRIOR / 'remote_public_inputs' / ref['path'].removeprefix(REMOTE_ROOT)
    if hashlib.sha256(path.read_bytes()).hexdigest() != ref['sha256']:
        raise ValueError('public saved file changed')
    return path


def main():
    path = PRIOR / 'offline_crop_sam_manifest.json'
    if hashlib.sha256(path.read_bytes()).hexdigest() != '122de1d0048033c2334044f849e61738384f0c98970e801cfd80be74aa226069':
        raise ValueError('registered view list changed')
    plan = json.loads(path.read_text())
    rows, pictures = [], []
    for frame in plan['frames']:
        rgb = np.asarray(Image.open(local_ref(frame['files']['rgb'])).convert('RGB'))
        with np.load(local_ref(frame['files']['world']), allow_pickle=False) as archive: world = archive['array']
        if world.shape != (*rgb.shape[:2], 3): raise ValueError('unaligned public RGB-D')
        shell = frame['current_shell']; lower, upper = np.asarray(shell['lower']), np.asarray(shell['upper'])
        gap = np.maximum(0, np.maximum(lower - world, world - upper))
        valid = np.isfinite(world).all(axis=-1) & (np.abs(world).sum(axis=-1) > 1e-6)
        # Do not cut off the far half of a control whose near edge attaches
        # to the stove. Check the component's measured AABB gap below, just
        # as the existing control geometry does.
        near = valid & (np.linalg.norm(gap, axis=-1) <= .15)
        near &= (world[..., 2] >= upper[2] - .015) & (world[..., 2] <= upper[2] + .08)
        outside_shell_xy = ~((world[..., :2] >= lower[:2]) & (world[..., :2] <= upper[:2])).all(axis=-1)
        roi = np.zeros(rgb.shape[:2], bool); x0,y0,x1,y1=frame['roi_xyxy'];roi[y0:y1,x0:x1]=True
        baseline_mask = None
        record = {'frame': frame['name'], 'camera': frame['camera'], 'source_step': frame['source_step'],
                  'public_files': frame['files'], 'shell': shell, 'thresholds': {}}
        for threshold in (40, 64, 80):
            dark = (rgb.max(axis=-1) <= threshold) & near & outside_shell_xy & roi
            labels, count = ndimage.label(dark)
            components = []
            kept = np.zeros_like(dark)
            for label in range(1, count + 1):
                mask = labels == label
                if mask.sum() < 100: continue
                points = world[mask].astype(float)
                lo,hi = np.quantile(points,(.02,.98),axis=0)
                if max(hi-lo) > .13: continue
                component_gap = np.maximum(0, np.maximum(lower-hi, lo-upper))
                if np.linalg.norm(component_gap) > .07:continue
                unique = np.unique(points,axis=0)
                zvalues,zcounts=np.unique(unique[:,2],return_counts=True)
                order=np.argsort(zcounts)[-12:]
                components.append({'label':label,'pixels':int(mask.sum()),'unique_points':len(unique),
                    'bbox_pixel_xyxy':[int(np.nonzero(mask)[1].min()),int(np.nonzero(mask)[0].min()),
                                      int(np.nonzero(mask)[1].max())+1,int(np.nonzero(mask)[0].max())+1],
                    'xyz_lower':lo.tolist(),'xyz_upper':hi.tolist(),'xyz_median':np.median(points,axis=0).tolist(),
                    'measured_component_shell_gap_m':float(np.linalg.norm(component_gap)),
                    'z_quantiles':np.quantile(unique[:,2],[0,.1,.25,.5,.75,.9,.95,1]).tolist(),
                    'z_modes':[{'z_m':float(zvalues[i]),'unique_points':int(zcounts[i])} for i in order]})
                if threshold == 64: kept |= mask
            record['thresholds'][str(threshold)]=components
            if threshold == 64:baseline_mask=kept
        image = rgb.copy();image[baseline_mask]=(.5*image[baseline_mask]+.5*np.asarray([0,255,0])).astype(np.uint8)
        image=Image.fromarray(image).crop(tuple(frame['roi_xyxy']))
        image.thumbnail((512,400));tile=Image.new('RGB',(512,440),'white');tile.paste(image,(0,0))
        ImageDraw.Draw(tile).multiline_text((6,403),frame['name']+'\nRGBmax64: '+str(len(record['thresholds']['64']))+' public components',fill='black')
        pictures.append(tile);rows.append(record)
    canvas=Image.new('RGB',(1024,440*((len(pictures)+1)//2)),'white')
    for index,picture in enumerate(pictures):canvas.paste(picture,((index%2)*512,(index//2)*440))
    canvas.save(OUTPUT/'dark_components_montage.png')
    report={'manifest':{'path':str(path),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()},
            'producer_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'records':rows,
            'private_labels_opened':False,'simulator_started':False,'GPU_started':False,'runtime_changed':False,
            'geometric_gate':{'component_shell_gap_m':.07,'per_pixel_search_gap_m':.15,'z_range_relative_shell_upper_m':[-.015,.08],
                              'outside_measured_shell_xy':True,'RGB_max_thresholds':[40,64,80],
                              'minimum_component_pixels':100,'maximum_visible_extent_m':.13}}
    (OUTPUT/'dark_components.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    print(json.dumps({row['frame']:{key:len(v) for key,v in row['thresholds'].items()} for row in rows}))


if __name__ == '__main__':main()
