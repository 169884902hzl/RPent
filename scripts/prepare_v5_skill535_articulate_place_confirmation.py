"""Register independent original LIBERO-90 articulate/place confirmation pools.

This is a CPU-only preparation step.  It reads only explicitly named standard
LIBERO metadata and the previously registered access/reservation indexes.  The
result is a diagnostic manifest; it does not execute physics and never assigns
a success label.  The runtime probe receives the case binding metadata but its
public state is still produced from measured entities and never from BDDL or
simulator coordinates.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
from collections import Counter, defaultdict
from pathlib import Path
from typing import Iterable

SUITE = "libero_90"
STATE_ENCODING = "C contiguous little endian float64"
ARMS = ("current160", "vla_subtask160")

# The lists are intentionally explicit.  Every selected task is an original
# LIBERO-90 task whose language contains the corresponding operation.  States
# 10--39 are reserved by convention for independent confirmation when enough
# tasks exist; microwave uses all 50 states of tasks 33 and 35 because those are
# the only two original microwave tasks (and are explicitly reserved in 529).
FIXTURE_SELECTIONS = {
    "drawer_open": [(6, range(10, 40)), (7, range(10, 40)),
                    (8, range(10, 40)), (11, range(10, 20))],
    "drawer_close": [(0, range(10, 40)), (22, range(10, 40)),
                     (23, range(10, 40)), (28, range(10, 20))],
    "microwave_open": [(33, range(50)), (35, range(50))],
    "microwave_close": [(33, range(50)), (35, range(50))],
    "stove_turn_on": [(44, range(50)), (20, list(range(0, 10)) + list(range(40, 50))),
                      (45, list(range(0, 10)) + list(range(40, 50))),
                      (21, list(range(0, 5)) + list(range(40, 45)))],
    "stove_turn_off": [(39, range(50)), (44, range(30)),
                       (20, list(range(0, 10)) + list(range(40, 50)))],
}

PLACE_SELECTIONS = {
    "place_on": [(10, range(50)), (25, range(50))],
    "place_in": [(2, range(50)), (24, range(50))],
}


def identity(path: Path) -> dict:
    path = Path(path)
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(block)
    return {"path": str(path), "sha256": h.hexdigest()}


def load_pinned(path: Path, expected_sha: str | None = None):
    record = identity(path)
    if expected_sha is not None and record["sha256"] != expected_sha:
        raise ValueError(f"pinned input changed: {path}")
    return json.loads(path.read_text()), record


def canonical_state_sha(state) -> str:
    import numpy as np
    return hashlib.sha256(np.asarray(state, dtype="<f8", order="C").tobytes()).hexdigest()


def _kind(symbol: str) -> str:
    from robots.libero.v5_oracle_policy import _kind as oracle_kind
    return oracle_kind(symbol)


def category(symbol: str, mode: str) -> str:
    """Convert a private BDDL symbol to the public category vocabulary."""
    kind = _kind(symbol)
    if kind in ("cabinet", "drawer"):
        part = next((part for part in ("top", "middle", "bottom")
                     if f"_{part}_region" in symbol), None)
        if part is not None:
            return "cabinet top surface" if mode == "on" else f"cabinet {part} drawer"
    return kind


def _goal_mode(mode: str) -> str:
    return {"turn_on": "turnon", "turn_off": "turnoff"}.get(mode, mode)


def _goal_for(problem: dict, mode: str):
    target = _goal_mode(mode)
    for goal in problem.get("goal_state", []):
        if len(goal) >= 2 and goal[0] == target:
            return goal
    return None


def _fixture_symbol_goal(problem: dict, mode: str):
    """Resolve an explicit fixture symbol even when the original task's goal
    is the opposite endpoint (for example task35 starts closed and says
    ``open the microwave``).  The requested mode remains the case label and
    is what the private verifier checks after the action.
    """
    goal = _goal_for(problem, mode)
    source_mode = mode
    if goal is None:
        opposite = {"open": "close", "close": "open", "turn_on": "turn_off",
                    "turn_off": "turn_on"}.get(mode)
        if opposite is not None:
            goal = _goal_for(problem, opposite)
            source_mode = opposite if goal is not None else mode
    return goal, source_mode


def _subtask_phrase(source_category: str, mode: str, target_category: str | None = None) -> str:
    from robots.libero.v5_subtasks import subtask_phrase
    return subtask_phrase(source_category, mode, target_category)


def _sha_for_original40(catalog: list[dict]) -> set[str]:
    return {digest for task in catalog for digest in task.get("state_sha256", [])}


def _state_sets_from_access(pools: dict, microwave_reserved: list[dict]):
    visited, reserved, reservation_sources = set(), set(), defaultdict(list)
    for group, rows in pools.items():
        if not isinstance(rows, list):
            continue
        for row in rows:
            digest = row.get("state_sha256")
            if not digest:
                continue
            if row.get("visited"):
                visited.add(digest)
            if row.get("reserved_by_explicit_prior_plan"):
                reserved.add(digest)
                reservation_sources[digest].append(f"pools/{group}")
    # The microwave reservation file intentionally claims all 100 states.
    microwave = set()
    for row in microwave_reserved:
        digest = row.get("state_sha256")
        if digest:
            microwave.add(digest)
            reserved.add(digest)
            reservation_sources[digest].append("microwave_open_close_reserved")
    return visited, reserved, microwave, reservation_sources


def _manifest_state_sets(paths: Iterable[Path]):
    seen = set()
    records = []
    for path in paths:
        plan, record = load_pinned(path)
        digests = {c["state_sha256"] for c in plan.get("cases", []) if c.get("state_sha256")}
        seen |= digests
        records.append({**record, "cases": len(plan.get("cases", [])),
                        "unique_state_sha": len(digests)})
    return seen, records


def _task_metadata(bench, task_id: int, roots: dict[str, Path], cache: dict[int, dict]):
    if task_id in cache:
        return cache[task_id]
    from libero.libero.envs.bddl_utils import robosuite_parse_problem
    task = bench.get_task(task_id)
    if task.problem_folder != SUITE:
        raise ValueError(f"task {task_id} is not from original {SUITE}")
    bddl = roots["bddl"] / task.problem_folder / task.bddl_file
    init_file = roots["init"] / task.problem_folder / task.init_states_file
    problem = robosuite_parse_problem(str(bddl))
    bddl_language = " ".join(problem.get("language_instruction", []))
    if bddl_language and bddl_language != task.language:
        raise ValueError(f"benchmark/BDDL language mismatch for task {task_id}")
    states = bench.get_task_init_states(task_id)
    cache[task_id] = {"task": task, "problem": problem, "bddl": identity(bddl),
                      "init_file": identity(init_file), "states": states,
                      "language": task.language, "trials": len(states)}
    return cache[task_id]


def _episode_rows(kind: str, selections: dict[str, list[tuple[int, Iterable[int]]]],
                  bench, roots: dict[str, Path], cache: dict[int, dict], *, mode_for,
                  state_reservations: set[str], visited: set[str], allow_microwave: set[str],
                  prior_state_hashes: set[str], original40_hashes: set[str]):
    rows, selected_digests, selected_by_label, overlap = [], set(), defaultdict(set), []
    for label in sorted(selections):
        mode = mode_for(label)
        requested = []
        for task_id, seeds in selections[label]:
            meta = _task_metadata(bench, task_id, roots, cache)
            goal, source_mode = (_fixture_symbol_goal(meta["problem"], mode)
                                 if kind == "articulate" else
                                 (_goal_for(meta["problem"], mode), mode))
            if kind == "articulate" and goal is None:
                raise ValueError(f"task {task_id} has no registered {mode} predicate for {label}")
            if kind == "place" and (goal is None or len(goal) < 3):
                raise ValueError(f"task {task_id} has no registered {mode} placement predicate")
            for seed in seeds:
                if not 0 <= seed < meta["trials"]:
                    raise ValueError(f"seed {seed} out of range for libero_90 task {task_id}")
                digest = canonical_state_sha(meta["states"][seed])
                if digest in selected_by_label[label]:
                    raise ValueError(f"duplicate state within confirmation selection: {label} {task_id}/{seed}")
                # A reset state may be used once for each distinct operation
                # label (e.g. microwave open and close), but never twice for
                # the same first-attempt denominator.
                selected_by_label[label].add(digest)
                selected_digests.add(digest)
                if digest in original40_hashes:
                    overlap.append({"type": label, "task": task_id, "seed": seed,
                                    "state_sha256": digest, "with": "skill500_original40_catalog"})
                if digest in prior_state_hashes:
                    overlap.append({"type": label, "task": task_id, "seed": seed,
                                    "state_sha256": digest, "with": "explicit_prior_manifest"})
                if digest in visited:
                    overlap.append({"type": label, "task": task_id, "seed": seed,
                                    "state_sha256": digest, "with": "original90_access529_visited"})
                if digest in state_reservations and digest not in allow_microwave:
                    overlap.append({"type": label, "task": task_id, "seed": seed,
                                    "state_sha256": digest, "with": "original90_reserved_pool"})
                requested.append((task_id, seed, digest, meta, goal))
        if len(requested) < 100:
            raise ValueError(f"{label} has only {len(requested)} independent states")
        # Keep exactly 100 deterministic rows per operation.  The explicit
        # selection lists above are already ordered and never post-select by outcome.
        requested = requested[:100]
        for trial, (task_id, seed, digest, meta, goal) in enumerate(requested):
            task = meta["task"]
            source = goal[1]
            target = goal[2] if len(goal) >= 3 else None
            source_category = category(source, mode)
            target_category = category(target, mode) if target else None
            prompt = (_subtask_phrase(source_category, mode, target_category)
                      if kind == "place" else
                      (f"{mode.replace('_', ' ')} the {source_category}"))
            setup = []
            if kind == "place":
                setup = [{"tool": "grasp", "object_symbol": source,
                          "object_category": source_category, "mode": "direct",
                          "required_public_receipt": "grasp_verified",
                          "private_diagnostic": "true_sustained_grasp_record_only"}]
            elif label.startswith("microwave_"):
                if label == "microwave_open" and task_id == 33:
                    setup = [{"tool": "articulate", "object_symbol": source,
                              "object_category": source_category, "mode": "close"}]
                elif label == "microwave_close" and task_id == 35:
                    setup = [{"tool": "articulate", "object_symbol": source,
                              "object_category": source_category, "mode": "open"}]
            elif label == "stove_turn_off" and task_id != 39:
                setup = [{"tool": "articulate", "object_symbol": source,
                          "object_category": source_category, "mode": "turn_on"}]
            row = {"name": f"{label}_libero_90_t{task_id}_s{seed}_r0_{kind}",
                   "episode": {"suite": SUITE, "task": task_id, "seed": seed},
                   "kind": kind, "type": label, "mode": mode,
                   "object_symbol": source, "object_category": source_category,
                   "subtask_prompt": prompt, "prompt_origin": "legal_original_LIBERO90_task_vocab",
                   "original_instruction": task.language, "setup": setup,
                   "condition": "PLACEHOLDER", "trial_index": trial,
                   "initial_state_repetition": 0, "official_init_index": seed,
                   "state_sha256": digest, "state_hash_encoding": STATE_ENCODING,
                   "bddl": meta["bddl"], "init_file": meta["init_file"],
                   "symbol_goal_source_mode": source_mode,
                   "private_metadata_use": "original-task diagnostic binding only; never state/candidate text",
                   "reservation_scope": "microwave task33/35 uses explicit 529 reservation" if digest in allow_microwave else "unreserved original90 state"}
            if target is not None:
                row.update(target_symbol=target, target_category=target_category)
            rows.extend(copy.deepcopy(row) for _ in ARMS)
            # Set conditions after cloning; names stay unique per arm.
            rows[-2]["condition"], rows[-1]["condition"] = ARMS
            rows[-2]["name"] += "_current160"
            rows[-1]["name"] += "_vla_subtask160"
    # Overlap is a hard preparation failure.  The only intentional reservation
    # reuse is the 529 microwave reservation, recorded in the manifest.
    invalid = [x for x in overlap if x["state_sha256"] not in allow_microwave]
    if invalid:
        sample = ", ".join(f"{x['type']}/t{x['task']}/s{x['seed']}:{x['with']}" for x in invalid[:5])
        raise ValueError(f"confirmation state overlap detected ({len(invalid)}): {sample}")
    return rows, selected_digests, overlap


def _conditions(max_chunks: int = 160) -> dict:
    controlled = {"vla_subtask_v1": True, "manual": "none", "skill_profile": "none",
                  "card": None, "legal_memory_manifest": None, "rpent_memory_index": None,
                  "deterministic_reset_v1": True, "dual_view_fusion_v1": True,
                  "fusion_depth_trim_v2": True, "measured_action_receipts_v1": True,
                  "measurement_progress_blocking_v1": True}
    return {
        "current160": {"executor": "current", "max_chunks": max_chunks,
                       "overrides": copy.deepcopy(controlled)},
        "vla_subtask160": {"executor": "vla_subtask", "max_chunks": max_chunks,
                           "contact_stop": "subtask_measurement_or_budget",
                           "grasp_early_stop": False, "overrides": copy.deepcopy(controlled)},
    }


def _plan(kind: str, rows: list[dict], *, base_config: dict, choice_package: str,
          catalog_file: dict, access_files: list[dict], overlap: list[dict],
          unique_states: set[str], prior_files: list[dict], source_script: dict):
    for row in rows:
        if row["kind"] != kind:
            raise ValueError("mixed skill kinds in one plan")
    counts = Counter(f"{r['type']}/{r['condition']}" for r in rows)
    return {
        "version": "original-libero90-skill535-confirmation/1",
        "base_config": base_config, "choice_package": choice_package,
        "original_task_catalog_file": catalog_file,
        "purpose": "independent original LIBERO-90 skill qualification diagnostic; no training or PRO data",
        "new_training_rows": 0, "runtime_default_changed": False,
        "pairing": "same original LIBERO-90 task/init and setup across current and vla_subtask arms",
        "state_repetition": "one physical first attempt per explicit task/init/arm; no repeated state within an arm",
        "confirmation": "only this complete independent batch may be used for 95/90/95 gates; all failures retained",
        "runtime_input": "public state/candidates contain measured entities only; BDDL/simulator truth remains private diagnostic metadata",
        "budget": {"max_chunks": 160, "actions_per_chunk": 5, "max_episode_steps": 10000,
                   "max_prompt_tokens": 3072},
        "metrics": {"truth_source": "private original-task predicate/joint state for diagnostics only",
                    "first_attempt_denominator": "all 100 preregistered states per operation and arm",
                    "articulate_success": "private requested predicate true after first attempt",
                    "place_success": "private requested placement predicate true after first attempt with verified grasp setup",
                    "public_null": "unmeasured; excluded from verifier precision/recall denominator",
                    "wilson": "binomial 95 percent intervals; state tuples are unique within this batch"},
        "conditions": _conditions(), "cases": rows,
        "preregistered_requests_by_type_arm": dict(counts),
        "qualification_authorized": False, "new_physical_trials": 0,
        "state_hash_encoding": STATE_ENCODING,
        "access_reservations": {"inputs": access_files, "prior_manifests": prior_files,
                                "selected_unique_state_sha": len(unique_states),
                                "overlap_records": overlap,
                                "intentional_microwave_reservation_reuse_unique_state_sha": len({
                                    x["state_sha256"] for x in overlap}),
                                "selection_has_no_outcome_filter": True},
        "producer": source_script,
        "selection": "explicit LIBERO-90 task IDs and seeds in this file; no score-based replacement",
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--libero-config-path", type=Path, required=True)
    parser.add_argument("--expected-asset-root", type=Path, required=True)
    parser.add_argument("--base-config", type=Path, required=True)
    parser.add_argument("--base-config-sha256", required=True)
    parser.add_argument("--choice-package", type=Path, required=True)
    parser.add_argument("--reservation-index", type=Path, required=True,
                        help="original90_access529 report/pools.json")
    parser.add_argument("--reservation-index-sha256", required=True)
    parser.add_argument("--microwave-reservation", type=Path, required=True)
    parser.add_argument("--microwave-reservation-sha256", required=True)
    parser.add_argument("--access-index", type=Path, required=True,
                        help="original90_access529 preparation/additional_index.json")
    parser.add_argument("--access-index-sha256", required=True)
    parser.add_argument("--original40-catalog", type=Path, required=True)
    parser.add_argument("--original40-catalog-sha256", required=True)
    parser.add_argument("--prior-manifest", type=Path, action="append", default=[],
                        help="prior/current independent manifest to exclude; repeatable")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError(f"output must be a new directory: {args.output}")
    os.environ["LIBERO_TYPE"] = "standard"
    os.environ["LIBERO_CONFIG_PATH"] = str(args.libero_config_path)
    base, base_file = load_pinned(args.base_config, args.base_config_sha256)
    if base.get("libero_type") != "standard":
        raise ValueError("only standard original LIBERO is accepted")
    if not (args.choice_package / "tokenizer_config.json").is_file():
        raise ValueError("choice package must contain tokenizer_config.json")
    pools, pools_file = load_pinned(args.reservation_index, args.reservation_index_sha256)
    microwave, microwave_file = load_pinned(args.microwave_reservation, args.microwave_reservation_sha256)
    access, access_file = load_pinned(args.access_index, args.access_index_sha256)
    catalog, catalog_file = load_pinned(args.original40_catalog, args.original40_catalog_sha256)
    if len(catalog) != 40:
        raise ValueError("original40 catalog must contain exactly 40 tasks")
    # Read the index's explicitly named reservation manifests.  Missing files
    # are fatal: silently losing an access ledger would invalidate the overlap audit.
    index_reserved_files = []
    for ref in access.get("reserved_manifests", []):
        p = Path(ref["path"])
        if not p.is_file():
            raise FileNotFoundError(f"registered reservation manifest is missing: {p}")
        _, rec = load_pinned(p, ref.get("sha256"))
        index_reserved_files.append(rec)
    visited, reserved, microwave_hashes, reservation_sources = _state_sets_from_access(pools, microwave)
    # The catalog itself is only used for an explicit original40 leakage check.
    original40_hashes = _sha_for_original40(catalog)
    prior_hashes, prior_files = _manifest_state_sets(args.prior_manifest)
    from libero.libero import get_libero_path
    from rlinf.envs.libero.utils import benchmark
    roots = {"bddl": Path(get_libero_path("bddl_files")).absolute(),
             "init": Path(get_libero_path("init_states")).absolute()}
    if any(not p.resolve().is_relative_to(args.expected_asset_root.resolve()) for p in roots.values()):
        raise ValueError("runtime original asset roots differ from the registered root")
    bench = benchmark.get_benchmark(SUITE)()
    cache: dict[int, dict] = {}
    fixture_rows, fixture_hashes, fixture_overlap = _episode_rows(
        "articulate", FIXTURE_SELECTIONS, bench, roots, cache,
        mode_for=lambda label: {"microwave_open": "open", "microwave_close": "close",
                                "stove_turn_on": "turn_on", "stove_turn_off": "turn_off"}.get(
                                    label, "open" if label == "drawer_open" else "close"),
        state_reservations=reserved, visited=visited, allow_microwave=microwave_hashes,
        prior_state_hashes=prior_hashes, original40_hashes=original40_hashes)
    place_rows, place_hashes, place_overlap = _episode_rows(
        "place", PLACE_SELECTIONS, bench, roots, cache,
        mode_for=lambda label: "on" if label == "place_on" else "in",
        state_reservations=reserved, visited=visited, allow_microwave=set(),
        prior_state_hashes=prior_hashes, original40_hashes=original40_hashes)
    source_script = identity(Path(__file__))
    access_files = [pools_file, microwave_file, access_file, *index_reserved_files]
    access_files.append({"path": str(args.original40_catalog), "sha256": catalog_file["sha256"]})
    fixture = _plan("articulate", fixture_rows, base_config=base_file,
                    choice_package=str(args.choice_package), catalog_file=catalog_file,
                    access_files=access_files, overlap=fixture_overlap,
                    unique_states=fixture_hashes, prior_files=prior_files,
                    source_script=source_script)
    place = _plan("place", place_rows, base_config=base_file,
                  choice_package=str(args.choice_package), catalog_file=catalog_file,
                  access_files=access_files, overlap=place_overlap,
                  unique_states=place_hashes, prior_files=prior_files,
                  source_script=source_script)
    # Keep a machine-readable inventory next to the two manifests.
    args.output.mkdir(parents=True, exist_ok=False)
    fixture_path, place_path = args.output / "fixtures.json", args.output / "place.json"
    fixture_path.write_text(json.dumps(fixture, ensure_ascii=False, indent=2) + "\n")
    place_path.write_text(json.dumps(place, ensure_ascii=False, indent=2) + "\n")
    registration = {"producer": source_script, "fixtures": identity(fixture_path),
                    "place": identity(place_path), "fixture_cases": len(fixture_rows),
                    "place_cases": len(place_rows), "fixture_unique_states": len(fixture_hashes),
                    "place_unique_states": len(place_hashes), "qualification_authorized": False,
                    "prior_manifests": prior_files, "access_inputs": access_files,
                    "node_binding": None, "dependency": None, "array_default": "0-7%8"}
    (args.output / "registration.json").write_text(json.dumps(registration, indent=2) + "\n")
    print(json.dumps(registration, indent=2))


if __name__ == "__main__":
    main()
