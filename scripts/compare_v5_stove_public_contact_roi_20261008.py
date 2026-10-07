"""Fixed public before-EEF ROI comparison on only the three registered train states.

ROI radius4cm is fixed before labels are opened. It is contact context, not a
claim that a knob has been localized. Nothing here admits a runtime stop.
"""

import argparse
import json
from pathlib import Path

import numpy as np

from robots.libero.v5_temporal_verifier import identity, model_features
from scripts.prepare_v5_temporal_endpoint_cpu import encode_sequence, read_pinned, check_split
from scripts.train_v5_temporal_control_trainonly_20261008 import fit
from scripts.train_v5_temporal_endpoint_cpu import metrics


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--dataset-manifest",type=Path,required=True)
    parser.add_argument("--dataset-manifest-sha256",required=True)
    parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args()
    manifest=read_pinned({"path":str(args.dataset_manifest),"sha256":args.dataset_manifest_sha256})
    plan=read_pinned(manifest["input_manifest"])
    if (plan["read_validation_episodes"] is not False or len(plan["cases"])!=3
            or any(c["split"]!="train" for c in plan["cases"])):
        raise ValueError("Only the three registered train states may enter this comparison")
    check_split(plan["cases"],set(plan["confirmation_raw_state_sha256"]))
    refs={Path(r["path"]).name:r for r in manifest["files"]}
    rows=read_pinned(refs["public_samples.jsonl"],jsonl=True)
    ref=refs["public_features.npz"]
    if identity(ref["path"])["sha256"]!=ref["sha256"]:raise ValueError("Public fixture features changed")
    with np.load(ref["path"],allow_pickle=False) as data:fixture=data["features"]
    args.output.mkdir(parents=True,exist_ok=False)
    contact,public,cache=[],[],{}
    for row in rows:
        center=np.asarray(row["before_frame"]["public_robot_observation"]["eef_xyz_m"],dtype=float)
        if center.shape!=(3,) or not np.isfinite(center).all():
            raise ValueError("Public action-before proprioception is missing")
        # Existing pool adds4cm padding to this point, yielding the fixed8cm box.
        # This is an offline context ROI, never a fabricated entity measurement.
        bounds={"lower":center.tolist(),"upper":center.tolist()}
        vector,available,reason=encode_sequence(row["before_frame"],row["recent_frames"],bounds,
            encoder_profile="world_xy_grid_v1",cache=cache)
        contact.append(vector)
        public.append({"sample_id":row["sample_id"],"raw_state_sha256":row["raw_state_sha256"],
            "ROI_center_public_before_eef_xyz_m":center.tolist(),"ROI_radius_m":.04,
            "center_source":"robot_proprioception_before_contact",
            "current_available_views":available,"unknown_reason":reason,
            "private_features":False,"control_part_identity_verified":False,
            "public_record":row["public_record"]})
    contact=np.stack(contact).astype(np.float32)
    features_path=args.output/"public_contact_features.npz"
    np.savez_compressed(features_path,features=contact)
    public_path=args.output/"public_contact_ROI.jsonl"
    public_path.write_text("".join(json.dumps(r)+"\n" for r in public))
    # Private label bytes are opened only after every public ROI vector is saved.
    ref=refs["private_training_labels.npz"]
    if identity(ref["path"])["sha256"]!=ref["sha256"]:raise ValueError("Private training labels changed")
    with np.load(ref["path"],allow_pickle=False) as data:targets=data["targets"]
    states=np.asarray([r["raw_state_sha256"] for r in rows]); valid=targets>=0
    fixture=model_features(fixture,"baseline_relative_v1")
    relative_contact=model_features(contact,"baseline_relative_v1")
    profiles={"unchanged_fixture_plus_proprio":fixture,
              "contact_ROI_plus_proprio":relative_contact,
              "fixture_plus_contact_ROI_plus_proprio":np.concatenate([fixture,relative_contact[:,:2568]],axis=1)}
    comparisons={}; predictions=[]
    for name,values in profiles.items():
        folds=[]; all_y=[]; all_p=[]
        for state in sorted(set(states.tolist())):
            training,held=valid&(states!=state),valid&(states==state)
            result=fit(values,targets,training,epochs=300,seed=577)
            if result is None:raise ValueError("Remaining train states lack both classes")
            probabilities=result[3][held]
            folds.append({"held_train_state":state,"metrics":metrics(targets[held],probabilities)})
            all_y.extend(targets[held].tolist());all_p.extend(probabilities.tolist())
            for index,p in zip(np.flatnonzero(held),probabilities):
                predictions.append({"sample_id":rows[index]["sample_id"],"raw_state_sha256":state,
                    "profile":name,"p_satisfied":float(p),"private_label_offline_only":int(targets[index]),
                    "contact_ROI_current_available_views":public[index]["current_available_views"],
                    "contact_ROI_unknown_reason":public[index]["unknown_reason"],"stop_admitted":False})
        comparisons[name]={"folds":folds,"aggregate_same954_known_original_samples":metrics(np.asarray(all_y),np.asarray(all_p))}
    predictions_path=args.output/"LOO_predictions.jsonl"
    predictions_path.write_text("".join(json.dumps(r)+"\n" for r in predictions))
    report={"schema":"control580-public-contact-ROI-LOO/1-dev","producer":identity(__file__),
        "dataset_manifest":identity(args.dataset_manifest),"public_encoded_before_private_open":True,
        "ROI_radius_m":.04,"ROI_center_source":"fixed action-before public EEF",
        "runtime_default_enabled":False,"stop_admitted":False,"read_validation_episodes":False,
        "comparison":comparisons,"rows":len(rows),"known_original_public_label_rows":int(valid.sum()),
        "contact_ROI_available_current_rows_by_camera":np.asarray([r["current_available_views"] for r in public]).sum(axis=0).tolist(),
        "contact_ROI_unmeasured_both_current_rows":sum(not any(r["current_available_views"]) for r in public),
        "fixed_training":{"epochs":300,"seed":577,"hidden":32,"lr":.001,"weight_decay":.03},
        "files":[identity(features_path),identity(public_path),identity(predictions_path)],
        "limitations":["Train-state LOO is development only, not independent confirmation.",
                       "Same954 diagnostic comparison retains masked unavailable views; no frame is silently discarded.",
                       "ROI occupancy does not prove knob visibility or authorize stopping."]}
    path=args.output/"report.json";path.write_text(json.dumps(report,indent=2)+"\n")
    print(json.dumps({k:v["aggregate_same954_known_original_samples"] for k,v in comparisons.items()}))


if __name__=="__main__":
    main()
