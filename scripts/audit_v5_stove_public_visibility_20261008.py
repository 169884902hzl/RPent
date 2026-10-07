"""Inspect fixed public frames from the original three train states, no labels."""

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw


def pinned(ref):
    path=Path(ref["path"])
    if not path.is_absolute() or hashlib.sha256(path.read_bytes()).hexdigest()!=ref["sha256"]:
        raise ValueError("Explicit public input changed: "+str(path))
    return path


def identity(path):
    return {"path":str(path),"sha256":hashlib.sha256(path.read_bytes()).hexdigest()}


def bbox(mask):
    ys,xs=np.where(mask)
    return [int(xs.min()),int(ys.min()),int(xs.max()+1),int(ys.max()+1)] if len(xs) else None


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--dataset-manifest",type=Path,required=True)
    parser.add_argument("--dataset-manifest-sha256",required=True)
    parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args()
    manifest=json.loads(pinned({"path":str(args.dataset_manifest),"sha256":args.dataset_manifest_sha256}).read_text())
    plan=json.loads(pinned(manifest["input_manifest"]).read_text())
    if (plan["read_validation_episodes"] is not False or len(plan["cases"])!=3
            or any(c["split"]!="train" for c in plan["cases"])):
        raise ValueError("Only three original train states authorized")
    ref=next(r for r in manifest["files"] if Path(r["path"]).name=="public_samples.jsonl")
    rows=[json.loads(line) for line in pinned(ref).read_text().splitlines()]
    states=list(dict.fromkeys(r["raw_state_sha256"] for r in rows))
    if len(states)!=3:raise ValueError("Expected only three train states")
    args.output.mkdir(parents=True,exist_ok=False)
    records=[]; outputs=[]
    for number,state in enumerate(states):
        selected=[r for r in rows if r["raw_state_sha256"]==state]
        before=selected[0]["before_frame"]
        frames=[("before",before)]+[(f"chunk{chunk}",next(r for r in selected if r["chunk_index"]==chunk)["recent_frames"][-1])
                                    for chunk in (20,40,160,320)]
        lower=np.asarray(selected[0]["measured_bounds"]["lower"])
        upper=np.asarray(selected[0]["measured_bounds"]["upper"])
        center=np.asarray(before["public_robot_observation"]["eef_xyz_m"])
        canvas=Image.new("RGB",(1400,5*520),"#eeeeee");draw=ImageDraw.Draw(canvas)
        for fi,(tag,frame) in enumerate(frames):
            for ci,camera in enumerate(("agentview","wrist")):
                view=frame["views"][camera]
                rgb,world_file=pinned(view["raw_rgb"]),pinned(view["raw_world"])
                image=Image.open(rgb).convert("RGB")
                with np.load(world_file,allow_pickle=False) as data:world=np.asarray(data["array"],dtype=np.float32)
                finite=np.isfinite(world).all(axis=-1)
                contact=finite&(world>=center-.04).all(axis=-1)&(world<=center+.04).all(axis=-1)
                shell=finite&(world>=lower-.01).all(axis=-1)&(world<=upper+.01).all(axis=-1)
                cb,sb=bbox(contact),bbox(shell)
                annotated=image.copy();ad=ImageDraw.Draw(annotated)
                if sb:ad.rectangle(sb,outline="#ff00ff",width=3)
                if cb:ad.rectangle(cb,outline="#ff9900",width=3)
                raw_path=args.output/f"state{number}_{tag}_{camera}.png"
                image.save(raw_path)
                annotated.thumbnail((680,470))
                canvas.paste(annotated,(ci*700+10,fi*520+40))
                draw.text((ci*700+10,fi*520+10),f"state{number} {tag} {camera}; purple=measured shell / orange=public EEF context",fill="black")
                records.append({"raw_state_sha256":state,"tag":tag,"camera":camera,
                    "source_step":frame["source_step"],"public_rgb":view["raw_rgb"],"public_world":view["raw_world"],
                    "audit_rgb":identity(raw_path),"public_shell_pixel_bbox":sb,"public_contact_context_pixel_bbox":cb,
                    "context_points":int(contact.sum()),"shell_points":int(shell.sum()),
                    "control_part_visibility":"not_established_by_occupancy",
                    "occlusion_annotation":"pending_explicit_RGB_inspection","private_labels_read":False})
        output=args.output/f"state{number}_fixed_frames_montage.png";canvas.save(output);outputs.append(identity(output))
    record_path=args.output/"public_frame_index.json"
    record_path.write_text(json.dumps(records,indent=2)+"\n")
    summary={"schema":"stove-three-train-public-visibility-audit/1","producer":identity(Path(__file__)),
        "dataset_manifest":identity(args.dataset_manifest),"frames_selected_per_state":["before",20,40,160,320],
        "state_count":3,"views":len(records),"read_validation_episodes":False,"private_labels_read":False,
        "selection_uses_private_endpoint":False,"control_identity_verified":False,
        "montages":outputs,"public_frame_index":identity(record_path),"stop_admitted":False}
    (args.output/"manifest.json").write_text(json.dumps(summary,indent=2)+"\n")
    print(json.dumps(summary,indent=2))


if __name__=="__main__":main()
