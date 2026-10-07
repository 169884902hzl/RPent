"""Preregister the approved additional76 original-scene layouts, before physics."""

import argparse
import copy
import hashlib
import itertools
import json
from pathlib import Path


def identity(path):
    path = Path(path).resolve(strict=True)
    return {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def pinned(ref):
    if not Path(ref["path"]).is_absolute() or identity(ref["path"])["sha256"] != ref["sha256"]:
        raise ValueError("Pinned absolute metadata changed")
    return json.loads(Path(ref["path"]).read_text())


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--prior-layout-manifest", type=Path, required=True)
    parser.add_argument("--prior-layout-manifest-sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    prior_ref = {"path": str(args.prior_layout_manifest), "sha256": args.prior_layout_manifest_sha256}
    prior = pinned(prior_ref)
    registry_ref = prior["selection"]["layout_registry"]
    original = pinned(registry_ref)
    if len(prior["cases"]) != 24 or sorted(c["layout_seed"] for c in prior["cases"]) != list(range(580100, 580124)):
        raise ValueError("The immutable approved24 cohort is required")
    bases = sorted((r for r in original["official_state_audit"] if r["episode"] == {
        "suite": "libero_90", "task": 19, "seed": r["episode"]["seed"]}), key=lambda r: r["episode"]["seed"])
    if len(bases) != 50 or [r["episode"]["seed"] for r in bases] != list(range(50)):
        raise ValueError("All official task19 bases must be explicitly indexed")
    grid = list(itertools.product((-.015, -.005, .005, .015), (-.015, 0., .015), (-10., 10.)))
    rules = []
    for index in range(24, 100):
        dx, dy, yaw = grid[index % 24]
        base = copy.deepcopy(bases[index % 50])
        rule = copy.deepcopy(original["layout_rules"][0]["rule"])
        rule.update(version="moka-original-layout-preregistration/2-approved76",
                    layout_seed=580100+index, global_layout_index=index,
                    transform={"world_xy_translation_m": [dx, dy], "world_z_translation_m": 0.,
                               "world_yaw_delta_deg": yaw},
                    selection_rule="global index24..99; prior24 lexical grid[index%24]; official task19 base[index%50]; fixed before any settle/outcome; no replacement")
        rules.append({"name": f"moka_layout_{580100+index}", "rule": rule,
                      "rule_sha256": digest(rule), "base_official_state": base,
                      "base_used": True, "state_sha256": None, "registered_layout_state": None,
                      "status": "preregistered_before_physics", "official_initial_state": False,
                      "independent_physical_state_verified": False, "excluded_from_training": True,
                      "permanent_training_exclusion": True, "confirmation_run_authorized": False})
    # Parameters differ even when an already-used official base recurs.
    pairs = [(r["base_official_state"]["state_sha256"], digest(r["rule"]["transform"]))
             for r in original["layout_rules"]+rules]
    if len(set(pairs)) != 100:
        raise ValueError("A base/transform declaration is repeated")
    plan = copy.deepcopy(original)
    plan.update(version="moka-original-layout-preregistration/2-approved76", layout_rules=rules,
                prior_confirmation_manifest=prior_ref, prior_registration=registry_ref,
                producer=identity(__file__), permanent_training_exclusion=True,
                training_allowed=False, confirmation_layout_seeds=list(range(580100,580200)),
                new_layout_seeds=list(range(580124,580200)),
                future_training_layout_seed_range=[680100,689999], minimum_moka_xy_distance_m=.05,
                exclusion_distance_rule="future training layouts: settled world XY Euclidean distance >=.05m from EVERY confirmation layout; private metadata never enters policy",
                source_snapshot=prior["source_snapshot"],
                counts={"layout_rules_registered":76,"previous_layout_rules_registered":24,
                        "total_layout_rules_registered":100,"layout_rawstates_materialized":0},
                remaining_gaps=["rawstates, physical stabilization, geometric audit, and actual startup remain pending"])
    plan["policy"].update(physics_executed=0, jobs_submitted=0, new_training_rows=0,
                          outcome_files_read=False, confirmation_run_authorized=False,
                          base_policy="official task19 base[index%50], global index24..99; used generation bases only, no fresh official confirmation trials",
                          correlation="all100 generated layouts share original task/assets and reused official bases; not claimed IID")
    output=args.output.resolve(); output.mkdir(parents=True,exist_ok=False)
    for name,value in (("layout_rules76.json",rules),("manifest.json",plan)):
        (output/name).write_text(json.dumps(value,indent=2,allow_nan=False)+"\n")
    print(json.dumps({"registry":identity(output/"manifest.json"),"rules":76,
                      "physics_executed":0,"jobs_submitted":0,"training_allowed":False},indent=2))


if __name__ == "__main__":
    main()
