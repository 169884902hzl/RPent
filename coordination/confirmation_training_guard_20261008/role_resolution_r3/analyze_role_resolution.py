"""Check registration roles using pinned metadata only; never read outcome files."""

import argparse
import hashlib
import json
from pathlib import Path

ROOT = "/public/home/sunyihan/rpent_libero_eval"
REGISTRY = {
    "path": ROOT + "/results/harness_v5/place4311_public_trace_CPU_20261008/preparation_r2/confirmation_registry_r2/official_confirmation_exclusions.json",
    "sha256": "49273ed0e83a0183393f8771c77131ecf01c4478227878950c637443db035cdf",
}
SELECTION_SUCCESSORS = [
    {"path": ROOT + "/results/harness_v5/skill540_articulate_place_selection/preparation/fixtures.json",
     "sha256": "59cc228e9aa4aa49349009c639f3312e6044a60201f8834b0f223b62ddace387"},
    {"path": ROOT + "/results/harness_v5/skill540_articulate_place_selection/preparation/place.json",
     "sha256": "23e97aeda7ae28c44ba15c74c10d4c80e92f12fd8de49e17b17c37fdb00abe93"},
]
COORD_EVIDENCE = {
    "path": ROOT + "/coordination/confirmation_training_guard_20261008/role_resolution_r3/coord_registration_metadata.json",
    "sha256": "b48a688642b682271ebac99cb821a234a1a0450779ea71de9806c790c0ca0f40",
}
SKILL544_POOL = {
    "path": ROOT + "/results/harness_v5/skill544_confirmation_pools_CPU_20261006/pool_only_v2/report.json",
    "sha256": "cd4193bb2ba24e889f57cb5ef3d0b64f32e00c8c32b1bd653954d91eb60b7495",
}


def identity(path):
    path = Path(path).resolve(strict=True)
    return {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def load(reference):
    if not Path(reference["path"]).is_absolute() or identity(reference["path"]) != {k: reference[k] for k in ("path", "sha256")}:
        raise ValueError("Explicit metadata changed: " + reference["path"])
    return json.loads(Path(reference["path"]).read_text())


def state_identity(row):
    episode = row["episode"]
    return (episode["suite"], episode["task"], episode["seed"], row["state_sha256"])


def metadata(plan):
    allowed = ("schema", "version", "cohort", "purpose", "confirmation", "not_reserved",
        "pool_only", "training_allowed", "new_training_rows", "qualification_authorized",
        "protocol_role", "split", "registration_role", "confirmation_audit", "role")
    return {key: plan[key] for key in allowed if key in plan}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    registry = load(REGISTRY)
    producer_ref = registry["producer"]
    if identity(producer_ref["path"]) != producer_ref:
        raise ValueError("Pinned r2 producer changed")
    producer_text = Path(producer_ref["path"]).read_text()
    coverage_literals = [{"line": index, "text": line.strip()}
        for index, line in enumerate(producer_text.splitlines(), 1)
        if '"coverage_complete": False' in line]
    if not coverage_literals:
        raise ValueError("Expected the documented conservative coverage flag")
    coordination = load(COORD_EVIDENCE)
    if not any("32e11afe73db40727b6f9574e68be2127033c4fdd47f7ea355b3debe23987737" in r["text"]
            and "PANCONF_MANIFEST=" in r["text"] for r in coordination["lines"]):
        raise ValueError("Missing pan559 submission-to-pan556 metadata proof")
    pool544 = load(SKILL544_POOL)
    if pool544.get("pool_only") is not True or pool544.get("not_reserved") is not True:
        raise ValueError("Candidate pool role changed")
    registered = {state_identity(row) for row in registry["records"]}
    sources, union = [], set()
    for reference in registry["registration_sources"]:
        plan = load(reference)
        ids = {state_identity(row) for row in plan["cases"]}
        union.update(ids)
        sources.append({"reference": reference, "metadata": metadata(plan),
            "case_rows": len(plan["cases"]), "distinct_identities": len(ids),
            "identities_absent_from_r2": [list(row) for row in sorted(ids - registered)]})
    if union != registered:
        raise ValueError("R2 differs from its explicitly declared six-source union")
    supplement_ref = registry["registration_provenance_supplements"][0]
    provenance = load(supplement_ref)
    command_ref = provenance["command_reference"]
    command = load(command_ref)
    pool_ref = provenance["pool_reference"]
    pool = load(pool_ref)
    pool_ids = {state_identity(row) for row in pool["cases"]}
    provenance_check = {"supplement": supplement_ref, "command_reference": command_ref,
        "command": command, "explicit_manifest_arguments": provenance["497_explicit_manifest_arguments"],
        "claims_new_registration": provenance["497_has_new_registration_outside_existing_first4"],
        "pool_reference": pool_ref, "pool_cases": len(pool["cases"]),
        "pool_distinct_identities": len(pool_ids),
        "pool_identities_absent_from_r2": [list(row) for row in sorted(pool_ids - registered)],
        "actual_plan_group_pool_matches": provenance["existing_registered_plans"]}
    ambiguous, selection_ids = [], set()
    for old_reference, successor_reference in zip(registry["ambiguous_registration"], SELECTION_SUCCESSORS, strict=True):
        old_plan = load(old_reference)
        successor = load(successor_reference)
        old_ids = {state_identity(row) for row in old_plan["cases"]}
        new_ids = {state_identity(row) for row in successor["cases"]}
        selection_ids.update(old_ids)
        ambiguous.append({"legacy_reference": old_reference, "legacy_metadata": metadata(old_plan),
            "case_rows": len(old_plan["cases"]), "distinct_legacy_identities": len(old_ids),
            "explicit_role": "selection", "role_authority": "User 2026-10-06 item3: current160/vla_subtask160 comparison is a selection batch; separate disjoint confirmation follows method selection.",
            "requires_additional_user_or_Codex1_approval": False,
            "successor_reference": successor_reference, "successor_metadata": metadata(successor),
            "successor_case_rows": len(successor["cases"]), "successor_distinct_identities": len(new_ids),
            "successor_same_identity_set": old_ids == new_ids,
            "overlap_with_genuine_registered_confirmations": len(old_ids & registered),
            "permanent_confirmation_exclusion_from_legacy_name_or_declaration": False})
    hold_ref = registry["ambiguous_training_hold"]
    hold = load(hold_ref)
    hold_ids = {state_identity(row) for row in hold["records"]}
    if hold_ids != selection_ids:
        raise ValueError("Legacy role hold does not match the two named selection manifests")
    resolved = {"schema": "libero-selection-role-resolution/3", "producer": identity(__file__),
        "legacy_ambiguous_hold": hold_ref, "legacy_registry_preserved": REGISTRY,
        "authority": "User 2026-10-06 explicitly declares skill535 articulate1200/place400 selection batches; successor manifests confirm the same identities.",
        "role_gap_status": "resolved", "temporary_role_hold_effective": False,
        "unresolved_role_identities": [], "additional_approval_required": False,
        "distinct_selection_identities": len(selection_ids),
        "records": [{"episode": {"suite": row[0], "task": row[1], "seed": row[2]},
            "state_sha256": row[3], "registration_role": "selection", "temporary_role_hold_effective": False,
            "permanent_confirmation_exclusion_based_on_old_name": False}
            for row in sorted(selection_ids)],
        "other_registered_exclusions_unchanged": True, "training_or_skill_qualification_granted": False}
    resolved_path = args.output / "resolved_selection_role_registry.json"
    resolved_path.write_text(json.dumps(resolved, indent=2) + "\n")
    report = {"schema": "confirmation-registration-role-resolution/3", "producer": identity(__file__),
        "r2_registry": REGISTRY, "r2_producer": registry["producer"],
        "r2_producer_coverage_is_hardcoded_false": True, "r2_coverage_literal_evidence": coverage_literals,
        "coordination_metadata_evidence": COORD_EVIDENCE,
        "r2_coverage_complete": registry["coverage_complete"],
        "six_source_registration_rows": sum(r["case_rows"] for r in sources),
        "six_source_distinct_identities": len(registered), "sources": sources,
        "source_union_matches_r2_exactly": True, "genuine_confirmations_absent_from_r2_within_reviewed_six_sources": [],
        "495_497_provenance": provenance_check,
        "legacy_skill535_role_resolution": ambiguous, "resolved_selection_role_registry": identity(resolved_path),
        "role_only_hold": {"reference": hold_ref, "distinct_identities": len(hold_ids),
            "overlap_with_true_confirmation_identities": len(hold_ids & registered),
            "selection_identities_outside_true_confirmation_registry": len(hold_ids - registered),
            "can_close_role_ambiguity_without_approval": True,
            "role_gap_status": "resolved", "temporary_role_hold_effective": False,
            "unresolved_role_identities": [], "additional_approval_required": False,
            "note": "All 650 identities are resolved selection identities. A filename or old declaration cannot maintain a temporary role hold. Other exclusions and the existing skill qualification prerequisite are unchanged."},
        "skill544_candidate_pool": {"reference": SKILL544_POOL,
            "cohort": pool544["cohort"], "pool_only": True, "not_reserved": True,
            "is_registered_confirmation": False, "is_missing_confirmation_registration": False},
        "closed_gaps": ["skill535 articulate1200/place400 needs a fresh role approval",
            "495/497 may hide additional identities outside the pinned pool", "pan559/4246 is a new registry missing from pan556",
            "skill544 pool-only states are registered confirmations"],
        "actual_identified_missing_official_confirmation_registrations": [],
        "unproven_global_inventory": {"verified": False,
            "basis": "No authoritative exhaustive historical registration inventory was supplied or verified; a six-source list is not an exhaustive inventory.",
            "does_not_establish_an_actual_missing_registration": True,
            "new_user_or_Codex1_role_approval_required": False},
        "separate_layout_registry_note": "Moka580100-580199 have a separate permanent layout-exclusion contract. The unmodified official base tuples are not substitute confirmation identities, and this role review does not establish a missing layout registration.",
        "coverage_complete_after_this_role_review": False,
        "read_scope": "explicit registration plans, pool, submission command and selected coordination metadata only",
        "outcome_or_score_files_read": False, "GPU_used": False,
        "r1_r2_or_guard_source_modified": False, "no_artifact_directory_discovery": True}
    path = args.output / "report.json"
    path.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"report": identity(path), "registered": len(registered),
        "hold": len(hold_ids), "hold_true_confirmation_overlap": len(hold_ids & registered),
        "role_ambiguity_closed": True, "global_coverage_still_false": True}, indent=2))


if __name__ == "__main__":
    main()
