# Copyright 2026 The RPent Authors.
# SPDX-License-Identifier: Apache-2.0
"""Private, evaluation-only helpers for the registered D2 hybrid experiment.

Nothing in this module is a model feature, a candidate generator or a new task
rule. Unsupported predicates stay unsupported. The ordinary original-only
oracle service and its admission rules are unchanged.
"""

from __future__ import annotations

import copy
import hashlib
import json
import os
import tempfile
from pathlib import Path

import numpy as np

D2_SUITES = tuple(f"libero_{family}_{variant}"
                  for family in ("spatial", "object", "goal", "10")
                  for variant in ("swap", "task"))
SPLIT_VERSION = "private-hybrid-call-vla-subtasks/3"
PROGRESS_VERSION = "private-registered-goal-or-subtask/1"
MODES = {"on": "on", "in": "in", "open": "open", "close": "close",
         "turnon": "turn_on", "turnoff": "turn_off"}


def validate_d2_episode(episode: dict) -> None:
    """Admit exactly D2 task0--4/init40, never a PRO test target."""
    if (set(episode) != {"suite", "task", "seed"}
            or episode["suite"] not in D2_SUITES
            or type(episode["task"]) is not int or not 0 <= episode["task"] < 5
            or type(episode["seed"]) is not int or episode["seed"] != 40):
        raise ValueError("hybrid diagnostic admits only registered D2 task0--4/init40")


def split_subtasks(goals: list, instruction: str = '') -> tuple[list[dict], list[dict]]:
    """Split existing flat goal rules into the existing call_vla modes.

    A transfer is pick followed by on/in; articulation remains one subtask.
    There is no inferred prerequisite or task-specific PRO rule. Every
    unsupported clause is returned explicitly, rather than silently skipped.
    """
    subtasks, unsupported = [], []
    for index, goal in enumerate(goals):
        if not isinstance(goal, (list, tuple)) or not goal:
            unsupported.append({"index": index, "goal": goal, "reason": "nonflat_goal"})
            continue
        mode = MODES.get(goal[0]) if isinstance(goal[0], str) else None
        arity = 3 if mode in {"on", "in"} else 2
        if mode is None or len(goal) != arity or not all(isinstance(x, str) for x in goal):
            unsupported.append({"index": index, "goal": goal, "reason": "existing_oracle_rule_not_covered"})
            continue
        common = {"goal_index": index, "goal": list(goal), "source_symbol": goal[1]}
        pushing = mode in {"on", "in"} and instruction.lower().strip().startswith('push ')
        if mode in {"on", "in"} and not pushing:
            subtasks.append({**common, "id": f"g{index}:pick", "mode": "pick", "target_symbol": None})
        if pushing:
            mode = 'push'
        subtasks.append({**common, "id": f"g{index}:{mode}", "mode": mode,
                         "target_symbol": goal[2] if len(goal) == 3 else None})
    # The current bounded selector has no storage-opening prerequisite or
    # deferred-close rule. Recognizing both predicates does not establish a
    # correct task-progress policy; do not invent one for PRO diagnostics.
    insertions = {task['target_symbol'] for task in subtasks if task['mode'] == 'in'}
    for task in subtasks:
        if task['mode'] == 'close' and task['source_symbol'] in insertions:
            unsupported.append({'index': task['goal_index'], 'goal': task['goal'],
                'reason': 'existing_oracle_storage_insert_close_progress_not_covered'})
    return subtasks, unsupported


def choose_branch(self_success: bool | None, vla_success: list[bool | None]) -> dict:
    """Choose a method by observed rate; prefer self on ties, retain unknowns."""
    if len(vla_success) != 3:
        raise ValueError("exactly three VLA trials are required")
    if self_success is None or any(value is None for value in vla_success):
        return {"method": None, "status": "incomplete_measurement", "rate": None}
    own = float(self_success)
    fallback = sum(vla_success) / 3
    return {"method": "self" if own >= fallback else "call_vla",
            "status": "both_failed" if own == fallback == 0 else "measured",
            "rate": max(own, fallback), "self_rate": own,
            "vla_success": sum(vla_success), "vla_n": 3}


def trial_progress_success(trial: dict) -> bool | None:
    """A completed registered goal can supersede a temporary grasp milestone.

    This is private oracle continuation accounting. The trial's original
    grasp, invocation and native whole-task verdicts remain independent.
    Missing historical endpoint predicates never impute new progress.
    """
    if trial.get('private_goal_satisfied_at_endpoint') is True:
        return True
    return trial['success']


_BYTE_JSON_TOKENS = np.asarray([str(i).encode()+b',' for i in range(256)], dtype='S4')


def snapshot_digest(snapshot: dict) -> str:
    """Hash the same canonical JSON without expanding large native byte lists."""
    def convert(value):
        if isinstance(value, np.ndarray):
            return value.tolist()
        if isinstance(value, np.generic):
            return value.item()
        raise TypeError(type(value).__name__)
    def encoded(value):
        return json.dumps(value, sort_keys=True, separators=(",", ":"),
            default=convert, allow_nan=False).encode()

    def large_bytes(value):
        return (isinstance(value, np.ndarray) and value.dtype == np.uint8
            and value.ndim == 1 and value.size >= 65536)

    containing = {}
    def contains_bytes(value):
        if large_bytes(value):
            return True
        if isinstance(value, (dict, list, tuple)):
            key = id(value)
            if key not in containing:
                members = value.values() if isinstance(value, dict) else value
                containing[key] = any(contains_bytes(item) for item in members)
            return containing[key]
        return False

    if not contains_bytes(snapshot):
        return hashlib.sha256(encoded(snapshot)).hexdigest()
    digest = hashlib.sha256()
    def update(value):
        if large_bytes(value):
            digest.update(b'[')
            for start in range(0, len(value), 1 << 20):
                end = min(start+(1 << 20), len(value))
                # Fixed-width ASCII tokens vectorize the decimal conversion.
                # Only NUL padding is removed; the resulting JSON bytes are
                # identical to dumps(array.tolist(), separators=(",", ":")).
                block = _BYTE_JSON_TOKENS[value[start:end]].tobytes().translate(None, b'\0')
                digest.update(block[:-1] if end == len(value) else block)
            digest.update(b']')
        elif not contains_bytes(value):
            digest.update(encoded(value))
        elif isinstance(value, dict):
            digest.update(b'{')
            for index, key in enumerate(sorted(value)):
                if index:
                    digest.update(b',')
                # Let the standard encoder retain all its key semantics,
                # including numeric keys and escaped/non-ASCII strings.
                digest.update(encoded({key: None})[1:-5])
                update(value[key])
            digest.update(b'}')
        else:
            digest.update(b'[')
            for index, item in enumerate(value):
                if index:
                    digest.update(b',')
                update(item)
            digest.update(b']')
    update(snapshot)
    return digest.hexdigest()


def capture_runtime(adapter, policy) -> dict:
    """Detach public measurement/recovery state, without clients or renderers."""
    captured = {
        "adapter": {key: value for key, value in vars(adapter).items()
                    if key not in {"ex", "p", "scene"}},
        "scene": {key: value for key, value in vars(adapter.scene).items()
                  if key not in {"toolkit", "rpc"}},
        "binding": {key: value for key, value in vars(policy.binding).items() if key != "rpc"},
        "private_trace": policy.private_trace,
        "primitive": {key: value for key, value in vars(adapter.p).items() if key.startswith("_bounded_")},
    }
    from rpent.session import EnvState

    store = getattr(adapter.scene.toolkit, '_state', None)
    if isinstance(store, EnvState):
        if hasattr(store,'flush'):
            store.flush()
        if store._step_open:
            raise RuntimeError('cannot checkpoint an unfinished observation capture')
        captured['artifact_state'] = vars(store)
    return copy.deepcopy(captured)


def restore_runtime(adapter, policy, state: dict) -> None:
    """Restore each fork's public caches and retry history as well as physics.

    Each restored branch gets a separate artifact directory and the captured
    frame cursor. Hard links preserve the exact RGB-D bytes without rendering
    again; atomic artifact writes cannot overwrite a sibling's files.
    """
    saved = copy.deepcopy(state)
    current_revision = getattr(adapter,'runtime_revision',None)
    changed_source = current_revision is not None and saved['adapter'].get('runtime_revision') != current_revision
    defaults = {name:copy.deepcopy(getattr(adapter,name)) for name in (
        'runtime_revision','schema6_v1','lazy_planning_v1','rendered_self_filter_v1','vla_budget',
        'verify_instance_crops_v1','vla_options_v2')
        if hasattr(adapter,name)}
    tracking_enabled = getattr(adapter.scene,'rgbd_mask_tracking_v1',False)
    for owner, name, keep in ((adapter, "adapter", {"ex", "p", "scene"}),
                              (adapter.scene, "scene", {"toolkit", "rpc"})):
        resources = {key: value for key, value in vars(owner).items() if key in keep}
        vars(owner).clear()
        vars(owner).update(resources | saved[name])
    if changed_source:
        vars(adapter).update(defaults)
        adapter._base_geometry = adapter._capture_obstacles = None
        adapter._base_geometry_cache = None
        adapter._screen_cache,adapter._instance_cache = {},{}
        adapter._grasp_geometry_cache = {}
        adapter._grasp_surface_fit_cache = {}
        adapter._self_filtered_capture = None
        from rpent.skill_package.progress import PublicProgress,DEFAULT_STAGNANT_DECISIONS
        adapter.public_progress = PublicProgress(DEFAULT_STAGNANT_DECISIONS)
        adapter._progress_normals,adapter._progress_goal_directions = {},{}
        adapter._vla_failed_options,adapter._stationary_observe_modes = set(),set()
        adapter._restoration_migration = {'source_revision':saved['adapter'].get('runtime_revision'),
            'target_revision':current_revision,'public_geometry_caches_invalidated':True,
            'progress_reinitialized_from_next_public_request':True}
        adapter.scene.rgbd_mask_tracking_v1 = tracking_enabled
        if tracking_enabled and not hasattr(adapter.scene,'_mask_tracking_history'):
            adapter.scene._mask_tracking_history = {'entries':{},'frames':{}}
    for key in list(vars(adapter.p)):
        if key.startswith("_bounded_"):
            delattr(adapter.p, key)
    vars(adapter.p).update(saved["primitive"])
    rpc = policy.binding.rpc
    vars(policy.binding).clear()
    vars(policy.binding).update(saved["binding"], rpc=rpc)
    policy.private_trace = saved["private_trace"]
    if 'artifact_state' in saved:
        store = adapter.scene.toolkit._state
        if hasattr(store,'flush'):
            store.flush()
        artifact_state = saved['artifact_state']
        source = artifact_state['_output_dir']
        branch_root = Path(adapter.scene.toolkit._state_output_dir) / 'restored_captures'
        branch_root.mkdir(parents=True, exist_ok=True)
        destination = Path(tempfile.mkdtemp(prefix='fork_', dir=branch_root))
        artifacts = [(name, None) for name in artifact_state['_run_artifacts']]
        artifacts.extend((name, record.step_idx)
            for record in artifact_state['_steps'] for name in record.artifacts)
        # Keep the EnvState object: toolkit tool callbacks and the mask tracker
        # hold references to it, rather than looking up toolkit._state afresh.
        vars(store).clear()
        vars(store).update(artifact_state)
        for name, step in artifacts:
            original = store._artifact_file(name, step)
            if original.exists():  # Older captures may have been pruned.
                target = destination / original.relative_to(source)
                target.parent.mkdir(parents=True, exist_ok=True)
                os.link(original, target)
        store._output_dir = destination
        store._write_manifest()


def d2_session(episode: dict, budget: int = 10000):
    """Open an owned private D2 facade without changing normal PRO services."""
    validate_d2_episode(episode)
    if os.environ.get("LIBERO_TYPE") != "pro":
        raise ValueError("D2 diagnostic requires LIBERO_TYPE=pro")
    from libero.libero import get_libero_path
    from libero.libero.envs.bddl_utils import robosuite_parse_problem

    from robots.libero.tools import LiberoPrimitives
    from robots.libero.v5_env_client import V5SkillEnvClient
    from robots.libero.v5_env_server import V5EnvFacade
    from robots.libero.v5_oracle_server import OriginalOracleFacade
    from scripts.probe_bounded_motion import LocalRPC
    from scripts.probe_v5_skill501_original import make_probe_env

    class D2DevelopmentFacade(OriginalOracleFacade):
        def __init__(self, env, meta):
            task = env.task_suite.get_task(meta["task"])
            path = Path(get_libero_path("bddl_files")) / task.problem_folder / task.bddl_file
            self._goals = robosuite_parse_problem(str(path))["goal_state"]
            self._bddl_sha = hashlib.sha256(path.read_bytes()).hexdigest()
            self._native_diagnostic = True
            self._native_success_events = []
            V5EnvFacade.__init__(self, env, meta=meta, motion_trace_v1=True, rgbd_no_msaa_v1=True)

    meta = {**episode, "max_episode_steps": budget}
    facade = D2DevelopmentFacade(make_probe_env(episode["task"], episode["seed"],
        episode["suite"], budget, rgbd_no_msaa_v1=True), meta)
    try:
        env = V5SkillEnvClient(LocalRPC(facade), expected_meta=meta)
        primitives = LiberoPrimitives(env, None, None, lambda: None)
        primitives.set_obs(env.last_obs)
        return facade, primitives
    except BaseException:
        facade.close()
        raise
