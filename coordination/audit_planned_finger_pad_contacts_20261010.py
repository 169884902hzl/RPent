"""Check whether the selected public contact patches fit actual finger pad faces."""
import argparse
from collections import Counter
import hashlib
import importlib.util
import json
from pathlib import Path

import numpy as np
from scipy.spatial.transform import Rotation


def pin(path):
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('report', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    root = Path('/public/home/sunyihan/rpent_libero_eval')
    manifest = json.loads((args.report / 'manifest.json').read_text())
    plans = {}
    for reference in manifest['plans']:
        path = root / reference['path']
        plan = json.loads(path.read_text())
        plans[path.parent.parent.parent.name + '/' + path.parent.parent.name] = plan
    cache, modules, rows = {}, {}, []
    for item in map(json.loads, (args.report / 'rows.jsonl').open()):
        plan = plans[item['group']]
        source = Path(plan['source_path'])
        if source not in modules:
            path = source / 'robots/libero/v5_geometric_grasp.py'
            spec = importlib.util.spec_from_file_location('saved_geometric_' + str(len(modules)), path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            xml = next(iter(plan['conditions'].values()))['overrides']['geometric_gripper_xml']
            modules[source] = module.panda_geometry(xml)
        geometry = modules[source]
        ledger = root / item['input']
        if ledger not in cache:
            if pin(ledger)['sha256'] != item['input_sha256']:
                raise ValueError('closed physical ledger changed')
            cache[ledger] = list(map(json.loads, ledger.open()))
        raw = cache[ledger][item['line']-1]
        receipt = (raw.get('first_attempt') or {}).get('receipt') or {}
        ranks = receipt.get('geometric_grasp_rankings') or []
        if not ranks:
            continue
        rank = ranks[-1]
        best = next((r for r in rank['candidates'] if not r['rejected']), None)
        if best is None:
            continue
        path = Path(raw['output_dir']) / ('analytic_target_' + rank['entity'] + '.npz') / f"{rank['measurement_step']:02d}.npz"
        with np.load(path) as archive:
            points = archive[archive.files[0]]
        site = Rotation.from_quat(best['body_quat_xyzw']).as_matrix() @ Rotation.from_euler('z', -np.pi/2).as_matrix()
        local = (points - best['xyz']) @ site
        counts, evidence = {}, {}
        # The XML pad inner faces are 1 mm closer than the summed joint opening.
        opening = best['width_m'] + .001
        for pad in geometry['boxes']:
            if not pad['name'].endswith('_pad'):
                continue
            slide = np.asarray(pad.get('slide_per_half_opening', [0., 0., 0.])) * opening / 2
            lower, upper = np.asarray(pad['lower']) + slide, np.asarray(pad['upper']) + slide
            face = upper[0] if (lower[0] + upper[0]) < 0 else lower[0]
            inside = ((abs(local[:, 0] - face) <= .002)
                      & (local[:, 1] >= lower[1]) & (local[:, 1] <= upper[1])
                      & (local[:, 2] >= lower[2]) & (local[:, 2] <= upper[2]))
            counts[pad['name']] = int(inside.sum())
            evidence[pad['name']] = {'inner_face_site_x_m': float(face),
                'site_lower': lower.tolist(), 'site_upper': upper.tolist(),
                'measured_public_points_on_contact_face': counts[pad['name']]}
        if len(counts) != 2:
            raise ValueError('two public robot pad faces required')
        rows.append({'case': item['case'], 'group': item['group'], 'candidate': best['id'],
            'approach': best['approach'], 'pad_counts': counts,
            'both_contact_faces_supported': all(counts.values()), 'pad_geometry': evidence,
            'claimed_normal_patch_counts': best.get('normal_patch_support_counts'),
            'width_m': best['width_m'], 'public_target': pin(path), 'robot_meshes': geometry['references'],
            'truth_or_contacts_used': False, 'training_allowed': False})
    args.output.mkdir(parents=True, exist_ok=False)
    path = args.output / 'rows.jsonl'
    path.write_text(''.join(json.dumps(r) + '\n' for r in rows))
    groups = {g: {'selected_n': sum(r['group'] == g for r in rows),
                  'both_contact_faces_supported': sum(r['group'] == g and r['both_contact_faces_supported'] for r in rows),
                  'missing_one_or_both_faces': sum(r['group'] == g and not r['both_contact_faces_supported'] for r in rows)}
              for g in Counter(r['group'] for r in rows)}
    report = {'records': pin(path), 'producer': pin(Path(__file__)), 'input': pin(args.report / 'rows.jsonl'),
        'groups': groups, 'limits': ['Missing public pad-face points do not prove missing private contact.',
            'This diagnoses the planner claimed geometric support; it does not replace v3 truth.'],
        'training_allowed': False, 'qualification_allowed': False}
    (args.output / 'manifest.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report))


if __name__ == '__main__':
    main()
