"""Explicit microwave583 snapshot plus the committed robot-mask query fix.

CPU only. Preserve all old snapshots and read only the pinned source index.
Plans reuse the same visited original state; no qualification or training.
"""

import argparse
import base64
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import tarfile


ROOT = Path("/public/home/sunyihan/rpent_libero_eval")
BASE = ROOT / "results/harness_v5/microwave583_source_CPU_20261007/r1/source_identity.json"
BASE_SHA = "decc2174b439405aea8718581582ca2b4ab9130cf54e1a9e9b6ada47bc7b69d1"
PARENT = ROOT / "results/harness_v5/microwave571_public_parent_CPU_20261006/preparation/registered/microwave_public_parent_original10.json"
PARENT_SHA = "f9a8b3532b169c0cf93e3d78445e11e96c8beeb343ec36b76ad96c491b9a2296"
FIX_COMMIT = "88c4388"
OVERLAY = "robots/libero/v5_microwave_capture.py"


def ref(path):
    path = Path(path).resolve(strict=True)
    return {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def checked(record):
    path = Path(record["path"])
    if not path.is_absolute() or ref(path)["sha256"] != record["sha256"]:
        raise ValueError("pinned file changed: " + str(path))
    return path


def build(args):
    checked({"path": str(BASE), "sha256": BASE_SHA})
    checked({"path": str(PARENT), "sha256": PARENT_SHA})
    base = json.loads(BASE.read_text())
    checked(base["archive"])
    packet = json.loads(args.packet.read_text())
    if packet["commit"][:7] != FIX_COMMIT or packet["relative_path"] != OVERLAY:
        raise ValueError("unexpected code-only overlay")
    content = base64.b64decode(packet["data_base64"], validate=True)
    if hashlib.sha256(content).hexdigest() != packet["sha256"]:
        raise ValueError("overlay bytes changed")
    snapshot, output = args.snapshot.resolve(), args.output.resolve()
    snapshot.mkdir(parents=True, exist_ok=False)
    output.mkdir(parents=True, exist_ok=False)
    files = []
    for record in base["files"]:
        old = checked(record)
        relative = record["relative_path"]
        if old != Path(base["path"]) / relative or ".." in Path(relative).parts:
            raise ValueError("source file outside declared snapshot")
        new = snapshot / relative
        new.parent.mkdir(parents=True, exist_ok=True)
        if relative == OVERLAY:
            new.write_bytes(content)
        else:
            shutil.copy2(old, new)
        files.append({**ref(new), "relative_path": relative})
    archive = Path(str(snapshot) + ".tar")
    if archive.exists():
        raise FileExistsError(archive)
    with tarfile.open(archive, "w") as stream:
        for record in files:
            stream.add(record["path"], arcname=record["relative_path"], recursive=False)
    identity = {"path": str(snapshot), "commit": packet["commit"],
                "identity_kind": "explicit_source583_plus_robotmask_query_overlay",
                "base_source_identity": ref(BASE), "overlays": [{k: packet[k] for k in
                    ("relative_path", "commit", "sha256")}], "files": files, "archive": ref(archive)}
    identity_path = output / "source_identity.json"
    identity_path.write_text(json.dumps(identity, indent=2) + "\n")
    producer_path = snapshot / "coordination/microwave_runtime_wiring_20261007/prepare_smoke.py"
    spec = importlib.util.spec_from_file_location("prepare_microwave584", producer_path)
    producer = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(producer)
    plans = []
    for key, case, enabled, chunks in (
        ("capture8", "microwave_open_libero_90_t33_s0_r0_articulate_public_parent_current160", False, 8),
        ("close_stop40", "microwave_close_libero_90_t33_s0_r0_articulate_public_parent_current160", True, 40),
    ):
        plan_path = output / (key + ".json")
        producer.prepare(PARENT, plan_path, case_name=case, enable_stop=enabled, max_chunks=chunks,
                         source_identity_file=identity_path)
        plan = json.loads(plan_path.read_text())
        plan.update(purpose="visited original robotmask query comparison; not qualification",
                    qualification_authorized=False, new_training_rows=0)
        plan["cases"][0].update(previously_used_for_selection=True, excluded_from_training=True)
        plan_path.write_text(json.dumps(plan, indent=2) + "\n")
        plans.append({"key": key, "manifest": ref(plan_path), "source": str(snapshot),
                      "output": str(ROOT / "results/harness_v5/microwave584_temporal_original_20261008" / key)})
    receipt = {"source_identity": ref(identity_path), "plans": plans,
               "CPU_preflight_pending": True, "real_same_launcher_startup_pending": True,
               "physics_executed": False, "new_training_rows": 0}
    (output / "preparation.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps(receipt))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--packet", type=Path, required=True)
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    build(parser.parse_args())
