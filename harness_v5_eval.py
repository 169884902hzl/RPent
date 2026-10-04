# Copyright 2026 Zhilun Hu.
# SPDX-License-Identifier: Apache-2.0
"""Independent v5 runner; official predicates are evaluation-only outputs."""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import sys
import time
from pathlib import Path

from robots.libero.v5_state import (
    CHOICE_INSTRUCTION,
    MAX_PROMPT_TOKENS,
    VERSION,
    candidates,
    entity_record,
    prepare_request,
    serialize,
)
from robots.libero.v5_termination import V2_CATEGORIES, classify_v2

TERMINATION_CATEGORIES = (
    "completion_judgment",
    "no_legal_candidate",
    "perception_missing_object",
    "skill_execution_failure",
    "over_token",
    "budget_exhausted",
    "startup_error",
    "model_error",
) + V2_CATEGORIES


def _select_grasp_probe(choices, entities, category, mode, bind_action):
    """Keep original-task instance binding independent of the probed staging."""
    names = {e.id: e.name for e in entities}
    matching = [c for c in choices if c.tool == "grasp" and c.mode == mode
                and names.get(c.object) == category]
    if not matching:
        raise ValueError("original grasp probe category is not measured")
    if len(matching) == 1:
        return matching[0], 1
    bound = bind_action()
    # The task oracle normally chooses direct first. Its instance binding is
    # still valid for a diagnostic that requests above_10cm or yaw_90.
    action = next((c for c in matching if bound.tool == "grasp"
                   and c.object == bound.object), None)
    if action is None:
        raise ValueError("original task binder did not select the probed grasp category")
    return action, len(matching)


def _termination_category(
    result: dict,
    last_action,
    last_receipt: dict | None,
    last_binding: dict | None,
    *,
    loop_exhausted: bool,
    accounting_v2: bool = False,
    receipts: list[dict] | None = None,
) -> tuple[str, str]:
    """Return one mutually exclusive terminal cause and its evidence."""
    if accounting_v2 and result.get("official_success") and result.get("native_terminated"):
        return classify_v2(result, last_action, receipts or [])
    if result.get("status") in ("startup", "error"):
        error = str(result.get("error", ""))
        if result.get("error_stage") == "decision_service":
            return "model_error", error
        lowered = error.lower()
        if "token" in lowered or str(MAX_PROMPT_TOKENS) in lowered:
            return "over_token", error
        if result.get("status") == "startup":
            return "startup_error", error or "episode did not initialize"
        return "skill_execution_failure", error or "episode raised an error"
    if result.get("persist_attempts_v1"):
        return "budget_exhausted", "decision_or_episode_budget; help/finish requests did not terminate"
    if accounting_v2:
        classified = classify_v2(result, last_action, receipts or [])
        if classified is not None and not (classified[0] == "unresolved_ask_help" and last_binding is not None):
            return classified
    tool = getattr(last_action, "tool", None)
    if result.get("official_success") and tool == "finish":
        return "completion_judgment", "correct_completion"
    if tool == "finish":
        return "completion_judgment", "false_finish"
    if tool == "ask_help":
        if last_binding is None:
            return "no_legal_candidate", "model_selected_ask_help; no oracle binding evidence"
        binding = last_binding or {}
        if binding.get("source_entity") is None or (
            "target_entity" in binding and binding.get("target_entity") is None
        ):
            return "perception_missing_object", json.dumps(binding, sort_keys=True)
        return "no_legal_candidate", json.dumps(binding, sort_keys=True)
    if last_receipt and (
        last_receipt.get("verification") == "execution_error"
        or last_receipt.get("error")
    ):
        return "skill_execution_failure", str(last_receipt.get("error", ""))
    if loop_exhausted or result.get("native_truncated"):
        return "budget_exhausted", "decision_or_episode_budget"
    return "budget_exhausted", "decision loop ended without an explicit terminal action"


def _execute_action(executor, action, view, resolved_card, result):
    """Apply the same environment gate to direct and card-resolved choices."""
    effective = resolved_card if action.tool == "card_next" and resolved_card is not None else action
    if result["persist_attempts_v1"] and effective.tool == "ask_help":
        result["ask_help_attempts"] += 1
        receipt = executor.reject_terminal_action(effective)
    elif result["persist_attempts_v1"] and effective.tool == "finish" and not executor.p.env.terminated:
        result["rejected_finish_attempts"] += 1
        receipt = executor.reject_terminal_action(effective)
    else:
        receipt = executor.execute(action, card=view)
    if effective != action and not receipt.get("executed"):
        receipt["requested_tool"] = action.tool
    return receipt, effective


def run_episode(args: argparse.Namespace, collection=None) -> dict:
    """Run one measured-state episode without exposing simulator goals."""
    from transformers import AutoTokenizer

    from robots.libero.robot_spec import _init_runtime
    from robots.libero.toolkit import LiberoToolkit
    from robots.libero.v5_env_client import V5SkillEnvClient
    from robots.libero.v5_runtime import MeasuredScene, V5Executor, category
    from rpent.dashboard.events import NullDashboardEventSink
    from rpent.memory import MemoryManager
    from rpent.utils.daemon import ProcessDaemon, pick_free_port
    from rpent.utils.rpc import wait_for_ready
    from rpent.utils.rpc.http_rpc import HttpRpcClient
    from typed_choice_eval import ChoiceScorer

    output = args.output_dir
    output.mkdir(parents=True, exist_ok=False)
    started = time.perf_counter()
    sys.path.insert(0, str(args.choice_package))
    import parallel_schema

    tokenizer = AutoTokenizer.from_pretrained(
        args.choice_package, local_files_only=True
    )
    events = NullDashboardEventSink()
    sam_endpoint = getattr(args, "sam3_endpoint", None)
    sam = None
    if sam_endpoint is None:
        sam_port = pick_free_port()
        sam_endpoint = f"http://127.0.0.1:{sam_port}"
        sam = ProcessDaemon(
            name="v5_sam3",
            cmd=[
                sys.executable,
                "-m",
                "robots.libero.v5_sam3_server",
                "--transport",
                "http",
                "--host",
                "127.0.0.1",
                "--port",
                str(sam_port),
                "--parent-watch",
            ],
            log_path=str(output / "sam3_v5.log"),
        )
    daemons, toolkit, oracle_daemon = [], None, None
    executor = None
    result = {
        "version": VERSION,
        "suite": args.suite,
        "task": args.task,
        "seed": args.seed,
        "provider": args.provider,
        "mode": "engineering_smoke" if args.provider == "smoke" else "development",
        "official_success": False,
        "correct_finish": False,
        "status": "startup",
        "premature_finish_attempts": 0,
        "rejected_finish_attempts": 0,
        "ask_help_attempts": 0,
        "persist_attempts_v1": getattr(args, "persist_attempts_v1", False),
        "termination_category": None,
        "termination_detail": None,
    }
    config = vars(args).copy()
    config = {k: str(v) if isinstance(v, Path) else v for k, v in config.items()}
    (output / "config.json").write_text(json.dumps(config, indent=2))
    try:
        if sam is not None:
            sam.start()
        sam_rpc = HttpRpcClient(sam_endpoint)
        wait_for_ready(sam_rpc, daemon=sam, timeout_s=300)
        oracle_policy = None
        env_endpoint = None
        if args.provider != "oracle" and collection is None:
            env_port = pick_free_port()
            env_endpoint = f"http://127.0.0.1:{env_port}"
            oracle_daemon = ProcessDaemon(
                name="v5_measured_env",
                cmd=[
                    sys.executable,
                    "-m",
                    "robots.libero.v5_env_server",
                    "--suite",
                    args.suite,
                    "--task",
                    str(args.task),
                    "--seed",
                    str(args.seed),
                    "--max-episode-steps",
                    str(args.max_episode_steps),
                    "--port",
                    str(env_port),
                    "--parent-watch",
                ],
                log_path=str(output / "env_server.log"),
            )
            if getattr(args, "deterministic_reset_v1", False):
                oracle_daemon.cmd.append("--deterministic-reset-v1")
            if getattr(args, "motion_trace_v1", False):
                oracle_daemon.cmd.append("--motion-trace-v1")
            oracle_daemon.start()
            wait_for_ready(
                HttpRpcClient(env_endpoint), daemon=oracle_daemon, timeout_s=300
            )
        else:
            from robots.libero.v5_oracle_policy import OriginalOraclePolicy

            oracle_port = pick_free_port()
            env_endpoint = f"http://127.0.0.1:{oracle_port}"
            oracle_daemon = ProcessDaemon(
                name="v5_original_oracle",
                cmd=[
                    sys.executable,
                    "-m",
                    "robots.libero.v5_oracle_server",
                    "--suite",
                    args.suite,
                    "--task",
                    str(args.task),
                    "--seed",
                    str(args.seed),
                    "--max-episode-steps",
                    str(args.max_episode_steps),
                    "--port",
                    str(oracle_port),
                    "--parent-watch",
                ] + (["--counterfactual-spec", str(args.counterfactual_spec)]
                     if getattr(args, "counterfactual_spec", None) else [])
                  + (["--native-diagnostic"] if getattr(args, "native_termination_diagnostic", False) else []),
                log_path=str(output / "oracle_env.log"),
            )
            if getattr(args, "deterministic_reset_v1", False):
                oracle_daemon.cmd.append("--deterministic-reset-v1")
            if getattr(args, "motion_trace_v1", False):
                oracle_daemon.cmd.append("--motion-trace-v1")
            oracle_daemon.start()
            oracle_rpc = HttpRpcClient(env_endpoint)
            wait_for_ready(oracle_rpc, daemon=oracle_daemon, timeout_s=300)
            oracle_policy = OriginalOraclePolicy(oracle_rpc,
                persist_retries=(getattr(args, "oracle_persist_retries_v1", False)
                                 or result["persist_attempts_v1"]))
            result["oracle_persist_retries"] = oracle_policy.persist_retries
        runtime_args = argparse.Namespace(
            suite=args.suite,
            task=args.task,
            seed=args.seed,
            libero_type=args.libero_type,
            max_episode_steps=args.max_episode_steps,
            env_endpoint=env_endpoint,
            env_client_class=V5SkillEnvClient,
            vla_endpoint=getattr(args, "vla_endpoint", None),
            sam3_endpoint=sam_endpoint,
            molmo_endpoint=None,
            cuda_device=None,
            planner="typed_choice",
            collect_flywheel_data=False,
        )
        daemons, runtime = _init_runtime(runtime_args, output, events, None)
        toolkit = LiberoToolkit(
            runtime_kwargs=runtime,
            dashboard_events=events,
            memory=MemoryManager(output / "empty_memory", memory_access="read_only"),
            state_output_dir=output,
        )
        scene = MeasuredScene(toolkit, sam_rpc, args.seed,
                              furniture_parts_v1=getattr(args, "furniture_parts_v1", False),
                              instruction_queries_v1=getattr(args, "instruction_queries_v1", False),
                              wrist_recall_v1=getattr(args, "wrist_recall_v1", False),
                              fixture_support_filter_v1=getattr(args, "fixture_support_filter_v1", False),
                              fixture_front_geometry_v1=getattr(args, "fixture_front_geometry_v1", False),
                              fixture_identity_cache_v1=getattr(args, "fixture_identity_cache_v1", False),
                              dual_view_fusion_v1=getattr(args, "dual_view_fusion_v1", False),
                              fusion_depth_trim_v2=getattr(args, "fusion_depth_trim_v2", False),
                              shape_fit_v1=getattr(args, "shape_fit_v1", False),
                              shape_completion_v2=getattr(args, "shape_completion_v2", False),
                              occluded_measurement_cache_v2=getattr(args, "occluded_measurement_cache_v2", False),
                              fixture_drawer_clouds_v2=getattr(args, "fixture_drawer_clouds_v2", False),
                              fixture_part_visibility_v2=getattr(args, "fixture_part_visibility_v2", False),
                              fixture_handle_geometry_v3=getattr(args, "fixture_handle_geometry_v3", False),
                              fixture_endpoint_geometry_v3=getattr(args, "fixture_endpoint_geometry_v3", False),
                              microwave_recall_geometry_v3=getattr(args, "microwave_recall_geometry_v3", False),
                              microwave_instance_geometry_v4=getattr(args, "microwave_instance_geometry_v4", False),
                              appliance_support_crop_v5=getattr(args, "appliance_support_crop_v5", False),
                              microwave_door_cloud_v6=getattr(args, "microwave_door_cloud_v6", False),
                              door_point_recall_v7=getattr(args, "door_point_recall_v7", False),
                              door_plane_consensus_v1=getattr(args, "door_plane_consensus_v1", False),
                              region_anchor_cache_v1=getattr(args, "region_anchor_cache_v1", False),
                              record_sam_masks_v6=getattr(args, "v6_media", False) or getattr(args, "v6_perception_snapshot_v1", False))
        from robots.libero.v5_skill_profiles import load_profiles
        profile_kind = getattr(args, "skill_profile", "none")
        if collection is not None and profile_kind == "rpent":
            raise ValueError("RPent skill profiles are evaluation-only")
        profiles = load_profiles(profile_kind, Path(__file__).resolve().parent)
        if getattr(args, "legal_memory_manifest", None):
            from robots.libero.v5_skill_profiles import attach_legal_memory
            profiles = attach_legal_memory(profiles, Path(args.legal_memory_manifest),
                                          Path(__file__).resolve().parent)
        result["skill_profile"] = profiles
        executor = V5Executor(toolkit, scene, args.max_chunks, skill_profiles=profiles,
                             **{name: getattr(args, name, False) for name in (
                                 "target_cache_v1", "strict_place_v1", "strict_place_v2", "strict_place_v3", "strict_place_v4", "adjust_place_v1",
                                 "articulate_verification_v1", "grasp_approach_v1", "grasp_retry_v1",
                                 "grasp_local_prompt_v1", "grasp_short_prompt_v2", "in_release_clearance_v1",
                                 "selected_fixture_target_v1", "wrist_refine_v1", "wrist_measurement_standoff_v2", "wrist_geometry_prompt_v3", "grasp_rim_v1", "measured_rim_v2", "mug_rim_first_v3", "handle_free_yaw_v2",
                                 "grasp_lift_check_v2", "grasp_occlusion_scan_v1", "native_grasp_stop_v1", "view_retreat_v2", "retreat_clearance_v1", "articulate_verification_v2", "fixture_in_contact_v1", "grasp_clearance_v1", "fixture_part_prompt_v1", "articulate_view_retreat_v1", "held_occlusion_v1", "motion_outcome_v1", "motion_trace_v1", "grasp_safe_approach_v2", "wrist_position_hold_v1", "stagnation_recovery_v1")})
        if profiles is not None and profiles.get("failure_lessons"):
            executor.grasp_approach_v1 = True
            executor.grasp_retry_v1 = True
            executor.wrist_refine_v1 = True
        initial = toolkit.execute_tool("view_env_state", {}).result
        canonical_instruction = initial["task_language"]
        instruction = getattr(args, "instruction_override", canonical_instruction)
        executor.instruction = instruction
        scene.instruction = instruction
        from collections import Counter
        from robots.libero.v5_runtime import category, scene_vocabulary
        vocab = scene_vocabulary(initial["state"]["object_names"], instruction)
        scene.instance_limits = Counter(category(name) for name in initial["state"]["object_names"])
        scene.refresh(vocab)
        memory_card = None
        card_index = 0
        if getattr(args, "card", None):
            from robots.libero.v5_cards import validate_card
            memory_card = json.loads(Path(args.card).read_text())
            validate_card(memory_card)
            if collection is not None and memory_card["origin"] != "original_oracle":
                raise ValueError("RPent cards are evaluation-only")
            result["card_sha256"] = hashlib.sha256(Path(args.card).read_bytes()).hexdigest()
        memory_text = None
        from robots.libero.v5_manual import manual_text
        guidance, manual_files = manual_text(getattr(args, "manual", "none"), Path(__file__).resolve().parent,
            variables={"memory_empty":not bool(getattr(args,"rpent_memory_index",None)),
                       "suite":args.suite,"task":str(args.task),"seed":str(args.seed),
                       "output_dir":str(output),"recipe_tag":f"{args.suite}_t{args.task}_s{args.seed}",
                       "memory_dir":"memory","reference_tag":f"{args.suite.removeprefix('libero_')}_t{args.task}_s0"})
        if collection is not None and getattr(args, "manual", "none") == "rpent":
            raise ValueError("RPent manuals are evaluation-only")
        result["manual"] = {"kind": getattr(args, "manual", "none"),
                            "files": {str(p.relative_to(Path(__file__).resolve().parent)):hashlib.sha256(p.read_bytes()).hexdigest() for p in manual_files},
                            "content_transformed": False, "content_truncated": False}
        if getattr(args, "rpent_memory_index", None):
            if collection is not None or args.provider != "qwen27":
                raise ValueError("Original RPent memory is only for the Qwen27 evaluation arm")
            from robots.libero.v5_rpent_memory import read_original_files
            memory_text, memory_evidence = read_original_files(Path(args.rpent_memory_index))
            result["rpent_original_memory"] = memory_evidence
        if guidance is not None:
            if args.provider != "qwen27":
                raise ValueError("large-model manual text requires Qwen27; small models use skill parameters")
            memory_text = guidance + ('\n\n'+memory_text if memory_text is not None else '')
        scorer = (
            None
            if args.provider in ("smoke", "oracle")
            else ChoiceScorer(args.provider, args.choice_endpoint, memory_text=memory_text,
                              goal_done_diagnostic=getattr(args, "goal_done_diagnostic", False))
        )
        rng = random.Random(args.seed)
        (output / "initial_measurements.json").write_text(
            json.dumps(
                {
                    "entities": [entity_record(e) for e in scene.entities.values()],
                    "segmentation_calls": scene.calls,
                    "perception_s": scene.perception_s,
                },
                indent=2,
            )
        )
        result.update(status="running", initialization_s=time.perf_counter() - started)
        last_action = None
        last_receipt = None
        last_choices = []
        from robots.libero.v5_recovery import MeasuredRecovery
        recovery = MeasuredRecovery() if getattr(args, "stagnation_recovery_v1", False) else None
        with (output / "choices.jsonl").open("w") as trace:
            for decision in range(args.max_decisions):
                step_started = time.perf_counter()
                if getattr(args, "v6_media", False) or getattr(args, "v6_perception_snapshot_v1", False):
                    executor.capture()
                    scene.refresh(sorted(scene.vocabulary))
                entities = list(scene.entities.values())
                if recovery is not None:
                    executor.public_recovery = recovery.status()
                    recovery_before = recovery.snapshot(entities, executor.held, executor.p._last_obs_gripper)
                fixture_evidence_before = dict(scene.fixture_measurement_evidence)
                perception_evidence_before = dict(scene.perception_evidence)
                robot_measurement_before = {"eef_xyz": [float(x) for x in executor.p._last_obs_eef_pos],
                                            "gripper_opening": float(executor.p._last_obs_gripper)}
                decision_frame_step = toolkit._state.latest_step
                from robots.libero.v5_cards import card_view, resolve_card, advance_card
                view = card_view(memory_card, card_index)
                resolved_card = resolve_card(view, entities, executor.held) if view else None
                choices = candidates(
                    entities,
                    instruction,
                    tuple(executor.p._last_obs_eef_pos),
                    executor.held,
                    executor.receipts,
                    rng,
                    card=view,
                    adjust_place=getattr(args, "adjust_place_v1", False),
                    persist_attempts=getattr(args, "persist_attempts_v1", False),
                    finish_rejections=result["rejected_finish_attempts"],
                    recovery_status=executor.public_recovery,
                    execution_error_cooldown=getattr(args, "execution_error_cooldown_v1", False),
                    use_cached_measurements=getattr(args, "occluded_measurement_cache_v2", False),
                )
                if (getattr(args, "execution_error_cooldown_v1", False)
                    and resolved_card is not None):
                    from robots.libero.v5_state import execution_error_blocked
                    if execution_error_blocked(resolved_card, executor.receipts):
                        choices = [c for c in choices if c.tool != "card_next"]
                if (getattr(args, "persist_attempts_v1", False)
                    and result["rejected_finish_attempts"] >= 2
                    and resolved_card is not None and resolved_card.tool == "finish"):
                    choices = [c for c in choices if c.tool != "card_next"]
                last_choices = choices
                context = serialize(
                    instruction,
                    entities,
                    executor.p._last_obs_gripper,
                    executor.held,
                    executor.receipts,
                    card=view,
                    view_axes=scene.view_axes,
                    choices=choices,
                    failure_counts=getattr(args, "candidate_failure_counts_v1", False),
                    recovery_status=executor.public_recovery,
                )
                try:
                    request, tokens = prepare_request(
                        tokenizer, parallel_schema.prepare_prompts, context, choices
                    )
                except ValueError as error:
                    (output / "rejected_request.json").write_text(json.dumps({
                        "decision": decision, "context": context,
                        "instruction": CHOICE_INSTRUCTION,
                        "options": [c.text() for c in choices],
                        "error": str(error), "truncated": False,
                    }, indent=2))
                    raise
                model_started = time.perf_counter()
                decision_media = None
                media_pair = None
                if getattr(args, "v6_media", False):
                    if args.provider != "systemone":
                        raise ValueError("--v6-media requires the local System One extension")
                    from robots.libero.v6_som import render_pair, wire_media
                    frame = toolkit._state.latest_record()
                    media_pair = render_pair(output, decision_frame_step, list(frame.artifacts),
                                             [entity_record(e) for e in entities],
                                             output / "decision_media" / f"{decision:04d}",
                                             perception_evidence=perception_evidence_before)
                    decision_media = wire_media(media_pair)
                localization_reference = None
                if oracle_policy is not None and getattr(args, "localization_diagnostic_v1", False):
                    localization_reference = oracle_rpc.call("oracle.measurement_reference", timeout_s=120)
                if args.provider == "oracle":
                    probe = getattr(args, "grasp_probe_category", None)
                    if probe:
                        probe_mode = getattr(args, "grasp_probe_mode", "direct")
                        action, matching_count = _select_grasp_probe(
                            choices, entities, probe, probe_mode,
                            lambda: oracle_policy.choose(
                                entities, choices, executor.held, executor.receipts,
                                canonical_instruction, scene.view_axes,
                                native_success=toolkit.solved()),
                        )
                        oracle_policy.last_binding = {**(oracle_policy.last_binding or {}),
                            "scope":"original_single_skill_diagnostic", "category":probe,
                            "mode":probe_mode,
                            "measured_matching_count":matching_count}
                    else:
                        action = oracle_policy.choose(
                        entities,
                        choices,
                        executor.held,
                        executor.receipts,
                        canonical_instruction,
                        scene.view_axes,
                        native_success=toolkit.solved(),
                        )
                    probe_mode = getattr(args, "first_grasp_probe_mode", None)
                    if probe_mode is not None and action.tool == "grasp":
                        action = next(c for c in choices if c.tool == "grasp"
                                      and c.object == action.object and c.mode == probe_mode)
                    answer = {
                        "selected": choices.index(action),
                        "probabilities": None,
                        "model": "original-measured-script-expert",
                        "model_inference_s": 0.0,
                    }
                elif scorer is None:
                    if executor.held:
                        options = [
                            c
                            for c in choices
                            if c.tool == "place"
                            and args.smoke_target in scene.entities[c.target].name
                        ]
                    elif executor.receipts and executor.receipts[-1].get(
                        "place_verified"
                    ):
                        options = [c for c in choices if c.tool == "finish"]
                    else:
                        options = [
                            c
                            for c in choices
                            if c.tool == "grasp"
                            and args.smoke_object in scene.entities[c.object].name
                            and c.mode == "direct"
                        ]
                    if not options:
                        raise ValueError(
                            "smoke category has no measured feasible candidate"
                        )
                    action = options[0]
                    answer = {
                        "selected": choices.index(action),
                        "probabilities": None,
                        "model": "scripted-engineering-smoke",
                        "model_inference_s": 0.0,
                    }
                else:
                    result["error_stage"] = "decision_service"
                    answer = (scorer.score(**request, media=decision_media) if decision_media is not None
                              else scorer.score(**request))
                    if getattr(args, "success_top3_v1", False):
                        if args.provider != "systemone" or decision_media is not None:
                            raise ValueError("--success-top3-v1 uses the diagnosed text-only local v5 model")
                        from robots.libero.v5_success_choice import rerank_grasp
                        answer = rerank_grasp(args.choice_endpoint, context, request["options"], answer)
                    if args.provider == "jev" and answer.get("model") != "jev-1.13.0":
                        raise ValueError("Jev response differs from frozen jev-1.13.0")
                    index = int(answer["selected"])
                    if not 0 <= index < len(choices):
                        raise ValueError("choice index out of bounds")
                    action = choices[index]
                    result.pop("error_stage", None)
                choice_s = time.perf_counter() - model_started
                collected = None
                if collection is not None:
                    # A private expert labels model-visited original states;
                    # it never replaces the action returned by the scorer.
                    expert_action = action if args.provider == "oracle" else oracle_policy.choose(
                        entities, choices, executor.held, executor.receipts,
                        canonical_instruction, scene.view_axes, native_success=toolkit.solved(),
                    )
                    collected = collection.before_action(
                        args, decision, request, action, choices, scene, executor,
                        toolkit, oracle_rpc, oracle_policy, tokenizer, parallel_schema,
                        card=view, expert_action=expert_action,
                    )
                perception_before = scene.perception_s
                execution_started = time.perf_counter()
                persistence = getattr(args, "persist_attempts_v1", False)
                receipt, effective_action = _execute_action(
                    executor, action, view, resolved_card, result
                )
                if getattr(args, "v6_media", False) or getattr(args, "v6_perception_snapshot_v1", False):
                    executor.capture()
                    scene.refresh(sorted(scene.vocabulary))
                last_receipt = receipt
                if recovery is not None:
                    recovery.observe(effective_action, recovery_before,
                                     recovery.snapshot(scene.entities.values(), executor.held, executor.p._last_obs_gripper))
                    executor.public_recovery = recovery.status()
                    result["measured_recovery"] = {**recovery.status(), "ineffective_actions": recovery.ineffective_actions}
                action_total_s = time.perf_counter() - execution_started
                perception_s = scene.perception_s - perception_before
                predicate_evidence = None
                if oracle_policy is not None and receipt.get("tool") in ("place", "adjust_place"):
                    status = oracle_rpc.call("oracle.status", timeout_s=120)
                    matching = [bool(satisfied) for goal, satisfied in zip(status["goals"], status["satisfied"])
                                if len(goal) == 3 and goal[0] == receipt.get("mode")
                                and oracle_policy._bindings.get(goal[1]) == receipt.get("object")
                                and oracle_policy._bindings.get(goal[2]) == receipt.get("target")]
                    predicate_evidence = {"judge": "measured_predicate", "scope": "original_task_labels_only",
                                          "matching_predicate_count": len(matching),
                                          "physical_placement_predicate": matching[0] if len(matching) == 1 else None}
                elif oracle_policy is not None and receipt.get("tool") == "articulate":
                    status = oracle_rpc.call("oracle.status", timeout_s=120)
                    matching = [bool(satisfied) for goal, satisfied in zip(status["goals"], status["satisfied"])
                                if len(goal) == 2 and goal[0] == receipt.get("mode")
                                and oracle_policy._bindings.get(goal[1]) == receipt.get("object")]
                    if not matching and oracle_policy.last_binding.get("source_entity") == receipt.get("object"):
                        # The original expert can select a unique cabinet for
                        # its named drawer. Multiple same-mode goals remain
                        # ambiguous and are not silently assigned a label.
                        matching = [bool(satisfied) for goal, satisfied in zip(status["goals"], status["satisfied"])
                                    if len(goal) == 2 and goal[0] == receipt.get("mode")]
                    predicate_evidence = {"judge": "measured_predicate", "scope": "original_task_labels_only",
                                          "matching_predicate_count": len(matching),
                                          "physical_articulation_predicate": matching[0] if len(matching) == 1 else None}
                http_decision = args.provider in ("jev", "qwen27") or str(answer.get("model", "")).startswith("jev-")
                record = {
                    "decision": decision,
                    "decision_frame_step": decision_frame_step,
                    "post_frame_step": toolkit._state.latest_step,
                    "media_pair": media_pair,
                    "request": request,
                    "prompt_tokens": tokens,
                    "candidates": [c.text() for c in choices],
                    "answer": answer,
                    "selected": action.text(),
                    "receipt": receipt,
                    "verification_measurements": executor.last_verification_measurements,
                    "motion_evidence": executor.motion_evidence,
                    "skill_profile_evidence": executor.last_skill_profile_evidence,
                    "predicate_verification_evidence": predicate_evidence,
                    "memory_card": view,
                    "measurements": [entity_record(e) for e in entities],
                    "fixture_measurement_evidence": fixture_evidence_before,
                    "perception_measurement_evidence": perception_evidence_before,
                    "robot_measurement": robot_measurement_before,
                    "post_robot_measurement": {"eef_xyz": [float(x) for x in executor.p._last_obs_eef_pos],
                                               "gripper_opening": float(executor.p._last_obs_gripper)},
                    "post_fixture_measurement_evidence": dict(scene.fixture_measurement_evidence),
                    "post_perception_measurement_evidence": dict(scene.perception_evidence),
                    "rejected_fixture_measurements": list(scene.rejected_fixture_measurements),
                    "post_measurements": [
                        entity_record(e) for e in scene.entities.values()
                    ],
                    "post_request": {
                        **request,
                        "context": serialize(
                            instruction,
                            list(scene.entities.values()),
                            executor.p._last_obs_gripper,
                            executor.held,
                            executor.receipts,
                            card=view,
                            view_axes=scene.view_axes,
                            choices=choices,
                            failure_counts=getattr(args, "candidate_failure_counts_v1", False),
                            recovery_status=executor.public_recovery,
                        ),
                    },
                    "official_success": toolkit.solved(),
                    "timing_s": {
                        "model_inference": answer.get("model_inference_s"),
                        "http_round_trip": answer.get("http_round_trip_s"),
                        "decision_inference": answer.get("http_round_trip_s",answer.get("choice_http_round_trip_s"))
                        if http_decision
                        else answer.get("model_inference_s"),
                        "decision_inference_kind": "http_round_trip"
                        if http_decision
                        else "server_compute",
                        "choice_request": choice_s,
                        "perception": perception_s,
                        "execution": action_total_s - perception_s,
                        "total": time.perf_counter() - step_started,
                    },
                }
                if "goal_done_diagnostic" in answer:
                    # Diagnosis concerns the pre-action state. Keep it outside
                    # executor.receipts and the registered model-visible state.
                    record["diagnostic_receipt"] = answer["goal_done_diagnostic"]
                if oracle_policy is not None:
                    record["oracle_annotation"] = dict(oracle_policy.last_binding)
                    if getattr(args, "native_termination_diagnostic", False):
                        record["native_termination_diagnostic"] = oracle_rpc.call(
                            "oracle.status", timeout_s=120)
                    if localization_reference is not None:
                        record["localization_diagnostic"] = {
                            "scope": "original_task_private_labels_only",
                            "reference": localization_reference,
                            "reference_after": oracle_rpc.call(
                                "oracle.measurement_reference", timeout_s=120
                            ),
                            "bindings": dict(oracle_policy._bindings),
                        }
                if args.done_gated:
                    # Oracle termination is private collection control, not
                    # another observation or a planner-visible receipt field.
                    record["collection_control"] = {
                        "expert_done": toolkit.solved(),
                        "premature_finish_negative": effective_action.tool == "finish"
                        and not toolkit.solved(),
                        "source": "original_official_predicate",
                    }
                    result["premature_finish_attempts"] += int(
                        record["collection_control"]["premature_finish_negative"]
                    )
                trace.write(json.dumps(record, ensure_ascii=True) + "\n")
                trace.flush()
                if collection is not None:
                    collection.after_action(collected, record, scene, executor, oracle_rpc)
                if advance_card(view, action, receipt, resolved_card):
                    card_index += 1
                last_action = action
                result["decisions"] = decision + 1
                result["native_terminated"] = executor.p.env.terminated
                result["native_truncated"] = executor.p.env.truncated
                if persistence and collection is None:
                    if executor.p.env.truncated or (toolkit.solved() and executor.p.env.terminated):
                        break
                    continue
                if args.done_gated:
                    if executor.p.env.truncated or (
                        toolkit.solved() and (collection is None or action.tool == "finish")
                    ):
                        break
                    continue
                if action.tool in ("finish", "ask_help") or executor.p.env.truncated:
                    break
                if executor.p.env.terminated:
                    # Preserve the model's explicit terminal choice after physical
                    # completion; control actions need no further simulator steps.
                    continue
        result.update(
            status="completed",
            official_success=toolkit.solved(),
            correct_finish=bool(
                toolkit.solved() and last_action and last_action.tool == "finish"
            ),
            false_finish=bool(
                not getattr(args, "persist_attempts_v1", False)
                and not toolkit.solved() and last_action and last_action.tool == "finish"
            ),
            budget_exhausted=bool(
                last_action
                and (
                    ((args.done_gated or getattr(args, "persist_attempts_v1", False)) and not toolkit.solved())
                    or last_action.tool not in ("finish", "ask_help")
                )
                and not (getattr(args, "persist_attempts_v1", False) and toolkit.solved())
            ),
            perception_calls=scene.calls,
            perception_s=scene.perception_s,
            native_terminated=executor.p.env.terminated,
            native_truncated=executor.p.env.truncated,
        )
        category_name, category_detail = _termination_category(
            result,
            last_action,
            last_receipt,
            getattr(oracle_policy, "last_binding", None),
            loop_exhausted=(result.get("decisions", 0) >= args.max_decisions),
            accounting_v2=getattr(args, "termination_accounting_v2", False),
            receipts=executor.receipts,
        )
        result["termination_accounting_version"] = (
            "v2" if getattr(args, "termination_accounting_v2", False) else "legacy"
        )
        result["termination_category"] = category_name
        result["termination_detail"] = category_detail
        if getattr(args, "persist_attempts_v1", False):
            result["termination_reason"] = "official_success" if result["official_success"] and result["native_terminated"] else "budget_exhausted"
        if category_name not in TERMINATION_CATEGORIES:
            raise AssertionError(f"unknown termination category: {category_name}")
        return result
    except Exception as error:
        result.update(status="error", error=f"{type(error).__name__}: {error}")
        if toolkit is not None and executor is not None:
            result.update(official_success=bool(toolkit.solved()),
                          native_terminated=bool(executor.p.env.terminated),
                          native_truncated=bool(executor.p.env.truncated))
        lowered = str(error).lower()
        if result.get("error_stage") == "decision_service":
            category_name = "model_error"
        elif "token" in lowered or str(MAX_PROMPT_TOKENS) in lowered:
            category_name = "over_token"
        elif "initialization_s" not in result and not result.get("decisions"):
            category_name = "startup_error"
        else:
            category_name = "skill_execution_failure"
        result["termination_category"] = category_name
        result["termination_detail"] = str(error)
        if getattr(args, "termination_accounting_v2", False) and result.get("official_success") and result.get("native_terminated"):
            result["termination_category"], result["termination_detail"] = classify_v2(result, None, [])
        raise
    finally:
        if toolkit is not None:
            toolkit.close()
        for daemon in reversed(daemons):
            daemon.stop()
        if oracle_daemon is not None:
            oracle_daemon.stop()
        if sam is not None:
            sam.stop()
        result["wall_s"] = time.perf_counter() - started
        result["source_hashes"] = {
            name: hashlib.sha256(
                (Path(__file__).resolve().parent / name).read_bytes()
            ).hexdigest()
            for name in (
                "harness_v5_eval.py",
                "robots/libero/v5_state.py",
                "robots/libero/v5_runtime.py",
                "robots/libero/v5_sam3_server.py",
                "robots/libero/v5_oracle_policy.py",
                "robots/libero/v5_oracle_server.py",
                "robots/libero/v5_env_server.py",
                "robots/libero/v5_reset_seed.py",
                "robots/libero/v5_env_client.py",
                "robots/libero/env_client.py",
                "robots/libero/robot_spec.py",
                "robots/libero/tools.py",
                "robots/libero/v5_termination.py",
                "robots/libero/v5_cards.py",
                "robots/libero/v5_fixture_parts.py",
                "robots/libero/v5_verification.py",
                "robots/libero/v5_systemone.py",
                "robots/libero/v6_som.py",
                "robots/libero/v5_success_choice.py",
                "robots/libero/v5_perception_geometry.py",
                "robots/libero/v5_manual.py",
                "robots/libero/v5_skill_profiles.py",
                "typed_choice_eval.py",
            )
        }
        (output / "result.json").write_text(json.dumps(result, indent=2))


def main() -> None:
    """Run a single bounded episode using its explicit output path."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--suite", default="libero_spatial")
    parser.add_argument("--task", type=int, default=0)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument(
        "--libero-type", choices=("standard", "pro"), default="standard"
    )
    parser.add_argument(
        "--provider",
        choices=("smoke", "oracle", "qwen4b", "dagger2323", "qwen27", "jev", "systemone"),
        default="smoke",
    )
    parser.add_argument("--choice-endpoint")
    parser.add_argument("--goal-done-diagnostic", action="store_true")
    parser.add_argument("--card", type=Path)
    parser.add_argument("--rpent-memory-index", type=Path)
    parser.add_argument("--sam3-endpoint")
    parser.add_argument("--vla-endpoint")
    parser.add_argument("--done-gated", action="store_true")
    parser.add_argument("--termination-accounting-v2", action="store_true")
    parser.add_argument("--persist-attempts-v1", action="store_true")
    parser.add_argument("--candidate-failure-counts-v1", action="store_true")
    parser.add_argument("--adjust-place-v1", action="store_true")
    for flag in ("furniture-parts-v1", "target-cache-v1", "strict-place-v1",
                 "articulate-verification-v1", "grasp-approach-v1", "grasp-retry-v1",
                 "instruction-queries-v1", "wrist-recall-v1", "fixture-support-filter-v1", "fixture-front-geometry-v1", "in-release-clearance-v1",
                 "fixture-identity-cache-v1"):
        parser.add_argument("--" + flag, action="store_true")
    parser.add_argument("--grasp-local-prompt-v1", action="store_true")
    parser.add_argument("--selected-fixture-target-v1", action="store_true")
    parser.add_argument("--dual-view-fusion-v1", action="store_true")
    parser.add_argument("--shape-fit-v1", action="store_true")
    parser.add_argument("--fixture-drawer-clouds-v2", action="store_true")
    parser.add_argument("--fixture-part-visibility-v2", action="store_true")
    parser.add_argument("--fixture-handle-geometry-v3", action="store_true")
    parser.add_argument("--fixture-endpoint-geometry-v3", action="store_true")
    parser.add_argument("--microwave-recall-geometry-v3", action="store_true")
    parser.add_argument("--microwave-instance-geometry-v4", action="store_true")
    parser.add_argument("--appliance-support-crop-v5", action="store_true")
    parser.add_argument("--microwave-door-cloud-v6", action="store_true")
    parser.add_argument("--door-point-recall-v7", action="store_true")
    parser.add_argument("--door-plane-consensus-v1", action="store_true")
    parser.add_argument("--region-anchor-cache-v1", action="store_true")
    parser.add_argument("--fixture-in-contact-v1", action="store_true")
    parser.add_argument("--grasp-clearance-v1", action="store_true")
    parser.add_argument("--fixture-part-prompt-v1", action="store_true")
    parser.add_argument("--articulate-view-retreat-v1", action="store_true")
    parser.add_argument("--held-occlusion-v1", action="store_true")
    parser.add_argument("--motion-outcome-v1", action="store_true")
    parser.add_argument("--motion-trace-v1", action="store_true")
    parser.add_argument("--stagnation-recovery-v1", action="store_true")
    parser.add_argument("--execution-error-cooldown-v1", action="store_true")
    parser.add_argument("--fusion-depth-trim-v2", action="store_true")
    parser.add_argument("--v6-media", action="store_true", help="Send measured Set-of-Mark dual images to local System One")
    parser.add_argument("--v6-perception-snapshot-v1", action="store_true", help="Save fresh dual-view entity masks and explicit decision frames for v6 collection")
    parser.add_argument("--success-top3-v1", action="store_true", help="Development: rerank grasp choices by pre-action success among top three")
    parser.add_argument("--grasp-safe-approach-v2", action="store_true")
    parser.add_argument("--wrist-position-hold-v1", action="store_true")
    parser.add_argument("--first-grasp-probe-mode", choices=("direct", "above_10cm", "yaw_90"))
    parser.add_argument("--shape-completion-v2", action="store_true")
    parser.add_argument("--occluded-measurement-cache-v2", action="store_true")
    parser.add_argument("--deterministic-reset-v1", action="store_true")
    parser.add_argument("--wrist-refine-v1", action="store_true")
    parser.add_argument("--wrist-measurement-standoff-v2", action="store_true")
    parser.add_argument("--wrist-geometry-prompt-v3", action="store_true")
    parser.add_argument("--grasp-short-prompt-v2", action="store_true")
    parser.add_argument("--grasp-rim-v1", action="store_true")
    parser.add_argument("--measured-rim-v2", action="store_true")
    parser.add_argument("--mug-rim-first-v3", action="store_true")
    parser.add_argument("--handle-free-yaw-v2", action="store_true")
    parser.add_argument("--articulate-verification-v2", action="store_true")
    parser.add_argument("--localization-diagnostic-v1", action="store_true")
    parser.add_argument("--native-termination-diagnostic", action="store_true")
    parser.add_argument("--grasp-lift-check-v2", action="store_true")
    parser.add_argument("--grasp-occlusion-scan-v1", action="store_true")
    parser.add_argument("--native-grasp-stop-v1", action="store_true")
    parser.add_argument("--view-retreat-v2", action="store_true")
    parser.add_argument("--retreat-clearance-v1", action="store_true")
    parser.add_argument("--grasp-probe-category")
    parser.add_argument("--grasp-probe-mode", choices=("direct", "above_10cm", "yaw_90"), default="direct")
    parser.add_argument("--manual", choices=("none", "general", "rpent"), default="none")
    parser.add_argument("--skill-profile", choices=("none", "general", "rpent"), default="none")
    parser.add_argument("--legal-memory-manifest", type=Path)
    parser.add_argument("--strict-place-v2", action="store_true")
    parser.add_argument("--strict-place-v3", action="store_true")
    parser.add_argument("--strict-place-v4", action="store_true")
    parser.add_argument("--oracle-persist-retries-v1", action="store_true")
    parser.add_argument("--choice-package", type=Path, required=True)
    parser.add_argument("--max-decisions", type=int, default=4)
    parser.add_argument("--max-episode-steps", type=int, default=3000)
    parser.add_argument("--max-chunks", type=int, default=40)
    parser.add_argument("--smoke-object", default="bowl")
    parser.add_argument("--smoke-target", default="plate")
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    if args.provider == "jev" and not args.choice_endpoint:
        parser.error("v5 Jev requires a pinned official evaluation relay endpoint")
    if args.provider in ("smoke", "oracle") and (
        args.libero_type != "standard"
        or args.suite
        not in ("libero_spatial", "libero_object", "libero_goal", "libero_10")
    ):
        parser.error("script experts are restricted to the 40 original tasks")
    if args.done_gated and (
        args.libero_type != "standard"
        or args.provider in ("smoke", "oracle", "jev")
        or args.suite
        not in ("libero_spatial", "libero_object", "libero_goal", "libero_10")
    ):
        parser.error("done-gated collection requires a local model on original tasks")
    run_episode(args)


if __name__ == "__main__":
    main()
