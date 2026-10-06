"""Render explicit original public RGB-D views and inspect coarse crop inputs."""

import hashlib
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

from crop_mapping import crop_rgb, padded_roi, mask_bbox, measured_crop_points
from robots.libero.v6_som import project_bounds, visible_box


BASE = Path(__file__).resolve().parent
INPUTS = BASE / 'remote_public_inputs'
REGISTERED_PREFIX = '/public/home/sunyihan/rpent_libero_eval/'


def local_ref(ref):
    assert ref['path'].startswith(REGISTERED_PREFIX)
    path = INPUTS / ref['path'].removeprefix(REGISTERED_PREFIX)
    assert hashlib.sha256(path.read_bytes()).hexdigest() == ref['sha256'], ref['path']
    return path


def panel(image, text):
    canvas = Image.new('RGB', (512, 420), 'white')
    source = image.copy(); source.thumbnail((512, 360))
    canvas.paste(source, ((512 - source.width) // 2, 0))
    ImageDraw.Draw(canvas).multiline_text((6, 366), text, fill='black', spacing=3)
    return canvas


def main():
    selected = json.loads((BASE / 'selected_public_views_remote.json').read_text())
    full_panels, crop_panels, records = [], [], []
    output = BASE / 'crop_demo_context50'; output.mkdir(exist_ok=True)
    for capture in selected['selected_public_views']:
        for camera in ('agentview', 'wrist'):
            view = capture['views'][camera]
            image = Image.open(local_ref(view['files']['rgb'])).convert('RGB')
            metadata = json.loads(local_ref(view['files']['metadata']).read_text())
            with np.load(local_ref(view['files']['world']), allow_pickle=False) as archive:
                world = archive['array']
            assert world.shape == (image.height, image.width, 3)
            shell_queries = [query for query in view['queries'] if query['feature_role'] == 'shell']
            instances = [item for query in shell_queries for item in query['instances'] if 'mask' in item]
            mask = None
            if len(instances) == 1:
                mask = np.asarray(Image.open(local_ref(instances[0]['mask']))) > 0
            box = mask_bbox(mask) if mask is not None else None
            source = 'same_capture_coarse_SAM_stove_mask' if box is not None else None
            support = None
            if box is None and capture['current_shell'] is not None:
                projected = project_bounds(capture['current_shell'], metadata, image.size)
                if projected is not None:
                    box, support = visible_box(projected, capture['current_shell'], world)
                    source = 'same_capture_measured_stove_AABB_with_current_depth_support' if box is not None else None
            record = {'case': capture['case'], 'phase': capture['phase'], 'stage': capture['stage'],
                      'camera': camera, 'source_step': capture['source_step'], 'files': view['files'],
                      'coarse_stove_bbox_xyxy': box, 'bbox_source': source,
                      'same_capture_current_depth_points': support, 'coarse_mask_instances': len(instances),
                      'coarse_mask_scores': [item['score'] for item in instances],
                      'control_binding_reason': view['control_features']['reason'],
                      'queries': [{'prompt': query['prompt'], 'role': query['feature_role'],
                          'instances': [{**{key: item.get(key) for key in ('id', 'score', 'valid_depth_points', 'geometry', 'binding', 'reason')},
                                         'mask_bbox_full_frame': mask_bbox(np.asarray(Image.open(local_ref(item['mask']))) > 0) if 'mask' in item else None}
                                        for item in query['instances']]} for query in view['queries']]}
            annotated = image.copy(); draw = ImageDraw.Draw(annotated)
            if box is not None:
                draw.rectangle(box, outline='lime', width=4)
            for query in view['queries']:
                if query['feature_role'] != 'control': continue
                for item in query['instances']:
                    if 'mask' not in item: continue
                    candidate_box = mask_bbox(np.asarray(Image.open(local_ref(item['mask']))) > 0)
                    if candidate_box:
                        draw.rectangle(candidate_box, outline='red', width=3)
                        draw.text((candidate_box[0], max(0, candidate_box[1]-15)),
                                  f"{query['prompt']} {item['score']:.3f}", fill='red')
            title = f"{capture['case']} {capture['phase']}/{capture['stage']} {camera}"
            full_panels.append(panel(annotated, title + '\n' + record['control_binding_reason']))
            if box is not None:
                roi = padded_roi(box, image.size, fraction=.50)
                crop, mapping = crop_rgb(np.asarray(image), metadata, roi)
                stem = f"{capture['case']}_{capture['phase']}_{capture['stage']}_{camera}"
                Image.fromarray(crop).save(output / (stem + '_crop.png'))
                (output / (stem + '_mapping.json')).write_text(json.dumps(mapping, indent=2)+'\n')
                # Validate on the actual original world map: an all-foreground
                # crop mask must select exactly all finite nonzero ROI samples.
                points, full_mask = measured_crop_points(world, np.ones(crop.shape[:2], bool), mapping)
                x0, y0, x1, y1 = roi
                valid = np.isfinite(world[y0:y1, x0:x1]).all(axis=-1)
                valid &= np.abs(world[y0:y1, x0:x1]).sum(axis=-1) > 1e-6
                assert np.array_equal(points, world[y0:y1, x0:x1][valid])
                record.update(crop_roi_xyxy=roi, crop_shape=list(crop.shape),
                    crop_mapping_sha256=hashlib.sha256((output / (stem + '_mapping.json')).read_bytes()).hexdigest(),
                    original_world_points_indexed=len(points), original_world_point_identity_passed=True)
                crop_panels.append(panel(Image.fromarray(crop), title + '\nROI=' + str(roi)))
            else:
                crop_panels.append(panel(image, title + '\nNo measured coarse stove ROI in this view'))
            records.append(record)
    for name, panels in [('full_views_montage.png', full_panels), ('control_crop_montage_context50.png', crop_panels)]:
        montage = Image.new('RGB', (1024, 420 * (len(panels) // 2)), 'white')
        for index, tile in enumerate(panels): montage.paste(tile, ((index % 2) * 512, (index // 2) * 420))
        montage.save(BASE / name)
    (BASE / 'public_montage_report_context50.json').write_text(json.dumps({'records':records,
        'context_fraction':.50,
        'private_labels_opened':False, 'SAM_crop_inference_run':False,
        'crop_thresholds_are_public_ROI_padding_only':True},indent=2)+'\n')
    print(json.dumps({'public_views':len(records), 'measured_coarse_rois':sum(r['coarse_stove_bbox_xyxy'] is not None for r in records),
        'crop_world_pixel_identity_passed':sum(r.get('original_world_point_identity_passed',False) for r in records),
        'private_labels_opened':False,'SAM_crop_inference_run':False}))


if __name__ == '__main__':main()
