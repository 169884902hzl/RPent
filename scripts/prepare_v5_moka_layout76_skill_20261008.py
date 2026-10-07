"""Prepare approved76 using immutable582r2 and the approved24 launcher family."""

import argparse
import copy
import hashlib
import json
from pathlib import Path
import shutil


def identity(path):
    path=Path(path).resolve(strict=True)
    return {"path":str(path),"sha256":hashlib.sha256(path.read_bytes()).hexdigest()}


def pinned(ref):
    if not Path(ref["path"]).is_absolute() or identity(ref["path"])["sha256"]!=ref["sha256"]:
        raise ValueError("Pinned absolute input changed: "+ref["path"])
    return json.loads(Path(ref["path"]).read_text())


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--parent",type=Path,required=True)
    parser.add_argument("--parent-sha256",required=True)
    parser.add_argument("--baseline-audit",type=Path,required=True)
    parser.add_argument("--baseline-audit-sha256",required=True)
    parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args()
    parent_ref={"path":str(args.parent),"sha256":args.parent_sha256}
    audit_ref={"path":str(args.baseline_audit),"sha256":args.baseline_audit_sha256}
    parent,audit=pinned(parent_ref),pinned(audit_ref)
    materialized=pinned(audit["materialized"]); registry=pinned(audit["registry"])
    if (audit["prepared_after_same_budget_baseline_audit"]!=76
            or len(parent["cases"])!=24 or registry["prior_confirmation_manifest"]!=parent_ref):
        raise ValueError("All76 fixed declarations and unchanged approved24 parent required")
    output=args.output.resolve(); output.mkdir(parents=True,exist_ok=False)
    prior_prep=args.parent.parent
    dependencies=[r for r in parent["producer_dependencies"]
                  if not Path(r["path"]).is_relative_to(prior_prep)]
    for name in ("probe_v5_moka_layout24_20261008.py","serve_v5_moka_layout24_20261008.py","typed_choice_eval.py"):
        ref=next(r for r in parent["producer_dependencies"] if r["path"]==str(prior_prep/name))
        if identity(ref["path"])["sha256"]!=ref["sha256"]:
            raise ValueError("Approved24 runner dependency changed")
        shutil.copyfile(ref["path"],output/name); dependencies.append(identity(output/name))
    preflight_name="preflight_v5_moka_layout24_CPU_20261008.py"
    preflight_ref=next(r for r in parent["producer_dependencies"] if r["path"]==str(prior_prep/preflight_name))
    if identity(preflight_ref["path"])["sha256"]!=preflight_ref["sha256"]:
        raise ValueError("Approved24 preflight changed")
    text=Path(preflight_ref["path"]).read_text()
    changes={"len(plan[\"cases\"]) != 24":"len(plan[\"cases\"]) != 76",
             "registered_layout_confirmation24":"registered_layout_confirmation76",
             "registered 24 new layouts":"registered approved76 new layouts"}
    for before,after in changes.items():
        if text.count(before)!=1: raise ValueError("Approved24 preflight structure changed: "+before)
        text=text.replace(before,after)
    (output/preflight_name).write_text(text); dependencies.append(identity(output/preflight_name))
    launcher_ref=parent["launcher_identity"]
    if identity(launcher_ref["path"])["sha256"]!=launcher_ref["sha256"]:
        raise ValueError("Approved24 launcher changed")
    launcher=Path(launcher_ref["path"]).read_text()
    launcher_changes={"registered_layout_confirmation24":"registered_layout_confirmation76",
                      "len(p['cases'])!=24":"len(p['cases'])!=76",
                      "registered 24 generated original layouts":"registered approved76 generated original layouts",
                      str(prior_prep.parent):str(output.parent)}
    for before,after in launcher_changes.items():
        if launcher.count(before)!=1: raise ValueError("Approved24 launcher structure changed: "+before)
        launcher=launcher.replace(before,after)
    launcher_path=output/"run_moka_layout76.sbatch"; launcher_path.write_text(launcher)
    dependencies.append(identity(launcher_path))
    generated={r["name"]:r for r in materialized["records"]}
    verified={r["name"]:r for r in audit["records"]}
    states=output/"registered_states"; states.mkdir()
    cases=[]; new_exclusions=[]
    for index,declared in enumerate(registry["layout_rules"]):
        row,check=generated[declared["name"]],verified[declared["name"]]
        raw=pinned(row["registered_layout_state"])
        raw["preparation_provenance"]={"proposed_state_sha256":row["proposed_state_sha256"],
             "settled_state_sha256":row["state_sha256"],"settled_geometry":row["geometry_after"],
             "geometry_fingerprint":check["geometry_fingerprint"],"original_state_file":row["registered_layout_state"],
             "baseline_audit":audit_ref,"base_used":True}
        raw_path=states/f"{declared['name']}.json"
        raw_path.write_text(json.dumps(raw,indent=2,allow_nan=False)+"\n")
        case=copy.deepcopy(parent["cases"][0])
        case.update(name=declared["name"],episode=raw["episode"],state_sha256=raw["state_sha256"],
             registered_layout_state=identity(raw_path),geometry_fingerprint=check["geometry_fingerprint"],
             previously_used_for_selection=False,visited=False,official_init_index=raw["episode"]["seed"],
             trial_index=index,layout_seed=raw["layout_seed"],excluded_from_training=True,
             permanent_training_exclusion=True)
        cases.append(case)
        new_exclusions.append({"case_name":case["name"],"layout_seed":case["layout_seed"],
             "layout_parameters":{"rule":declared["rule"],"rule_sha256":declared["rule_sha256"],
                                  "base_official_state":declared["base_official_state"]},
             "state_sha256":case["state_sha256"],"geometry_fingerprint":case["geometry_fingerprint"],
             "settled_moka_xy_m":row["geometry_after"]["moka_pot_1"][:2],
             "permanent_training_exclusion":True})
    prior_registry=pinned(parent["selection"]["layout_registry"])
    prior_rules={r["name"]:r for r in prior_registry["layout_rules"]}
    exclusions=[]
    for case in parent["cases"]:
        declared=prior_rules[case["name"]]; raw=pinned(case["registered_layout_state"])
        exclusions.append({"case_name":case["name"],"layout_seed":case["layout_seed"],
             "layout_parameters":{"rule":declared["rule"],"rule_sha256":declared["rule_sha256"],
                                  "base_official_state":declared["base_official_state"]},
             "state_sha256":case["state_sha256"],"geometry_fingerprint":case["geometry_fingerprint"],
             "settled_moka_xy_m":raw["preparation_provenance"]["settled_geometry"]["moka_pot_1"][:2],
             "permanent_training_exclusion":True})
    exclusions+=new_exclusions
    if (len(exclusions)!=100 or len({r["geometry_fingerprint"] for r in exclusions})!=100
            or {r["layout_seed"] for r in exclusions}!=set(range(580100,580200))):
        raise ValueError("Union100 geometric/seed completeness failed")
    union={"schema":"libero_confirmation_exclusions/1","training_allowed":False,
           "minimum_moka_xy_distance_m":.05,"records":exclusions,
           "future_training_seed_range":[680100,689999],"coordinates_private_exclusion_only":True,
           "no_policy_text_use":True,"statistical_independence_claimed":False,
           "sources":[parent_ref,audit_ref,audit["registry"],audit["materialized"]]}
    union_path=output/"confirmation_exclusions100.json"
    union_path.write_text(json.dumps(union,indent=2,allow_nan=False)+"\n")
    plan=copy.deepcopy(parent)
    plan.update(cases=cases,purpose="Approved additional76 layouts, completing100 layout transfer confirmations; no IID claim",
          selection={"analysis_role":"registered_layout_confirmation76","confirmation":True,
                     "parent_selection":parent["selection"]["parent_selection"],"layout_registry":audit["registry"]},
          producer=identity(__file__),producer_dependencies=dependencies,parent_runtime_manifest=parent_ref,
          preparation_inputs=[audit_ref,audit["materialized"],audit["registry"]],
          qualification_authorized=False,new_training_rows=0,new_confirmation_attempts=0,
          source_count={"official_unused":0,"registered_layouts":76,"prior_registered_layouts":24,
                        "additional76_authorized":True,"additional76_included":76},
          source_scope="100 total generated original layouts; no fresh official states and no IID claim",
          launcher_identity=identity(launcher_path),launcher_parent=launcher_ref,launcher_changes=launcher_changes,
          permanent_training_exclusion=True,confirmation_exclusion_registry=identity(union_path),jobs_submitted=0,
          budget="unchanged582r2:10000 env steps,320 complete five-action contact chunks")
    manifest=output/"moka_layout76.json"; manifest.write_text(json.dumps(plan,indent=2,allow_nan=False)+"\n")
    handoff={"manifest":identity(manifest),"launcher":identity(launcher_path),"source":plan["source_snapshot"]["path"],
             "source_archive":plan["source_snapshot"]["archive"],"cases":76,"jobs_submitted":0,
             "confirmation_exclusions100":identity(union_path),"first_physical_case":cases[0]["name"],
             "fresh_same_launcher_startup_contract_required":True}
    (output/"handoff.json").write_text(json.dumps(handoff,indent=2)+"\n")
    print(json.dumps(handoff,indent=2))


if __name__=="__main__":
    main()
