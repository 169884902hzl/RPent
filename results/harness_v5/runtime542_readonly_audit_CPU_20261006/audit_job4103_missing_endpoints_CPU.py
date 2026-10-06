"""Read explicit job4103 captures only; no model calls or simulator replay."""
from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np
from PIL import Image, ImageDraw

from robots.libero.v6_som import project_bounds, visible_box

ROOT = Path('/public/home/sunyihan/rpent_libero_eval')
DEST = ROOT / 'results/harness_v5/runtime542_readonly_audit_CPU_20261006'
INPUT = DEST / 'job4103_original_unmeasured_root_causes.json'
SOURCE = ROOT / 'source_v5_runtime544_20261006/robots/libero/v5_runtime.py'


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def reproduce_filter() -> dict:
    tree = ast.parse(SOURCE.read_text())
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'MeasuredScene')
    refresh = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == 'refresh')
    branch = next(n for n in ast.walk(refresh) if isinstance(n, ast.If)
                  and isinstance(n.test, ast.Name) and n.test.id == 'placement')
    module = ast.fix_missing_locations(ast.Module(body=branch.body, type_ignores=[]))
    target = SimpleNamespace(visible=True, lower=(0., 0., 0.), upper=(1., 1., 1.))
    samples = {'seen_outside_target': [((1.05, .5, .2),)],
               'two_seen_inside_target': [((.4, .4, .2),), ((.6, .6, .2),)],
               'one_seen_inside_target': [((.5, .5, .2),)]}
    output = {}
    for name, measured in samples.items():
        namespace = {'placement': (SimpleNamespace(id='e1'), target), 'measured': measured}
        exec(compile(module, str(SOURCE), 'exec'), namespace)
        output[name] = {'input_candidates': len(measured),
                        'output_candidates': len(namespace['measured'])}
    return {'source_path': str(SOURCE), 'source_sha256': sha(SOURCE),
            'source_lines': [branch.lineno, branch.end_lineno], 'cases': output,
            'implication': 'Visible wrong placements and multi-instance ambiguity become missing '
                           'measurement before placement verification. This demonstrates a code '
                           'path; it does not prove old SAM produced a candidate in any of the five cases.'}


def capture(episode: Path, frame: int, view: str, entities: list[dict], registered: dict) -> tuple[Image.Image, dict]:
    files = {'image': f'{view}_high.png', 'metadata': f'{view}_metadata.json',
             'world': f'{view}_world_high.npz'}
    if any(v not in registered[frame] for v in files.values()):
        raise ValueError('capture was not registered by states.json')
    paths = {k: episode / n / f'{frame:02d}.{n.rsplit(".", 1)[1]}' for k, n in files.items()}
    image = Image.open(paths['image']).convert('RGB')
    metadata = json.loads(paths['metadata'].read_text())
    with np.load(paths['world']) as archive:
        world = archive['array'].astype(float)
    draw = ImageDraw.Draw(image)
    records = []
    for e, color in zip(entities, ('#f337b0', '#11e3c1')):
        box = project_bounds(e, metadata, image.size)
        count = 0
        support = None
        if box:
            support, count = visible_box(box, e, world)
            draw.rectangle(box, outline=color, width=2)
            draw.text((box[0], max(0, box[1] - 12)), f"{e['id']} cached", fill=color)
        records.append({'id': e['id'], 'name': e['name'], 'cached_source_step': e['source_step'],
                        'projected_cached_box': box, 'current_depth_support_in_cached_bounds': count,
                        'support_box': support})
    return image, {'frame': frame, 'camera': view, 'files': {k: {'path': str(p), 'sha256': sha(p)}
                  for k, p in paths.items()}, 'cached_projection': records,
                  'caution': 'Depth support uses a previous measured AABB and no SAM mask. '
                             'It cannot establish semantic identity after movement.'}


report = json.loads(INPUT.read_text())
records = []
montage = Image.new('RGB', (6 * 256, len(report['records']) * 296), '#222222')
draw = ImageDraw.Draw(montage)
for row_index, item in enumerate(report['records']):
    episode = Path(item['path']).parent
    choices = episode / 'choices.jsonl'
    row = json.loads(choices.read_text().splitlines()[item['line'] - 1])
    states_path = episode / 'states.json'
    states = json.loads(states_path.read_text())
    registered = {s['step_idx']: s['artifacts'] for s in states['steps']}
    history_path = episode / 'measurement_history.jsonl'
    history = [json.loads(s) for s in history_path.read_text().splitlines()]
    obj = next(e for e in row['measurements'] if e['id'] == row['receipt']['object'])
    target = next((e for e in row['measurements'] if e['id'] == row['receipt'].get('target')), None)
    selected = [obj] + ([target] if target else [])
    lo, hi = item['decision_frame_step'], item['post_frame_step']
    events = [h for h in history if lo < h['source_step'] <= hi and obj['name'] in h['queries']]
    frames = list(dict.fromkeys(h['source_step'] for h in events))
    if not frames:
        frames = [hi]
    first, second = frames[0], frames[-1]
    draw.text((4, row_index * 296 + 2),
              f"{item['case']} {row['selected']} | pink=previous object bounds, cyan=previous target bounds", fill='white')
    captures = []
    for col, (frame, view) in enumerate((lo, v) for v in ('agentview', 'wrist')):
        image, detail = capture(episode, frame, view, selected, registered)
        montage.paste(image.resize((256, 256)), (col * 256, row_index * 296 + 38))
        draw.text((col * 256 + 4, row_index * 296 + 20), f'before {frame} {view}', fill='white')
        captures.append(detail)
    for offset, frame in enumerate((first, second)):
        for camera_index, view in enumerate(('agentview', 'wrist')):
            col = 2 + 2 * offset + camera_index
            image, detail = capture(episode, frame, view, selected, registered)
            montage.paste(image.resize((256, 256)), (col * 256, row_index * 296 + 38))
            draw.text((col * 256 + 4, row_index * 296 + 20), f'endpoint {frame} {view}', fill='white')
            captures.append(detail)
    ids = {e['id'] for e in row['measurements'] if e['name'] == obj['name']}
    after = [e for e in row['post_measurements'] if e['name'] == obj['name']]
    records.append({'case': item['case'], 'selected': row['selected'], 'receipt': row['receipt'],
                    'input_files': {'choices': {'path': str(choices), 'sha256': sha(choices)},
                                    'states': {'path': str(states_path), 'sha256': sha(states_path)},
                                    'history': {'path': str(history_path), 'sha256': sha(history_path)}},
                    'query_events': events, 'same_category_after': after,
                    'same_category_new_ids': [e['id'] for e in after if e['id'] not in ids],
                    'rejected_fixture_measurements': row['rejected_fixture_measurements'],
                    'record_sam_masks_v6': json.loads((episode/'config.json').read_text()).get('record_sam_masks_v6', False),
                    'captures': captures})

montage_path = DEST / 'job4103_original_unmeasured_public_views.png'
montage.save(montage_path)
output = {'scope': 'Read-only, public RGB-D and registered capture artifacts. No SAM/model/physics rerun.',
          'input_report': {'path': str(INPUT), 'sha256': sha(INPUT)},
          'placement_filter_CPU_reproducer': reproduce_filter(), 'records': records,
          'montage': {'path': str(montage_path), 'sha256': sha(montage_path)}}
out_path = DEST / 'job4103_original_unmeasured_capture_evidence_CPU.json'
out_path.write_text(json.dumps(output, indent=2) + '\n')
print(json.dumps({'report': str(out_path), 'sha256': sha(out_path), 'montage': str(montage_path),
                  'filter': output['placement_filter_CPU_reproducer'],
                  'case_summaries': [{'case': r['case'], 'query_frames': [x['source_step'] for x in r['query_events']],
                                      'same_category_new_ids': r['same_category_new_ids']} for r in records]}))
