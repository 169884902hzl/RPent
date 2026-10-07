"""Build an explicit source581 overlay and two visited original microwave plans.

CPU preparation only. The caller supplies committed overlay bytes; every source
file comes from the source581 manifest. No artifact directory scan or GPU/job
submission is performed, and all prior snapshots and attempts remain unchanged.
"""

import argparse
import base64
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import tarfile


BASE_PLAN = Path("/public/home/sunyihan/rpent_libero_eval/results/harness_v5/runtime581_source_CPU_20261007/source_plan.json")
BASE_PLAN_SHA = "76d2c31915a2d9817be8160e17e0f5a2321782a29f27fd637ca60a16cb6bb8b9"
PARENT = Path("/public/home/sunyihan/rpent_libero_eval/results/harness_v5/microwave571_public_parent_CPU_20261006/preparation/registered/microwave_public_parent_original10.json")
PARENT_SHA = "f9a8b3532b169c0cf93e3d78445e11e96c8beeb343ec36b76ad96c491b9a2296"
BASE_ARCHIVE_SHA = "66e2c898240f84a60485e72de8eb3b2191a93d5305c88e3134d0d5e9324b883a"
ROOT = Path("/public/home/sunyihan/rpent_libero_eval")
PREPARE_RELATIVE = "coordination/microwave583_sourceprep_20261007/prepare.py"
LAUNCHER_RELATIVE = "coordination/microwave_runtime_wiring_20261007/run_smoke.sbatch"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def ref(path):
    path = Path(path).resolve(strict=True)
    return {"path": str(path), "sha256": sha(path)}


def check(reference):
    path = Path(reference["path"])
    if not path.is_absolute() or sha(path) != reference["sha256"]:
        raise ValueError("explicit file changed: " + str(path))
    return path


def absolute_references(value):
    if isinstance(value, dict):
        if "path" in value and not Path(value["path"]).is_absolute():
            raise ValueError("relative manifest file path: " + str(value["path"]))
        for child in value.values():
            absolute_references(child)
    elif isinstance(value, list):
        for child in value:
            absolute_references(child)


def build(args):
    if not all(path.is_absolute() for path in (args.packet, args.output, args.snapshot)):
        raise ValueError("absolute packet/output/snapshot required")
    check({"path": str(BASE_PLAN), "sha256": BASE_PLAN_SHA})
    check({"path": str(PARENT), "sha256": PARENT_SHA})
    packet = json.loads(args.packet.read_text())
    plan = json.loads(BASE_PLAN.read_text())
    base = plan["source_snapshot"]
    if base["path"] != str(ROOT / "source_v5_runtime581_20261007"):
        raise ValueError("source581 snapshot identity changed")
    if base["archive"]["sha256"] != BASE_ARCHIVE_SHA:
        raise ValueError("source581 archive identity changed")
    check(base["archive"])
    args.output.mkdir(parents=True, exist_ok=False)
    args.snapshot.mkdir(parents=True, exist_ok=False)
    archive = Path(str(args.snapshot) + ".tar")
    if archive.exists():
        raise FileExistsError(archive)
    source_files = {}
    before = {}
    for item in base["files"]:
        old = check(item)
        relative = item["relative_path"]
        if old != Path(base["path"]) / relative or Path(relative).is_absolute() or ".." in Path(relative).parts:
            raise ValueError("file outside source581: " + relative)
        if relative in source_files:
            raise ValueError("duplicate declared source file: " + relative)
        new = args.snapshot / relative
        new.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(old, new)
        source_files[relative] = new
        before[relative] = item["sha256"]
    required_overlays = {
        "robots/libero/v5_microwave_capture.py": "db8d49ca35f94751f63ca9d33beb41a3c4668e57",
        "robots/libero/v5_microwave_door_temporal.py": "db8d49ca35f94751f63ca9d33beb41a3c4668e57",
        LAUNCHER_RELATIVE: "7b338622dc2ce109c561132538b5b00a4c03751a",
        PREPARE_RELATIVE: packet["preparation_commit"],
    }
    if {item["relative_path"] for item in packet["overlays"]} != set(required_overlays):
        raise ValueError("only the two baseline modules, fixed launcher and preparation source are admitted")
    changes = []
    for item in packet["overlays"]:
        relative = item["relative_path"]
        if item["commit"] != required_overlays[relative]:
            raise ValueError("overlay commit changed: " + relative)
        content = base64.b64decode(item["data_base64"], validate=True)
        if hashlib.sha256(content).hexdigest() != item["sha256"]:
            raise ValueError("overlay bytes changed: " + relative)
        path = args.snapshot / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        source_files[relative] = path
        changes.append({"relative_path": relative, "commit": item["commit"],
                        "before_sha256": before.get(relative), "after_sha256": item["sha256"]})
    files = [{**ref(path), "relative_path": relative} for relative, path in sorted(source_files.items())]
    with tarfile.open(archive, "w") as saved:
        for item in files:
            saved.add(item["path"], arcname=item["relative_path"], recursive=False)
    # Identity commit is the committed preparation recipe, not a claim that
    # all files are from that checkout. Exact mixed lineage is explicit below.
    identity = {"path": str(args.snapshot), "commit": packet["preparation_commit"],
                "identity_kind": "explicit_source581_plus_committed_overlays",
                "base_commit": base["commit"], "base_source_plan": ref(BASE_PLAN),
                "base_archive": base["archive"], "overlays": changes,
                "files": files, "archive": ref(archive)}
    identity_path = args.output / "source_identity.json"
    identity_path.write_text(json.dumps(identity, indent=2) + "\n")
    prepare_path = args.snapshot / "coordination/microwave_runtime_wiring_20261007/prepare_smoke.py"
    spec = importlib.util.spec_from_file_location("prepare_microwave583_smoke", prepare_path)
    producer = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(producer)
    prepared = []
    for key, case, stop, chunks in (
        ("capture8", "microwave_open_libero_90_t33_s0_r0_articulate_public_parent_current160", False, 8),
        ("close_stop40", "microwave_close_libero_90_t33_s0_r0_articulate_public_parent_current160", True, 40),
    ):
        path = args.output / (key + ".json")
        producer.prepare(PARENT, path, case_name=case, enable_stop=stop, max_chunks=chunks,
                         source_identity_file=identity_path)
        trial = json.loads(path.read_text())
        trial.update(purpose=("visited original baseline capture development smoke; already-open is not opening success"
                              if not stop else "visited original close endpoint stop method selection; not qualification"),
                     producer=ref(args.snapshot / PREPARE_RELATIVE),
                     source_snapshot_sha256=hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest(),
                     startup_requirement="one real same-source/launcher episode before any additional shard release",
                     new_physics_executed_in_preparation=0, qualification_authorized=False,
                     selection="explicit task33/init0 case fixed before new physical outcomes",
                     source_preparation={"base": ref(BASE_PLAN), "packet": ref(args.packet),
                                         "code_only_overlays": changes},
                     public_stop_contract={"input": "fresh public RGB-D and robot proprioception only",
                                           "private_truth_controls_stop": False,
                                           "baseline_maximum_total_pairs": 3,
                                           "neutral_holds_each_pair": 6},
                     run_status="CPU_prepared_no_GPU_submitted")
        trial["producer_dependencies"] += [ref(prepare_path), ref(PARENT), ref(BASE_PLAN)]
        trial["cases"][0].update(previously_used_for_selection=True, excluded_from_training=True)
        trial["metrics"]["qualification"] = "none; visited development smoke/selection only"
        trial["budget"]["note"] = ("8-block bounded baseline capture smoke" if not stop else
                                      "40-block development selection; may later expand to160 in a separately recorded plan")
        absolute_references(trial)
        path.write_text(json.dumps(trial, indent=2) + "\n")
        env = {
            "MICROWAVE_SOURCE": str(args.snapshot), "MICROWAVE_PLAN": str(path),
            "MICROWAVE_PLAN_SHA": sha(path),
            "MICROWAVE_OUTPUT": str(ROOT / "results/harness_v5/microwave583_temporal_original_20261007" / key),
            "MICROWAVE_CPU_ONLY": "0",
        }
        prepared.append({"key": key, "manifest": ref(path), "case": trial["cases"][0]["name"],
                         "max_chunks": chunks, "stop_enabled": stop, "env": env,
                         "launcher": ref(args.snapshot / LAUNCHER_RELATIVE)})
    # Re-hash each original declared file, not just the three changed names.
    for item in base["files"]:
        check(item)
    check(base["archive"])
    receipt = {"version": "microwave583_sourceprep/1-dev", "source_identity": ref(identity_path),
               "source_files": len(files), "old_source581_unchanged": True,
               "base_source_plan": ref(BASE_PLAN), "overlay_packet": ref(args.packet),
               "code_changes": changes, "plans": prepared,
               "CPU_preflight": "pending same immutable launcher", "GPU_submitted": False,
               "new_physical_trials": 0, "qualification": False}
    (args.output / "preparation.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps({"output": str(args.output), "source": str(args.snapshot),
                      "files": len(files), "plans": [item["manifest"] for item in prepared]}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--packet", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--snapshot", required=True, type=Path)
    build(parser.parse_args())
