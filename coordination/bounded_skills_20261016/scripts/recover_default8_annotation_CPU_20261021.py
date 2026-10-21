"""Recover old observed-adapter labels from their captured public caches only."""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import pickle
import sys
from types import SimpleNamespace


def ref(path):
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def checked(reference):
    p = Path(reference['path'])
    assert ref(p) == reference
    return p


def recover(record, source, output):
    import numpy as np
    from rpent.session import EnvState
    from robots.libero.bounded_motion import measured_robot
    from robots.libero.bounded_skills import MeasuredSkillAdapter
    from robots.libero.bounded_offline_labels import (
        FrozenScreens, FrozenSensors, annotate_prefix, capture_annotation_state, request_digest,
        save_annotation_state,
    )
    from libero.libero.envs.bddl_utils import robosuite_parse_problem

    assert record['source_split'] == 'train' and not record['PRO'] and not record['confirmation']
    snapshot = checked(record['snapshot'])
    saved = pickle.loads(snapshot.read_bytes())
    request = record['public_request']
    assert request_digest(request) == record['binding']['request_sha256']
    assert request_digest(saved['request']) == request_digest(request)
    assert saved['request'] == saved['public_runtime']['adapter']['latest_request']
    runtime = copy.deepcopy(saved['public_runtime'])
    revision = json.loads((source/'SOURCE_REVISION.json').read_bytes())
    assert revision['commit'] == record['binding']['source_revision']
    assert runtime['adapter']['runtime_revision'] == MeasuredSkillAdapter.RUNTIME_REVISION
    # Public robot proprioception is the only part read from the sensor cache.
    # In particular, none of the simulator's object pose observables are read.
    raw = saved['physics']['actuator_state']['observation_state']['cache']
    public = {key: raw[key] for key in ('robot0_eef_pos', 'robot0_eef_quat',
        'robot0_gripper_qpos', 'robot0_joint_pos')}
    robot = measured_robot(SimpleNamespace(env=SimpleNamespace(raw_obs=lambda: public)))
    for key in ('eef_xyz_m', 'eef_quat_xyzw', 'gripper_opening_m'):
        assert np.array_equal(robot[key], request['robot'][key]), key
    used = int(np.asarray(saved['physics']['counters']['_elapsed_steps']).item())
    budget = {'used_sim_steps': used, 'remaining_sim_steps': request['remaining_sim_steps'],
        'max_sim_steps': used+request['remaining_sim_steps']}

    # The actual self branch uses SubtaskRPC: it projects the registered goal
    # to one predicate before choosing. Its nonterminal first choice proves
    # that predicate was unsatisfied; it says nothing about the other goals.
    bddl = checked(record['case']['bddl'])
    original_goals = robosuite_parse_problem(str(bddl))['goal_state']
    goal_index = record['outcome_contract']['subtask']['goal_index']
    goals = [original_goals[goal_index]]
    assert goals[0] == record['outcome_contract']['subtask']['goal']
    if goals[0][0] == 'in' and any(word in goals[0][2] for word in ('cabinet', 'drawer', 'microwave')):
        raise ValueError('storage-open predicate was not separately captured')
    branch = next(b for b in record['branches'] if b['method_family'] == 'self')
    trial = branch['trials'][0]
    invocation = checked(trial['invocation_evidence'])
    first = next(c for c in request['candidates'] if c['id'] == branch['candidate_id'])
    assert first['skill'] not in {'finish', 'ask_help', 'call_vla'}
    assert trial['state_binding_verified'] and trial['status'] == 'closed'
    assert not saved['client_stop_flags']['terminated']
    private_status = {'goals': goals, 'satisfied': [False], 'done': False,
        'storage_open': {}, 'bddl_sha256': record['case']['bddl']['sha256']}

    adapter = object.__new__(MeasuredSkillAdapter)
    vars(adapter).update(runtime['adapter'])
    adapter.scene = SimpleNamespace(**runtime['scene'])
    adapter.p = SimpleNamespace(env=FrozenSensors(robot, budget), **runtime['primitive'])
    store = object.__new__(EnvState)
    vars(store).update(runtime['artifact_state'])
    adapter.ex = SimpleNamespace(instruction=adapter.scene.instruction,
        toolkit=SimpleNamespace(_state=store))
    adapter.scene.toolkit = adapter.ex.toolkit
    screens, toggled = {}, []
    # Every surface and IK seed is from the hash-pinned checkpoint. A missing
    # contact variant can share those same captured pixels, with its pose
    # certificates cleared; neither a new image nor a new SAM query is used.
    for anchor in [None, *[a['id'] for a in request['anchors']]]:
        contact = anchor is not None
        key = (anchor, contact, adapter.held, tuple(robot['eef_xyz_m']), tuple(robot['finger_positions_m']))
        if key in adapter._screen_cache:
            screen = adapter._screen_cache[key]
        elif (anchor, False, *key[2:]) in adapter._screen_cache:
            screen = copy.copy(adapter._screen_cache[(anchor, False, *key[2:])])
            screen.contact_allowed = contact
            screen._pose_geometry_cache, screen._endpoint_ik_cache = {}, {}
            toggled.append(anchor)
        else:
            raise ValueError('captured route geometry absent: '+str(anchor))
        screens[anchor] = screen
    adapter._cloud_and_ik = FrozenScreens(screens)
    oracle = SimpleNamespace(adapter=adapter, binding=SimpleNamespace(**runtime['binding']))
    state = capture_annotation_state(oracle, request, status=private_status)
    initial_label = annotate_prefix(state, request, [])
    if first['id'] not in initial_label['rule_acceptable']:
        raise ValueError('recovered initial rules disagree with the actual first self action')
    evidence = {'record_id': record['record_id'], 'snapshot': record['snapshot'],
        'request_sha256': request_digest(request), 'source_revision': record['binding']['source_revision'],
        'outcome_contract_sha256': record['binding']['outcome_contract_sha256'],
        'oracle_source': ref(source/'robots/libero/bounded_oracle.py'),
        'private_status_basis': 'source SubtaskRPC projection; hash-bound actual nonterminal first self action; source done->finish rule',
        'source_subtask_rpc': ref(source/'scripts/probe_bounded_hybrid_d2.py'),
        'private_goal_scope': {'original_goal_count': len(original_goals), 'selected_goal_index': goal_index,
            'scope': 'registered subtask only; other goal truth is unknown'},
        'actual_first_self_action_in_recovered_acceptable': True,
        'first_self_candidate_id': first['id'], 'first_self_invocation': ref(invocation),
        'contact_flags_recreated_from_same_cached_geometry': toggled,
        'geometry_source': 'hash-pinned public_runtime adapter screens; unchanged old capture depth files',
        'captured_depth': [ref(Path(store.artifact_path(camera+'_world_high.npz')))
            for camera in ('agentview', 'wrist')],
        'sensor_keys': list(public), 'physics_steps': 0, 'camera_captures': 0, 'sam_requests': 0,
        'model_visible_private_status': False, 'training': False}
    state['recovery_provenance'] = evidence
    annotation = save_annotation_state(output, state)
    return state, {**evidence, 'annotation_state': annotation}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--records', type=Path, required=True)
    p.add_argument('--queries', type=Path, required=True)
    p.add_argument('--source', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    a.source = a.source.resolve(strict=True)
    sys.path.insert(0, str(a.source))
    from robots.libero.bounded_offline_labels import annotate_prefix
    a.output.mkdir(parents=True, exist_ok=False)
    records = {r['record_id']: r for r in json.loads(a.records.read_bytes())['rows']}
    queries = [json.loads(line) for line in a.queries.read_text().splitlines()]
    states, failures, results = {}, {}, []
    for index, query in enumerate(queries):
        key = query['record_id']
        try:
            if key not in states:
                if key in failures:
                    raise ValueError(failures[key])
                states[key] = recover(records[key], a.source, a.output/f'state_{len(states):02d}.pkl.gz')
            state, evidence = states[key]
            assert query['request_sha256'] == evidence['request_sha256']
            label = annotate_prefix(state, records[key]['public_request'], query['prefix'])
            result = {'query': query, 'annotation_reference': evidence['annotation_state'],
                'binding': evidence, 'label': label}
        except Exception as exc:
            failures.setdefault(key, type(exc).__name__+': '+str(exc))
            result = {'query': query, 'status': 'unknown', 'reason': failures[key]}
        results.append(result)
        with (a.output/'labels.jsonl').open('a') as f:
            f.write(json.dumps(result, default=str)+'\n')
        print(json.dumps({'index': index, 'record_id': key, 'status': result.get('status', result.get('label', {}).get('status'))}), flush=True)
    summary = {'queries': len(queries), 'recovered_states': len(states),
        'labeled': sum(bool(r.get('label', {}).get('rule_acceptable')) for r in results),
        'unknown': sum(r.get('status') == 'unknown' for r in results),
        'failures': failures, 'records': ref(a.records), 'queries_reference': ref(a.queries),
        'script': ref(Path(__file__)), 'physics_steps': 0, 'gpu_used': False}
    (a.output/'manifest.json').write_text(json.dumps(summary, indent=2)+'\n')
    print(json.dumps(summary))


if __name__ == '__main__':
    main()
