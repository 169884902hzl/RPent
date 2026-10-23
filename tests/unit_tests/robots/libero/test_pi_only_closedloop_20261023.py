"""Whole-task control retains one world and allows at most one retry."""
import importlib.util
from pathlib import Path


def driver():
    path = Path(__file__).resolve().parents[4]/'coordination/bounded_skills_20261016/scripts/run_pi_only_closedloop_20261023.py'
    spec = importlib.util.spec_from_file_location('pi_only_driver', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_failed_attempt_continues_same_world_with_fresh_noise():
    world = {'steps': 0}
    seeds = []
    def call(index, seed):
        seeds.append(seed)
        world['steps'] += 104
        return dict(world)
    rows = driver().retry_calls(call, lambda: False, lambda: False, 7)
    assert [row['steps'] for row in rows] == [104, 208]
    assert seeds == [7, 1000007]


def test_native_success_does_not_retry_or_query_an_oracle():
    world = {'done': False}
    def call(index, seed):
        world['done'] = True
        return {'seed': seed}
    assert driver().retry_calls(call, lambda: world['done'], lambda: world['done'], 9) == [{'seed': 9}]


def test_native_truncation_prevents_a_second_attempt():
    world = {'truncated': False}
    def call(index, seed):
        world['truncated'] = True
        return {'seed': seed}
    assert driver().retry_calls(call, lambda: False, lambda: world['truncated'], 3) == [{'seed': 3}]
