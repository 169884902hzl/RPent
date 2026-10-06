"""Register control-centred crops before any SAM query; saved public RGB-D only."""

import copy
import hashlib
import json
from pathlib import Path

from PIL import Image, ImageDraw

from crop_mapping import padded_roi


LOCAL_ROOT = Path('/home/agilex/cobot_magic/rpent_libero_eval')
REMOTE_ROOT = Path('/public/home/sunyihan/rpent_libero_eval')
PACKET = Path('results/harness_v5/stove560_control_crop_CPU_20261006')
OLD_PACKET = Path('results/harness_v5/stove555_live_CPU_20261006')
GEOMETRY_PACKET = Path('results/harness_v5/stove559_public_geometry_CPU_20261006')
BASELINE = REMOTE_ROOT / 'results/harness_v5/stove556_crop_SAM_original_20261006/crop_job4240'


def remote_ref(relative):
    data = (LOCAL_ROOT / relative).read_bytes()
    return {'path': str(REMOTE_ROOT / relative), 'sha256': hashlib.sha256(data).hexdigest()}


def public_image(ref):
    relative = Path(ref['path']).relative_to(REMOTE_ROOT)
    path = LOCAL_ROOT / OLD_PACKET / 'remote_public_inputs' / relative
    if hashlib.sha256(path.read_bytes()).hexdigest() != ref['sha256']:
        raise ValueError('local saved public RGB does not match registered capture')
    return Image.open(path).convert('RGB')


def main():
    old_manifest = OLD_PACKET / 'offline_crop_sam_manifest.json'
    bbox_evidence = GEOMETRY_PACKET / 'full_frame/dark_components.json'
    old = json.loads((LOCAL_ROOT / old_manifest).read_text())
    records = json.loads((LOCAL_ROOT / bbox_evidence).read_text())['records']
    by_name = {row['frame']: row for row in records}
    frames = []
    mosaic = Image.new('RGB', (4 * 420, 3 * 460), 'white')
    crop_summary = []
    for index, original in enumerate(old['frames']):
        frame = copy.deepcopy(original)
        components = by_name[frame['name']]['thresholds']['64']
        frame.pop('original_coarse_bbox')
        image = public_image(frame['files']['rgb'])
        panel = Image.new('RGB', (420, 460), 'white')
        draw = ImageDraw.Draw(panel)
        draw.text((8, 8), frame['name'].replace('libero_goal_t7_', ''), fill='black')
        if len(components) == 1:
            bbox = components[0]['bbox_pixel_xyxy']
            roi = padded_roi(bbox, image.size, fraction=.25, minimum_px=20)
            frame.update(status='registered_control_crop', control_bbox_xyxy=bbox, roi_xyxy=roi,
                         roi_source='full_frame_unique_RGBmax64_public_component', context_fraction=.25,
                         minimum_context_px=20, component_label=components[0]['label'],
                         observed_component_pixels=components[0]['pixels'])
            crop = image.crop(roi)
            overlay = ImageDraw.Draw(crop)
            overlay.rectangle((bbox[0]-roi[0], bbox[1]-roi[1], bbox[2]-roi[0]-1, bbox[3]-roi[1]-1),
                              outline='lime', width=2)
            crop.thumbnail((400, 400))
            panel.paste(crop, ((420-crop.width)//2, 45+(400-crop.height)//2))
            draw.text((8, 435), 'green=complete observed bar/rim component', fill='black')
        elif len(components) == 0:
            frame.update(status='missing_control_bbox', control_bbox_xyxy=None, roi_xyxy=None,
                         roi_source='no_unique_RGBmax64_public_component', context_fraction=.25,
                         minimum_context_px=20, observed_component_pixels=0)
            preview = image.copy()
            preview.thumbnail((400, 350))
            panel.paste(preview, ((420-preview.width)//2, 60))
            draw.text((8, 435), 'missing; no crop and no substitute view', fill='black')
        else:
            raise ValueError('public control component is ambiguous')
        frames.append(frame)
        crop_summary.append({key: frame[key] for key in ('name', 'status', 'control_bbox_xyxy', 'roi_xyxy')})
        mosaic.paste(panel, ((index % 4) * 420, (index // 4) * 460))
    if sum(f['status']=='registered_control_crop' for f in frames) != 10:
        raise ValueError('expected ten control crops and two missing views')
    plan = {key: copy.deepcopy(old[key]) for key in ('source_run_manifest', 'source_root', 'source_files',
                                                    'queries', 'minimum_score', 'resources')}
    plan.update(version='original-stove-public-control-crop-SAM/1-dev',
                source_offline_manifest=remote_ref(old_manifest), public_bbox_evidence=remote_ref(bbox_evidence),
                public_geometry_commit='fad9337ddb6d70ff25e0aa91495df7bd349db11f',
                baseline_files={'summary': {'path': str(BASELINE / 'summary.json'),
                                             'sha256': '3c28afeb5bfbe81d5a4ba74f4d5f510f6bd8d72cc0d45f266cc798df667cad30'},
                                'queries': {'path': str(BASELINE / 'queries.jsonl'),
                                            'sha256': '1cec938dfc870104e9929281956139a16c91426941e835b6e373d994305ef117'}},
                producers=[remote_ref(PACKET / name) for name in ('offline_control_crop_sam.py', 'crop_mapping.py',
                           'run_offline_control_crop_sam.sbatch', 'prepare_control_crops.py')],
                frames=frames, frames_count=12, profiles=['control_crop_context25'],
                control_crop_frames=10, missing_control_bbox_views=2, new_RPC_calls=20,
                reused_baseline_RPC_calls=48, context_fraction=.25, minimum_context_px=20,
                selection='All twelve job4240 public original views retained, same order; no outcome-based selection',
                no_simulator=True, no_private_labels=True, unchanged_geometry_rules=True,
                endpoint_state='unmeasured', node_binding=None, qualification_authorized=False, new_training_rows=0,
                warning='RGB dark component is only a crop proposal; neither query hits nor candidate angles are on/off truth')
    directory = LOCAL_ROOT / PACKET
    (directory / 'control_crop_sam_manifest.json').write_text(json.dumps(plan, indent=2) + '\n')
    (directory / 'fixed_crops_summary.json').write_text(json.dumps({'frames': crop_summary,
            'new_RPC_calls': 20, 'baseline_RPC_calls_reused': 48, 'private_labels_opened': False,
            'simulator_started': False, 'GPU_started': False}, indent=2) + '\n')
    mosaic.save(directory / 'fixed_control_crops_montage.png')
    print(json.dumps({'manifest_sha256': hashlib.sha256((directory/'control_crop_sam_manifest.json').read_bytes()).hexdigest(),
                      'new_RPC_calls': 20, 'views_retained': 12, 'missing_views': 2}))


if __name__ == '__main__':
    main()
