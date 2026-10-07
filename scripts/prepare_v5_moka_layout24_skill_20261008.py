"""Prepare, but do not submit, the approved 24-layout moka skill subcohort."""

import argparse
import copy
import hashlib
import json
from pathlib import Path
import shutil


def identity(path):
    path = Path(path).resolve(strict=True)
    return {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def read_pinned(reference):
    actual = identity(reference["path"])
    if actual["sha256"] != reference["sha256"]:
        raise ValueError("Pinned input changed")
    return json.loads(Path(actual["path"]).read_text())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--parent", type=Path, required=True)
    parser.add_argument("--parent-sha256", required=True)
    parser.add_argument("--baseline-audit", type=Path, required=True)
    parser.add_argument("--baseline-audit-sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    parent_ref = {"path": str(args.parent), "sha256": args.parent_sha256}
    audit_ref = {"path": str(args.baseline_audit), "sha256": args.baseline_audit_sha256}
    parent, audit = read_pinned(parent_ref), read_pinned(audit_ref)
    materialized = read_pinned(audit["materialized"])
    registry = read_pinned(audit["registry"])
    if audit["prepared_after_same_budget_baseline_audit"] != 24:
        raise ValueError("All approved layout declarations must be retained and prepared")
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    source = Path(parent["source_snapshot"]["path"])
    script_root = Path(__file__).parent
    dependencies = list(parent["producer_dependencies"])
    for name in ("preflight_v5_moka_layout24_CPU_20261008.py", "probe_v5_moka_layout24_20261008.py",
                 "serve_v5_moka_layout24_20261008.py"):
        shutil.copyfile(script_root / name, output / name)
        dependencies.append(identity(output / name))
    shutil.copyfile(args.parent.parent / "typed_choice_eval.py", output / "typed_choice_eval.py")
    dependencies.append(identity(output / "typed_choice_eval.py"))
    launcher_source = source / "scripts/run_v5_moka_transfer_public_smoke10_20261007.sbatch"
    launcher = launcher_source.read_text()
    changes = {
        "p['selection']['analysis_role']!='development_visited_state_smoke'": "p['selection']['analysis_role']!='registered_layout_confirmation24'",
        "len(p['cases'])!=10": "len(p['cases'])!=24",
        "Only the registered ten visited development states are authorized": "Only the registered 24 generated original layouts are authorized",
        'MOKA_TRANSFER_BASE="$MOKA_TRANSFER_ROOT/results/harness_v5/moka_transfer_confirmation_prep_CPU_20261007"': f'MOKA_TRANSFER_BASE="{output.parent}"',
        '"$MOKA_TRANSFER_SOURCE/scripts/v5_probe_preflight.py"': '"$MOKA_TRANSFER_PREP/preflight_v5_moka_layout24_CPU_20261008.py"',
        '"$MOKA_TRANSFER_SOURCE/scripts/probe_v5_moka_transfer_public_20261007.py"': '"$MOKA_TRANSFER_PREP/probe_v5_moka_layout24_20261008.py"',
    }
    for before, after in changes.items():
        if before not in launcher:
            raise ValueError("Registered launcher structure changed: " + before)
        launcher = launcher.replace(before, after)
    launcher_path = output / "run_moka_layout24.sbatch"
    launcher_path.write_text(launcher)
    dependencies.append(identity(launcher_path))
    generated = {record["name"]: record for record in materialized["records"]}
    verified = {record["name"]: record for record in audit["records"]}
    states_dir = output / "registered_states"
    states_dir.mkdir()
    cases = []
    for index, declared in enumerate(registry["layout_rules"]):
        record, check = generated[declared["name"]], verified[declared["name"]]
        raw = read_pinned(record["registered_layout_state"])
        raw["preparation_provenance"] = {
            "proposed_state_sha256": record["proposed_state_sha256"],
            "settled_state_sha256": record["state_sha256"],
            "settled_geometry": record["geometry_after"],
            "geometry_fingerprint": check["geometry_fingerprint"],
            "original_state_file": record["registered_layout_state"],
            "baseline_audit": audit_ref, "base_used": True,
        }
        raw_path = states_dir / f"{declared['name']}.json"
        raw_path.write_text(json.dumps(raw, indent=2, allow_nan=False) + "\n")
        case = copy.deepcopy(parent["cases"][0])
        case.update(name=declared["name"], episode=raw["episode"],
                    state_sha256=raw["state_sha256"], registered_layout_state=identity(raw_path),
                    geometry_fingerprint=check["geometry_fingerprint"],
                    source="preregistered_original_task19_layout_perturbation",
                    original_initial_state=False, base_used=True,
                    previously_used_for_selection=False, visited=False,
                    official_init_index=raw["episode"]["seed"], trial_index=index,
                    layout_seed=raw["layout_seed"], excluded_from_training=True)
        cases.append(case)
    plan = copy.deepcopy(parent)
    plan.update(cases=cases, purpose="Approved 24 generated original moka layouts, independent source stratum; insufficient for the100 threshold",
                selection={"analysis_role": "registered_layout_confirmation24", "confirmation": True,
                           "parent_selection": parent["selection"]["parent_selection"],
                           "layout_registry": audit["registry"]},
                producer=identity(__file__), producer_dependencies=dependencies,
                parent_runtime_manifest=parent_ref,
                preparation_inputs=[audit_ref, audit["materialized"], audit["registry"]],
                qualification_authorized=False, new_training_rows=0, new_confirmation_attempts=0,
                source_count={"official_unused": 0, "registered_layouts": 24,
                              "additional76_authorized": False, "additional76_included": 0},
                source_scope="24 layout states, not76 unused official states and not100 total; never declare skill qualification from this subcohort",
                repair={"fresh_startup_contract_required": True, "previous_contract_reusable": False},
                reset_contract="custom state restored in server reset before first client perception; raw sensors and controller goals rebuilt; private proposed/settled/restored geometry/SHA recorded",
                launcher_identity=identity(launcher_path), launcher_parent=identity(launcher_source),
                launcher_changes=changes, jobs_submitted=0)
    manifest = output / "moka_layout24.json"
    manifest.write_text(json.dumps(plan, indent=2, allow_nan=False) + "\n")
    handoff = {"manifest": identity(manifest), "launcher": identity(launcher_path),
               "source": str(source), "source_archive": plan["source_snapshot"]["archive"],
               "cases": 24, "source_scope": plan["source_scope"], "jobs_submitted": 0,
               "qualification": False, "first_physical_case": cases[0]["name"]}
    (output / "handoff.json").write_text(json.dumps(handoff, indent=2) + "\n")
    print(json.dumps(handoff, indent=2))


if __name__ == "__main__":
    main()
