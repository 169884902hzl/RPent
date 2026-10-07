"""Original moka sentence through the measured SOURCE571 placement path.

Only the public selected moka and stove bind the action. Original task status
is recorded before and after the action and never controls its termination.
"""

import copy
import hashlib
import importlib
import json
import os
import sys
import traceback
from pathlib import Path


def _bootstrap_registered_dependencies(manifest: Path) -> dict:
    """Import the registered decision scorer before importing the runner.

    The array launcher changes directory to ``/tmp``.  Relying only on the
    shell's PYTHONPATH therefore made the dependency lookup depend on the
    submit environment.  The manifest directory is the registered preparation
    root, so make it the first import location and verify the module actually
    came from there.
    """
    preparation = manifest.resolve(strict=True).parent
    source_root = Path(
        os.environ.get("MOKA_TRANSFER_SOURCE", str(Path(__file__).resolve().parents[1]))
    ).expanduser().resolve(strict=True)
    # Put the source root in place first, then the preparation directory at
    # index zero so a stale source-tree module cannot shadow the registered
    # supplement.
    for path in (source_root, preparation):
        value = str(path)
        if value in sys.path:
            sys.path.remove(value)
        sys.path.insert(0, value)
    importlib.invalidate_caches()
    sys.modules.pop("typed_choice_eval", None)
    module = importlib.import_module("typed_choice_eval")
    actual = Path(module.__file__).resolve(strict=True)
    expected = (preparation / "typed_choice_eval.py").resolve()
    # Local smoke runs may use the immutable source snapshot when the
    # preparation packet is materialized without the supplement; production
    # packets must carry the explicit preparation copy.
    if expected.is_file() and actual != expected:
        raise ImportError(f"typed_choice_eval resolved outside preparation: {actual}")
    return {
        "module": "typed_choice_eval",
        "path": str(actual),
        "sha256": hashlib.sha256(actual.read_bytes()).hexdigest(),
        "manifest_preparation": str(preparation),
        "source_root": str(source_root),
    }


def _output_argument() -> Path | None:
    try:
        return Path(sys.argv[sys.argv.index("--output") + 1]).resolve()
    except (ValueError, IndexError):
        return None


def _audit_registered_module(plan, module, relative_path):
    """Reject a shadowed or changed runner before any service is launched."""
    snapshot = plan["source_snapshot"]
    source_root = Path(snapshot["path"]).resolve(strict=True)
    expected = source_root / relative_path
    actual = Path(module.__file__).resolve(strict=True)
    if actual != expected.resolve(strict=True):
        raise ImportError(f"{module.__name__} resolved outside registered snapshot: {actual}")
    references = [ref for ref in snapshot["files"]
                  if Path(ref["path"]).resolve() == actual]
    if len(references) != 1:
        raise ValueError(f"Snapshot must explicitly pin {relative_path}")
    digest = hashlib.sha256(actual.read_bytes()).hexdigest()
    if digest != references[0]["sha256"]:
        raise ValueError(f"Registered runner module changed: {actual}")
    return {"path": str(actual), "sha256": digest, "relative_path": relative_path}


def execute_original_subtask(executor, case, condition, obj, receipt, evidence):
    from math import hypot, isfinite

    from robots.libero import v5_subtasks
    from robots.libero.v5_runtime import V5Executor
    from robots.libero.v5_state import Candidate, entity_record

    if not case.get("original_goal_source") or not case.get("instruction"):
        raise ValueError("Original moka transfer needs its complete original instruction")
    # This is an operating-area heuristic from public RGB-D bounds and robot
    # proprioception, not a kinematic reachability or private-goal selector.
    evidence["public_stove_entities_before_refresh"] = [
        entity_record(entity) for entity in executor.scene.entities.values() if entity.name == "stove"
    ]
    executor.scene.refresh(["stove"])

    def measured_vector(value):
        if value is None:
            return None
        try:
            values = [float(item) for item in value]
        except (TypeError, ValueError):
            return None
        return values if len(values) == 3 and all(isfinite(item) for item in values) else None

    eef = measured_vector(getattr(executor.p, "_last_obs_eef_pos", None))
    binding = {
        "version": "public_stove_bbox_operating_area/2",
        "refresh_queries": ["stove"], "public_eef_xyz_m": eef,
        "eef_source": "robot_proprioception", "bbox_source": "RGB-D perception",
        "max_nearest_bbox_xy_distance_m": 1.0, "entities": [],
        "private_goal_used_for_selection": False,
    }
    stoves, unmeasured = [], False
    for entity in executor.scene.entities.values():
        if entity.name != "stove":
            continue
        xyz = measured_vector(entity.xyz)
        lower = measured_vector(entity.lower)
        upper = measured_vector(entity.upper)
        record = {
            "id": entity.id, "name": entity.name, "visible": bool(entity.visible),
            "xyz_m": xyz, "bbox_m": {"lower": lower, "upper": upper},
            "source_step": getattr(entity, "source_step", None),
            "geometry": getattr(entity, "geometry", None),
            "nearest_bbox_xy_distance_m": None,
        }
        if (eef is None or not entity.visible or xyz is None or lower is None or upper is None
                or any(lo > hi for lo, hi in zip(lower, upper))):
            record.update(disposition="unmeasured", rejection_reason="current_public_measurement_missing")
            unmeasured = True
        else:
            distance = hypot(*(max(lower[i] - eef[i], 0., eef[i] - upper[i]) for i in (0, 1)))
            record["nearest_bbox_xy_distance_m"] = distance
            if distance > binding["max_nearest_bbox_xy_distance_m"]:
                record.update(disposition="rejected", rejection_reason="outside_public_operating_area")
            else:
                record.update(disposition="eligible", rejection_reason=None)
                stoves.append(entity)
        binding["entities"].append(record)
    # Dual-view fusion and a second SAM mask may describe the same stove.
    # Merge only nearly identical current measured bounds, never select by
    # the private task's target or by median-centre proximity alone.
    def same_measured_bbox(first, second):
        overlap = 1.
        volume_first = volume_second = 1.
        for axis in range(3):
            if max(abs(first.lower[axis] - second.lower[axis]),
                   abs(first.upper[axis] - second.upper[axis])) > .02:
                return False
            overlap *= max(0., min(first.upper[axis], second.upper[axis])
                           - max(first.lower[axis], second.lower[axis]))
            volume_first *= max(0., first.upper[axis] - first.lower[axis])
            volume_second *= max(0., second.upper[axis] - second.lower[axis])
        union = volume_first + volume_second - overlap
        return union > 0. and overlap / union >= .8

    measurements = getattr(executor.scene, "perception_evidence", {})
    def measurement_rank(entity):
        measured = measurements.get(entity.id, {})
        return (-int(bool(measured.get("fusion", {}).get("fused", measured.get("fused")))),
                -len(measured.get("source_cameras", [])), str(entity.id))

    unique = []
    for entity in sorted(stoves, key=measurement_rank):
        representative = next((other for other in unique
                               if same_measured_bbox(entity, other)), None)
        if representative is None:
            unique.append(entity)
        else:
            record = next(row for row in binding["entities"] if row["id"] == entity.id)
            record.update(disposition="duplicate_measurement",
                          representative_id=representative.id,
                          rejection_reason="same_current_public_bbox")
    binding["duplicate_rule"] = {"max_bbox_edge_difference_m": .02, "min_bbox_iou": .8}
    stoves = unique
    binding["eligible_entity_ids"] = [entity.id for entity in stoves]
    binding["outcome"] = ("unmeasured" if unmeasured or eef is None else "unique"
                          if len(stoves) == 1 else "ambiguous" if stoves else "missing")
    evidence["public_stove_binding_evidence"] = binding
    if binding["outcome"] != "unique":
        receipt.update(executed=False, place_verified=None, verification="unmeasured",
                       failure_reason="original_transfer_public_stove_binding_missing_or_ambiguous")
        return
    target = stoves[0]
    action = Candidate("vla_subtask", obj.id, target.id, "on")
    prompt = case["instruction"]

    def private_status():
        try:
            return executor.p.env._client.call("oracle.status", timeout_s=30)
        except Exception:
            evidence["error_stage"] = "private_metrology"
            raise

    evidence["private_original_task_status_before"] = private_status()
    evidence.update(contact_prompt=prompt, contact_max_chunks=condition["max_chunks"],
                    full_prompt_origin="original_BDDL_complete_task_sentence",
                    public_transfer_binding={"object": entity_record(obj),
                                             "target": entity_record(target), "mode": "on"})
    original_prompt = v5_subtasks.subtask_prompt

    def exact_original_prompt(selected, entities, view_axes):
        # Keep the runtime's measured-instance binding check before using the
        # unmodified public task sentence.
        original_prompt(selected, entities, view_axes)
        return prompt

    v5_subtasks.subtask_prompt = exact_original_prompt
    try:
        # SOURCE571 executes all five controls in each VLA chunk. Native task
        # status is a private diagnostic latch and cannot stop the macro.
        with executor.p.env.complete_skill():
            V5Executor.execute_subtask(executor, action, receipt)
    finally:
        v5_subtasks.subtask_prompt = original_prompt
    receipt.update(tool="vla_subtask", object=obj.id, target=target.id, mode="on",
                   execution_kind="complete_original_subtask_with_public_placement",
                   original_public_instruction=prompt)
    evidence["public_placement_verdict"] = receipt.get("place_verified")
    evidence["public_placement_measurements"] = copy.deepcopy(executor.last_verification_measurements)
    evidence["public_receipt_before_private_metrology"] = copy.deepcopy(receipt)
    evidence["private_original_task_status_after"] = private_status()
    evidence['server_chunk_execution'] = executor.p.env._client.call('diagnostic.moka_chunks', timeout_s=30)
    evidence['registered_reset_evidence'] = executor.p.env._client.call('diagnostic.moka_registered_reset', timeout_s=30)


def main():
    if '--help' in sys.argv or '-h' in sys.argv:
        from scripts import probe_v5_grasp449_20261005 as probe
        probe.main()
        return
    manifest = Path(sys.argv[sys.argv.index('--manifest') + 1]).resolve(strict=True)
    plan = json.loads(manifest.read_text())
    dependency_audit = {}
    try:
        dependency_audit = _bootstrap_registered_dependencies(manifest)
        if Path(dependency_audit["source_root"]) != Path(plan["source_snapshot"]["path"]).resolve(strict=True):
            raise ValueError("MOKA_TRANSFER_SOURCE differs from registered snapshot")
        import harness_v5_eval
        from scripts import probe_v5_grasp449_20261005 as probe
        from scripts import v5_probe_preflight as preflight
        dependency_audit["runner_modules"] = {
            module.__name__: _audit_registered_module(plan, module, relative_path)
            for module, relative_path in (
                (harness_v5_eval, "harness_v5_eval.py"),
                (probe, "scripts/probe_v5_grasp449_20261005.py"),
            )
        }
    except Exception:
        output = _output_argument()
        if output is not None:
            output.mkdir(parents=True, exist_ok=True)
            (output / "startup_dependency_audit.json").write_text(json.dumps({
                **dependency_audit, "error_stage": "registered_dependency_import",
                "traceback": traceback.format_exc(),
            }, indent=2) + "\n")
        raise
    from rpent.utils import daemon
    cases = {case['name']: case for case in plan['cases']}
    original_daemon = daemon.ProcessDaemon
    original_run_episode = harness_v5_eval.run_episode
    original_validate_states = preflight.validate_registered_states

    class TransferDaemon(original_daemon):
        def __init__(self, *args, **kwargs):
            command = list(kwargs.get('cmd', []))
            if 'robots.libero.v5_oracle_server' in command:
                index = command.index('robots.libero.v5_oracle_server')
                if index == 0 or command[index-1] != '-m':
                    raise ValueError('Unexpected original oracle launcher')
                command[index-1:index+1] = [str(Path(__file__).with_name('serve_v5_moka_transfer_registered_20261007.py'))]
                kwargs['cmd'] = command
            super().__init__(*args, **kwargs)

    def run_episode(args, *argv, **kwargs):
        name = Path(args.output_dir).name.removesuffix('_infra_retry1')
        case = cases[name]
        previous = os.environ.get('MOKA_TRANSFER_REGISTERED_STATE_REFERENCE')
        reference = case.get('registered_layout_state')
        if reference is not None:
            os.environ['MOKA_TRANSFER_REGISTERED_STATE_REFERENCE'] = json.dumps(reference)
        else:
            os.environ.pop('MOKA_TRANSFER_REGISTERED_STATE_REFERENCE', None)
        try:
            return original_run_episode(args, *argv, **kwargs)
        finally:
            if previous is None:
                os.environ.pop('MOKA_TRANSFER_REGISTERED_STATE_REFERENCE', None)
            else:
                os.environ['MOKA_TRANSFER_REGISTERED_STATE_REFERENCE'] = previous

    def validate_states(registered_cases):
        official = [case for case in registered_cases if not case.get('registered_layout_state')]
        result = original_validate_states(official)
        import numpy as np
        custom = 0
        for case in registered_cases:
            reference = case.get('registered_layout_state')
            if reference is None:
                continue
            preflight.pinned_file(reference, 'registered_layout_state')
            value = json.loads(Path(reference['path']).read_text())
            digest = hashlib.sha256(np.asarray(value['rawstate'], dtype='<f8', order='C').tobytes()).hexdigest()
            if digest != case['state_sha256'] or value['episode'] != case['episode']:
                raise ValueError('Registered layout state differs from manifest')
            custom += 1
        return {**result, 'state_hashes_checked': result['state_hashes_checked']+custom,
                'registered_layout_states_checked': custom}

    daemon.ProcessDaemon = TransferDaemon
    harness_v5_eval.run_episode = run_episode
    preflight.validate_registered_states = validate_states
    probe.execute_original_subtask = execute_original_subtask
    try:
        probe.main()
    except Exception:
        output = _output_argument()
        if output is not None:
            output.mkdir(parents=True, exist_ok=True)
            (output / "startup_dependency_audit.json").write_text(
                json.dumps({**dependency_audit, "traceback": traceback.format_exc()}, indent=2) + "\n"
            )
        raise
    finally:
        output = _output_argument()
        if output is not None:
            output.mkdir(parents=True, exist_ok=True)
            path = output / "startup_dependency_audit.json"
            if not path.exists():
                path.write_text(json.dumps(dependency_audit, indent=2) + "\n")


if __name__ == "__main__":
    main()
