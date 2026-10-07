"""Summarize the five explicit 4349 outputs without globbing artifacts."""
from pathlib import Path
import hashlib, json, subprocess

REMOTE_ROOT = Path("/public/home/sunyihan/rpent_libero_eval/results/harness_v5/articulate577_stove_multiframe_original_20261007/probe_job4349")
PARTS = [REMOTE_ROOT / f"part{i}" / "episodes.jsonl" for i in range(5)]


def digest(path):
    raw = path.read_bytes(); return {"path": str(path), "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def main():
    rows=[]; refs=[]
    for i, path in enumerate(PARTS):
        if not path.is_file(): raise FileNotFoundError(path)
        refs.append(digest(path)); lines=path.read_text().splitlines()
        if len(lines)!=1: raise ValueError(f"part{i} expected one episode row")
        row=json.loads(lines[0]); phases={}
        for phase, cap in row["captures"].items():
            seq=cap.get("public_temporal_sequence")
            if seq is None: continue
            seq_path=Path(seq["path"])
            if not seq_path.is_file(): raise FileNotFoundError(seq_path)
            data=json.loads(seq_path.read_text()); refs.append(digest(seq_path))
            phases[phase]={k:data[k] for k in ("status","frames","unknown_reason","fixed_hold_controls","fixed_gripper_control","stop_based_on_private_label","unobstructed_view_claim")}
            phases[phase]["sha256_registered"] = seq["sha256"]
            if digest(seq_path)["sha256"] != seq["sha256"]: raise ValueError(f"hash mismatch {seq_path}")
        rows.append({"part":i,"case":row["case"]["name"],"state_sha256":row["case"]["state_sha256"],
                     "status":row["status"],"new_training_rows":row["new_training_rows"],
                     "public_stop_enabled":row["public_stop_enabled"],"external_action_budget_exhausted":row["external_action_budget_exhausted"],
                     "phases":phases,"wall_s":row["wall_s"]})
    report={"schema":"articulate577-4349-summary/1","job":4349,"cases":rows,"parts":refs,
            "parts_completed":len(rows)==5,"all_public_temporal_sequences_present":all(len(r["phases"])==3 for r in rows),
            "new_training_rows":sum(r["new_training_rows"] for r in rows),"private_labels_controller_access":False,
            "public_stop_enabled":False,"scope":"five original libero_goal task7 seed0..4 development states; not confirmation batch"}
    out=Path(__file__).resolve().parent/"4349_summary.json"; out.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps({"output":str(out),"sha256":hashlib.sha256(out.read_bytes()).hexdigest(),"bytes":out.stat().st_size,"parts":len(rows)}))

if __name__=="__main__": main()
