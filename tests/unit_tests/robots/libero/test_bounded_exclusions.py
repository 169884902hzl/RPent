"""Permanent exclusions use state identities and domain-specific seeds."""
import hashlib
import json
from types import SimpleNamespace

import pytest

from scripts.bounded_state_exclusions import check_exclusions
from scripts.probe_bounded_feasibility import pinned_permanent_exclusions


def test_pinned_registry_reference_is_immutable_and_non_admitting(tmp_path):
    registry = tmp_path / 'registry.jsonl'
    registry.write_text('{"record_type":"permanent_seed_reservation"}\n')
    ref = pinned_permanent_exclusions(registry)
    assert ref['path'] == str(registry.resolve())
    assert len(ref['sha256']) == 64
    assert ref['role'] == 'permanent_confirmation_state_registry'
    assert ref['coverage_complete'] is False
    assert ref['training_admission'] is False

    registry.write_text('{"record_type":"permanent_seed_reservation","changed":true}\n')
    with pytest.raises(ValueError, match='changed'):
        check_exclusions([], ref)


def test_build_plan_embeds_registry_without_changing_category_cohort(tmp_path, monkeypatch):
    from scripts.probe_bounded_feasibility import build_plan
    import rlinf.envs.libero.utils as libero_utils
    import libero.libero as libero_api

    instructions = [
        'pick up the black bowl and place it on the plate',
        'push the plate to the left',
        'pick up the cookie box and place it on the table',
        'pick up the cup and place it on the table',
        'open the top drawer of the cabinet',
        'close the top drawer of the cabinet',
        'turn on the stove', 'turn off the stove',
        'open the microwave', 'close the microwave',
        'put the thing in the basket',
    ]
    bddl_root = tmp_path / 'bddl_files'
    task_dir = bddl_root / 'fixture'
    task_dir.mkdir(parents=True)
    bddl = task_dir / 'fixture.bddl'
    bddl.write_text('(define (problem fixture))\n')

    class Suite:
        def __init__(self, tasks):
            self.tasks = tasks
            self.n_tasks = len(tasks)

        def get_task(self, task_id):
            return self.tasks[task_id]

        def get_task_init_states(self, task_id):
            return [__import__('numpy').array([float(task_id), float(i)]) for i in range(2)]

    suites = {}
    for index, name in enumerate(('libero_spatial', 'libero_object', 'libero_goal', 'libero_10', 'libero_90')):
        tasks = []
        for instruction in instructions[index::5]:
            tasks.append(SimpleNamespace(language=instruction, problem_folder='fixture', bddl_file='fixture.bddl'))
        suites[name] = Suite(tasks)
    monkeypatch.setattr(libero_utils.benchmark, 'get_benchmark', lambda name: (lambda: suites[name]))
    monkeypatch.setattr(libero_api, 'get_libero_path', lambda name: str(bddl_root) if name == 'bddl_files' else str(tmp_path))

    registry = tmp_path / 'registry.jsonl'
    registry.write_text('{"record_type":"permanent_seed_reservation"}\n')
    output = tmp_path / 'plan.json'
    plan = build_plan(output, 1, registry)
    assert len(plan['cases']) == 11
    assert sorted({case['category'] for case in plan['cases']}) == sorted({
        'bowl_transfer', 'plate_push', 'box_transfer', 'cup_transfer', 'container',
        'drawer_open', 'drawer_close', 'stove_on', 'stove_off', 'microwave_open', 'microwave_close'})
    assert plan['training'] is False and plan['confirmation'] is False
    assert plan['permanent_exclusions']['path'] == str(registry.resolve())
    assert plan['permanent_exclusions']['sha256'] == hashlib.sha256(registry.read_bytes()).hexdigest()


def test_known_states_and_reserved_layouts_are_excluded_without_global_seed_ban(tmp_path):
    rows = [
        {'record_type': 'permanent_state_identity', 'identity_domain': 'official_original_libero_init_state',
         'suite': 'libero_10', 'task': 1, 'official_init_index': 15, 'state_sha256': 'a'*64},
        {'record_type': 'permanent_state_identity', 'identity_domain': 'generated_libero_skill_layout',
         'state_sha256': 'b'*64},
        {'record_type': 'permanent_seed_reservation', 'identity_domain': 'generated_moka_confirmation_layout_seed',
         'range_inclusive': [9200000, 9200999]}]
    path = tmp_path/'registry.jsonl'
    path.write_text(''.join(json.dumps(row)+'\n' for row in rows))
    ref = {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(), 'coverage_complete': False}
    case = {'name': 'development', 'episode': {'suite': 'libero_10', 'task': 2, 'seed': 15}, 'state_sha256': 'c'*64}
    report = check_exclusions([case], ref)
    assert report['overlap'] == 0 and report['coverage_complete'] is False
    assert report['training_admission'] is False
    for forbidden in [
        {**case, 'state_sha256': 'b'*64},
        {**case, 'episode': {**case['episode'], 'task': 1}},
        {**case, 'identity_domain': 'generated_moka_confirmation_layout_seed', 'layout_seed': 9200005}]:
        with pytest.raises(ValueError, match='permanently'):
            check_exclusions([forbidden], ref)
    assert check_exclusions([{**case, 'layout_seed': 9200005}], ref)['overlap'] == 0
