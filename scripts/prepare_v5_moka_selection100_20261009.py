"""Pin the corrected transfer recipe on retained original development states."""

import argparse
import copy
import hashlib
import json
from pathlib import Path
import shutil


def ref(path):
    path = Path(path).resolve(strict=True)
    return {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def pinned(item):
    if ref(item["path"])["sha256"] != item["sha256"]:
        raise ValueError("Pinned input changed: " + item["path"])
    return json.loads(Path(item["path"]).read_text())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--recipe", type=Path, required=True)
    parser.add_argument("--recipe-sha", required=True)
    parser.add_argument("--layouts76", type=Path, required=True)
    parser.add_argument("--layouts76-sha", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    recipe_ref = {"path": str(args.recipe), "sha256": args.recipe_sha}
    layouts_ref = {"path": str(args.layouts76), "sha256": args.layouts76_sha}
    recipe, layouts = pinned(recipe_ref), pinned(layouts_ref)
    previous24_ref = layouts["parent_runtime_manifest"]
    previous24 = pinned(previous24_ref)
    if len(recipe["cases"]) != 10 or len(layouts["cases"]) != 76 or len(previous24["cases"]) != 24:
        raise ValueError("Expected the original visited10 and retained24+76 plans")
    source = Path(recipe["source_snapshot"]["path"]).resolve(strict=True)
    for item in [*recipe["source_snapshot"]["files"], recipe["source_snapshot"]["archive"],
                 recipe["producer"], *recipe["producer_dependencies"]]:
        if ref(item["path"])["sha256"] != item["sha256"]:
            raise ValueError("Recipe source/dependency changed: " + item["path"])
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    dependencies = list(recipe["producer_dependencies"])
    for name in ("probe_v5_moka_layout24_20261008.py", "serve_v5_moka_layout24_20261008.py"):
        item = next(item for item in layouts["producer_dependencies"] if Path(item["path"]).name == name)
        if ref(item["path"])["sha256"] != item["sha256"]:
            raise ValueError("Layout adapter changed: " + name)
        shutil.copyfile(item["path"], output / name)
        dependencies.append(ref(output / name))
    shutil.copyfile(args.recipe.parent / "typed_choice_eval.py", output / "typed_choice_eval.py")
    dependencies.append(ref(output / "typed_choice_eval.py"))
    conditions = recipe["conditions"]
    if len(conditions) != 1:
        raise ValueError("Selection compares one fixed corrected recipe")
    method = next(iter(conditions))
    cases, invalid = [], []
    for case in [*previous24["cases"], *layouts["cases"]]:
        if case.get("preparation_valid", True) is False:
            invalid.append(copy.deepcopy(case))
            continue
        raw = pinned(case["registered_layout_state"])
        if raw["state_sha256"] != case["state_sha256"]:
            raise ValueError("Layout state differs from its registered case")
        case = copy.deepcopy(case)
        case.update(name="selection582_" + case["name"], condition=method,
                    previously_used_for_selection=True, excluded_from_training=True,
                    permanent_training_exclusion=True, confirmation=False)
        cases.append(case)
    if len(cases) != 98 or len(invalid) != 2:
        raise ValueError("Retained layout readiness differs; do not silently substitute states")
    for original in recipe["cases"][:2]:
        case = copy.deepcopy(original)
        case.update(name="selection582_" + case["name"], condition=method,
                    excluded_from_training=True, confirmation=False)
        cases.append(case)
    if len({c["state_sha256"] for c in cases}) != 100:
        raise ValueError("The selection100 states must have distinct raw-state hashes")
    for index, case in enumerate(cases):
        case["trial_index"] = index
    # Retain the existing launcher's real physical-startup contract and exit
    # semantics, replacing only this explicitly registered selection scope.
    old_launcher = source / "scripts/run_v5_moka_transfer_public_smoke10_20261007.sbatch"
    launcher = old_launcher.read_text()
    changes = {
        "p['selection']['analysis_role']!='development_visited_state_smoke'":
            "p['selection']['analysis_role']!='development_original_moka_selection100'",
        "len(p['cases'])!=10": "len(p['cases'])!=100",
        "Only the registered ten visited development states are authorized":
            "Only the registered original selection100 states are authorized",
        'MOKA_TRANSFER_BASE="$MOKA_TRANSFER_ROOT/results/harness_v5/moka_transfer_confirmation_prep_CPU_20261007"':
            f'MOKA_TRANSFER_BASE="{output.parent / "physical"}"',
        '"$MOKA_TRANSFER_SOURCE/scripts/v5_probe_preflight.py"':
            '"$MOKA_TRANSFER_PREP/preflight.py"',
        '"$MOKA_TRANSFER_SOURCE/scripts/probe_v5_moka_transfer_public_20261007.py"':
            '"$MOKA_TRANSFER_PREP/probe_v5_moka_layout24_20261008.py"',
    }
    for old, new in changes.items():
        if old not in launcher:
            raise ValueError("Launcher structure differs: " + old)
        launcher = launcher.replace(old, new)
    launcher_path = output / "run_selection100.sbatch"
    launcher_path.write_text(launcher)
    dependencies.append(ref(launcher_path))
    preflight = output / "preflight.py"
    preflight.write_text('''"""Use the same registered-state checks as the physical runner."""
import argparse
from pathlib import Path

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--manifest",type=Path,required=True)
    p.add_argument("--shard-index",type=int,default=0)
    p.add_argument("--shards",type=int,default=8)
    p.add_argument("--states",action="store_true")
    a=p.parse_args()
    from scripts import probe_v5_moka_transfer_public_20261007 as runner
    runner._bootstrap_registered_dependencies(a.manifest)
    from scripts.v5_probe_preflight import load_pinned_manifest,validate_registered_states,pinned_file
    _,plan,_=load_pinned_manifest(a.manifest)
    if len(plan["cases"])!=100 or plan["selection"]["analysis_role"]!="development_original_moka_selection100":
        raise ValueError("Wrong registered development scope")
    selected=plan["cases"][a.shard_index::a.shards]
    official=[c for c in selected if not c.get("registered_layout_state")]
    result=validate_registered_states(official)
    import hashlib,json,numpy as np
    for c in selected:
        item=c.get("registered_layout_state")
        if item is None: continue
        pinned_file(item,"registered_layout_state")
        raw=json.loads(Path(item["path"]).read_text())
        state=np.asarray(raw["rawstate"],dtype="<f8",order="C")
        if hashlib.sha256(state.tobytes()).hexdigest()!=c["state_sha256"] or raw["episode"]!=c["episode"]:
            raise ValueError("Registered layout state changed")
    print(json.dumps({"selected":len(selected),"official_audit":result,"physics_executed":False}))

if __name__=="__main__": main()
''')
    dependencies.append(ref(preflight))
    plan = copy.deepcopy(recipe)
    plan.update(cases=cases, producer=ref(__file__), producer_dependencies=dependencies,
                selection={"analysis_role": "development_original_moka_selection100",
                           "confirmation": False, "recipe": recipe_ref,
                           "retained_layouts": [previous24_ref, layouts_ref]},
                purpose="fixed corrected transfer selection:98 retained layouts and2 visited official states",
                qualification_authorized=False, training_allowed=False, new_training_rows=0,
                preparation_invalid_cases_retained=invalid,
                original_layout_declarations=100, valid_layout_trials=98, official_trials=2,
                retained_states_are_independent_confirmation=False,
                launcher_identity=ref(launcher_path), launcher_parent=ref(old_launcher),
                launcher_changes=changes, jobs_submitted=0)
    path = output / "selection100.json"
    path.write_text(json.dumps(plan, indent=2, allow_nan=False) + "\n")
    handoff = {"manifest": ref(path), "launcher": ref(launcher_path),
               "source": str(source), "physical_trials": 100,
               "retained_invalid_preparations": 2, "training_allowed": False,
               "confirmation": False, "new_confirmation_seeds_consumed": 0}
    (output / "handoff.json").write_text(json.dumps(handoff, indent=2) + "\n")
    print(json.dumps(handoff))


if __name__ == "__main__":
    main()
