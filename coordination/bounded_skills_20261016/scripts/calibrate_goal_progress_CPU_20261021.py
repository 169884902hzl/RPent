"""Calibrate goal-directed stopping exclusively on immutable original220."""
import argparse
import gzip
import hashlib
import json
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--windows', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--exact-public-frames',action='store_true')
    parser.add_argument('--shard',type=int,default=0)
    parser.add_argument('--shards',type=int,default=1)
    parser.add_argument('--aggregate',type=Path,nargs='*')
    args = parser.parse_args()
    sys.path.insert(0, str(args.source))
    from robots.libero.bounded_goal_progress import instruction_goal_metrics
    from rpent.skill_package.progress import PublicProgress, VERSION
    from robots.libero.bounded_offline_labels import load_annotation_state
    raw = args.windows.read_bytes()
    data = json.loads(gzip.decompress(raw))
    assert len(data['episodes']) == 220 and not data['errors']
    episodes = []
    if not 0<=args.shard<args.shards:raise ValueError('invalid CPU shard')
    for episode in ([] if args.aggregate else data['episodes'][args.shard::args.shards]):
        raw_choices = Path(episode['choices_meta']['path']).read_bytes()
        if hashlib.sha256(raw_choices).hexdigest() != episode['choices_meta']['sha256']:
            raise ValueError('historical choices changed')
        monitor, decisions, normals = PublicProgress(), [], {}
        windows = {w['index']: w for w in episode['windows']}
        for raw_row in raw_choices.splitlines():
            row = json.loads(raw_row)
            if 'request' not in row:
                continue
            request = row['request']
            axes=((1,0,0),(0,-1,0))
            measurement_ref=None
            if args.exact_public_frames:
                measurement_ref=row['private_prefix_annotation_state']
                captured=load_annotation_state(measurement_ref['path'],measurement_ref['sha256'])
                adapter=captured['adapter']
                axes=adapter.scene.view_axes
                for key,plan in adapter.plans.items():
                    normal=(plan.get('handle_measurement',{}).get('pose') or {}).get('approach_normal_xyz')
                    if normal is not None:normals.setdefault(key,normal)
            metrics = instruction_goal_metrics(request, view_axes=axes, normals=normals)
            monitor.update(request, metrics)
            index = row['index']
            decisions.append(dict(index=index, stagnant=monitor.stagnant,
                loop_detected=monitor.loop_detected, metrics=metrics,
                reasons=monitor.last_reasons, start_s=windows.get(index, {}).get('start_s'),
                measurement_ref=measurement_ref,view_axes=axes))
            catalog = {c['id']: c for c in request['candidates']}
            selected = [catalog[cid] for cid in (row.get('decision') or {}).get('candidate_ids', [])]
            monitor.record_actions(selected, row.get('receipts', []),
                goal_directions={m['anchor_id']:m['direction'] for m in metrics if 'direction' in m})
        episodes.append(dict(case=episode['case']['name'], success=episode['success'],
            wall_s=episode['wall_s'], decisions=decisions,
            max_stagnant=max((d['stagnant'] for d in decisions), default=0)))
        print(json.dumps({'case':episode['case']['name'],'closed_episodes':len(episodes)}),flush=True)
    if args.aggregate:
        parts=[json.loads(path.read_bytes()) for path in args.aggregate]
        if any(p.get('public_frame_scope')!='captured_camera_axes_and_handle_normals' for p in parts):
            raise ValueError('cannot mix default axes with exact public-frame calibration')
        episodes=[episode for part in parts for episode in part['episodes']]
        if len(episodes)!=220 or len({e['case'] for e in episodes})!=220:
            raise ValueError('aggregate must include each original220 case exactly once')
    allowed = 'stove_off_libero_90_t39_s8'
    retained = [e for e in episodes if e['success'] and e['case'] != allowed]
    ns = {'allow_only_registered_stove':1+max(e['max_stagnant'] for e in retained),
          'preserve_all_successes':1+max(e['max_stagnant'] for e in episodes if e['success'])}
    sweep = []
    for n in range(1, max(e['max_stagnant'] for e in episodes)+2):
        cut = []
        for episode in episodes:
            stop = next((d for d in episode['decisions'] if d['stagnant'] >= n or d['loop_detected']), None)
            if stop:
                cut.append(dict(case=episode['case'], success=episode['success'], index=stop['index'],
                    loop_detected=stop['loop_detected'],
                    saved_wall_s=max(0., episode['wall_s']-(stop['start_s'] or 0.))))
        sweep.append(dict(N=n, cut_successes=[e['case'] for e in cut if e['success']],
            saved_wall_s=sum(e['saved_wall_s'] for e in cut), episodes=cut))
    comparisons = {}
    for name, n in ns.items():
        result = sweep[n-1]
        violations = [x for x in result['cut_successes'] if name == 'preserve_all_successes' or x != allowed]
        comparisons[name] = dict(result, forbidden_success_cuts=violations)
    output = dict(version=VERSION, episodes=episodes, comparisons=comparisons, threshold_sweep=sweep,
        public_frame_scope='captured_camera_axes_and_handle_normals' if args.exact_public_frames else 'default_axes',
        shard=args.shard,shards=args.shards,aggregate_inputs=[str(p) for p in args.aggregate or []],
        selected_N=ns['allow_only_registered_stove'] if not comparisons['allow_only_registered_stove']['forbidden_success_cuts'] else None,
        windows=dict(path=str(args.windows),sha256=hashlib.sha256(raw).hexdigest()),
        source=str(args.source), script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        domain='original220_only', physics_steps=0, rpc_calls=0, training=False,
        limitation='Historical public requests omit flame fraction and some door plane normals; missing evidence is not progress.')
    with args.output.open('x') as stream:
        json.dump(output, stream, indent=2)
    print(json.dumps(dict(selected_N=output['selected_N'],
        comparisons={key:dict(N=value['N'],cut_successes=value['cut_successes'],
            saved_wall_s=value['saved_wall_s']) for key,value in comparisons.items()})), flush=True)


if __name__ == '__main__':
    main()
