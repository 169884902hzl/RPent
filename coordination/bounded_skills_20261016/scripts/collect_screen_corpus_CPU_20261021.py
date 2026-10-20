"""Record exact public route/IK calls replayed from trusted saved observations.

No simulator, RPC, model inference or private task rule is used. Pickle inputs
are for trusted CPU kernel development only, never model training.
"""
import argparse
import gzip
import hashlib
import json
import pickle
import sys
import time
from collections import Counter
from pathlib import Path
from types import SimpleNamespace


def public_adapter(saved):
    """Rebuild only the public part of a complete physical branch snapshot."""
    from rpent.session import EnvState
    from robots.libero.bounded_skills import MeasuredSkillAdapter
    from robots.libero.v5_runtime import MeasuredScene
    runtime = saved['public_runtime']
    if 'artifact_state' in runtime:
        store = object.__new__(EnvState)
        vars(store).update(runtime['artifact_state'])
    else:
        # Old branches omitted the frame cursor. Their captured screen/cache
        # still owns complete geometry, but never read a guessed later frame.
        def missing_frame(*args, **kwargs):
            raise RuntimeError('legacy snapshot has no captured artifact cursor')
        store = SimpleNamespace(load=missing_frame,
            latest_step=max(e.source_step for e in runtime['scene']['entities'].values()))
    class NoRPC:
        def call(self, *args, **kwargs):
            raise AssertionError('CPU corpus cannot call RPC')
    scene = object.__new__(MeasuredScene)
    vars(scene).update(runtime['scene'])
    scene.toolkit = SimpleNamespace(_state=store)
    scene.rpc = NoRPC()
    raw = saved['physics']['actuator_state']['observation_state']['cache']
    cache = {key:raw[key] for key in ('robot0_eef_pos','robot0_eef_quat',
        'robot0_gripper_qpos','robot0_joint_pos')}
    request = saved['request']
    budget = {'remaining_sim_steps':request['remaining_sim_steps'],
              'used_sim_steps':10000-request['remaining_sim_steps']}
    adapter = object.__new__(MeasuredSkillAdapter)
    vars(adapter).update(runtime['adapter'])
    adapter.scene = scene
    adapter.p = SimpleNamespace(env=SimpleNamespace(raw_obs=lambda:cache,
        execution_budget=lambda:budget, terminated=False,truncated=False))
    adapter.ex = SimpleNamespace(toolkit=scene.toolkit,instruction=scene.instruction)
    adapter.record_public_geometry = False
    return adapter, request


def sha(data):
    return hashlib.sha256(data).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--windows', type=Path)
    parser.add_argument('--branchpoint', type=Path)
    parser.add_argument('--category', default='saved_branchpoint')
    parser.add_argument('--domain', choices=('original','D2'), default='original')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--shard', type=int, default=0)
    parser.add_argument('--shards', type=int, default=1)
    parser.add_argument('--limit', type=int, default=300)
    args = parser.parse_args()
    sys.path.insert(0, str(args.source))
    from robots.libero.bounded_offline_labels import load_annotation_state
    from robots.libero.bounded_screen import PublicRouteScreen
    from robots.libero.v5_grasp_kinematics import PublicPoseScreen

    args.output.mkdir(parents=True, exist_ok=False)
    blobs = args.output / 'inputs'
    blobs.mkdir()
    context = {}
    counts = Counter()
    errors = []
    assets = {}
    recording_overhead = 0.
    ledger = (args.output / 'calls.jsonl').open('x', buffering=1)

    def record(owner, name, kind):
        original = getattr(owner, name)

        def wrapped(instance, *positional, **kwargs):
            nonlocal recording_overhead
            # Include caches and incoming IK continuation state. Serialization
            # time is deliberately outside the measured kernel call interval.
            save_started = time.perf_counter()
            raw = pickle.dumps((instance, positional, kwargs), protocol=5)
            digest = sha(raw)
            path = blobs / (digest + '.pkl.gz')
            if not path.exists():
                path.write_bytes(gzip.compress(raw, compresslevel=1, mtime=0))
            recording_overhead += time.perf_counter()-save_started
            overhead_before = recording_overhead
            started = time.perf_counter()
            result = original(instance, *positional, **kwargs)
            elapsed = time.perf_counter() - started - (recording_overhead-overhead_before)
            log_started = time.perf_counter()
            counts[kind] += 1
            row = dict(kind=kind, index=counts[kind], context=dict(context),
                input=str(path), input_sha256=digest, wall_s=elapsed,
                result=result, input_bytes=len(raw))
            ledger.write(json.dumps(row, default=lambda x: x.tolist() if hasattr(x, 'tolist') else str(x))+'\n')
            solver = instance if kind == 'ik' else instance.ik
            if solver is not None:
                reference = solver.reference
                assets[reference['path']] = reference['sha256']
            recording_overhead += time.perf_counter()-log_started
            return result

        setattr(owner, name, wrapped)

    record(PublicRouteScreen, '__call__', 'route')
    record(PublicPoseScreen, 'check', 'ik')
    if args.branchpoint:
        adapter, request = public_adapter(pickle.loads(args.branchpoint.read_bytes()))
        context.update(category=args.category, checkpoint=str(args.branchpoint),
            checkpoint_sha256=sha(args.branchpoint.read_bytes()), domain=args.domain,
            held=adapter.held, original_domain=args.domain=='original')
        for candidate in request['candidates']:
            if candidate['skill'] in {'call_vla','observe','finish','ask_help'}:
                continue
            context.update(candidate_id=candidate['id'],skill=candidate['skill'])
            try:
                adapter._candidate(candidate['skill'],candidate['parameters'],complete=True)
            except Exception as exc:
                errors.append(dict(context=context.copy(),error=repr(exc)))
        selected = []
    else:
        cohort = json.loads(gzip.decompress(args.windows.read_bytes()))
        selected = cohort['episodes'][args.shard::args.shards]
    # Round-robin episodes preserves bowl/cup/drawer/microwave and later
    # held-payload observations instead of exhausting the first category.
    for episode in selected:
        choice_path = Path(episode['choices_meta']['path'])
        rows = [json.loads(line) for line in choice_path.open()]
        positions = [0, len(rows)//2, len(rows)-1]
        for position in dict.fromkeys(positions):
            row = rows[position]
            ref = row.get('private_prefix_annotation_state')
            if not ref:
                continue
            try:
                captured = load_annotation_state(ref['path'], ref['sha256'])
                adapter = captured['adapter']
                adapter.record_public_geometry = False
                context.clear()
                context.update(episode=episode['case']['name'], category=episode['category'],
                    source_choices=str(choice_path), decision_index=row['index'],
                    annotation=ref, held=adapter.held, original_domain=True)
                for candidate in row['request']['candidates']:
                    if candidate['skill'] in {'call_vla', 'observe', 'finish', 'ask_help'}:
                        continue
                    context['candidate_id'] = candidate['id']
                    context['skill'] = candidate['skill']
                    adapter._candidate(candidate['skill'], candidate['parameters'], complete=True)
            except Exception as exc:
                errors.append(dict(context=context.copy(), error=repr(exc)))
            if counts['route'] >= args.limit:
                break
        print(json.dumps(dict(episode=episode['case']['name'], counts=dict(counts), errors=len(errors))), flush=True)
        if counts['route'] >= args.limit:
            break
    ledger.close()
    manifest = dict(version='public-screen-call-corpus/1', source=str(args.source),
        source_sha=__import__('subprocess').check_output(['git', '-C', str(args.source), 'rev-parse', 'HEAD'], text=True).strip()
            if (args.source/'.git').exists() else None,
        source_files={str(p.relative_to(args.source)): sha(p.read_bytes()) for p in [
            args.source/'robots/libero/bounded_screen.py', args.source/'robots/libero/v5_grasp_kinematics.py']},
        script_sha256=sha(Path(__file__).read_bytes()), counts=dict(counts), errors=errors,
        robot_assets=assets, calls_sha256=sha((args.output/'calls.jsonl').read_bytes()),
        windows=dict(path=str(args.windows), sha256=sha(args.windows.read_bytes())) if args.windows else None,
        branchpoint=dict(path=str(args.branchpoint),sha256=sha(args.branchpoint.read_bytes())) if args.branchpoint else None,
        shard=args.shard, shards=args.shards, physics_steps=0, rpc_calls=0,
        scope='real saved public observations; current source CPU replay, not historic runtime timings',
        training=False, pro=args.domain=='D2', confirmation=False)
    (args.output/'manifest.json').write_text(json.dumps(manifest, indent=2)+'\n')
    print(json.dumps(manifest), flush=True)


if __name__ == '__main__':
    main()
