"""Compare equal-tick public requests and private snapshots, without stepping."""
import argparse
import hashlib
import json
import pickle
from pathlib import Path

import numpy as np


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'),
        default=lambda item: item.tolist() if hasattr(item, 'tolist') else str(item)).encode()


def load_snapshot(row):
    ref = row['private_pre_execution_snapshot']
    raw = Path(ref['path']).read_bytes()
    assert digest(raw) == ref['sha256']
    return pickle.loads(raw), ref


def control_sequence(rows):
    controls = []
    for row in rows:
        for detail in row['execution_details']:
            execution = detail.get('execution', {})
            for phase in (execution.get('preparation', {}), execution):
                controls.extend(control['action'] for control in phase.get('trace', []))
    return np.asarray(controls)


def inspect(root, index):
    directory = root/'results/bounded_skills/feasibility_20261017'/f'job8822_{index}'
    new_path, = [p for p in directory.glob('*/choices.jsonl') if not p.parent.name.endswith('_legacy')]
    old_path = new_path.with_name('choices.jsonl').parent.with_name(new_path.parent.name+'_legacy')/'choices.jsonl'
    new = [json.loads(s) for s in new_path.read_bytes().splitlines()]
    old = [json.loads(s) for s in old_path.read_bytes().splitlines()]
    tick = new[0]['sim_steps_after']
    old_index = next(i for i, row in enumerate(old) if row['sim_steps_before'] == tick)
    a, b = new[1], old[old_index]
    assert a['sim_steps_before'] == b['sim_steps_before'] == tick
    snapshots = [load_snapshot(row) for row in (a, b)]
    physics = [np.asarray(s['sim_state'], dtype='<f8') for s, _ in snapshots]
    controls = [control_sequence(rows) for rows in (new[:1], old[:old_index])]
    assert all(len(c) == tick for c in controls)
    request_a, request_b = a['request'], b['request']
    candidates = [{c['id']: c for c in r['candidates']} for r in (request_a, request_b)]
    common = sorted(candidates[0].keys() & candidates[1].keys())
    changes = [dict(id=cid, skill=candidates[0][cid]['skill'],
        parameters=candidates[0][cid]['parameters'], new=candidates[0][cid]['consequences'],
        legacy=candidates[1][cid]['consequences']) for cid in common
        if candidates[0][cid]['consequences'] != candidates[1][cid]['consequences']]
    anchors = [{e['id']: e for e in r['anchors']} for r in (request_a, request_b)]
    geometry = []
    for row in (a, b):
        artifacts = {}
        for name, ref in row['public_geometry_evidence'].items():
            path = Path(ref['path']); raw = path.read_bytes()
            assert digest(raw) == ref['sha256']
            with np.load(path) as archive:
                points = archive[archive.files[0]]
            artifacts[name] = {'capture_step': ref['capture_step'], 'points': len(points),
                'array_sha256': digest(points.tobytes()), 'artifact': ref}
        geometry.append(artifacts)
    return dict(index=index, first_chunk_tick=tick, old_request_index=old_index,
        inputs=[dict(path=str(p), sha256=digest(p.read_bytes())) for p in (new_path, old_path)],
        snapshots=[ref for _, ref in snapshots],
        sim_state_sha256=[digest(p.tobytes()) for p in physics],
        sim_state_exactly_equal=np.array_equal(*physics),
        sim_state_max_abs_delta=float(np.max(np.abs(physics[0]-physics[1]))),
        actuator_state_sha256=[digest(canonical(s['actuator_state'])) for s, _ in snapshots],
        actuator_component_sha256={key: [digest(canonical(s['actuator_state'][key]))
            for s, _ in snapshots] for key in ('model', 'data', 'robots', 'rng')},
        controls_exactly_equal=np.array_equal(*controls),
        controls_sha256=[digest(c.astype('<f8').tobytes()) for c in controls],
        request_field_changes=[key for key in request_a if request_a[key] != request_b.get(key)],
        robots=[request_a['robot'], request_b['robot']],
        anchor_changes=[dict(id=key,new=anchors[0].get(key),legacy=anchors[1].get(key))
            for key in sorted(anchors[0].keys() | anchors[1].keys())
            if anchors[0].get(key) != anchors[1].get(key)],
        candidate_effect_changes=changes,
        new_only_candidates=[candidates[0][cid] for cid in candidates[0].keys()-candidates[1].keys()],
        old_only_candidates=[candidates[1][cid] for cid in candidates[1].keys()-candidates[0].keys()],
        public_geometry=geometry,
        following_receipts=[row.get('receipts', []) for row in new[1:]],
        first_chunk_receipts=new[0]['receipts'],
        new_next_decision=a.get('decision'), legacy_corresponding_decision=b.get('decision'))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, default=Path('/public/home/sunyihan/rpent_libero_eval'))
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    report = dict(pairs=[inspect(args.root, i) for i in (0,24,40)],
        controls=0, gpu_used=False, training=False, confirmation=False, model_visible=False,
        script_sha256=digest(Path(__file__).read_bytes()),
        scope='private equal-tick saved-snapshot audit; not runtime input or new physics')
    args.output.write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps([{k: r[k] for k in ('index','first_chunk_tick','old_request_index',
        'sim_state_exactly_equal','sim_state_max_abs_delta','controls_exactly_equal','request_field_changes')}
        for r in report['pairs']]))
