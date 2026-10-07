"""Build the repaired moka source from its explicit parent packet and overlays."""

import argparse
import ast
import hashlib
import json
import shutil
import tarfile
from pathlib import Path


def identity(path):
    path = Path(path).resolve(strict=True)
    return {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def checked(ref):
    path = Path(ref["path"])
    if not path.is_absolute() or identity(path)["sha256"] != ref["sha256"]:
        raise ValueError(f"Registered file changed: {path}")
    return path


def validate_source_interfaces(source):
    """Check the snapshot's real caller signature and finalizer dependencies."""
    runtime = ast.parse((source / "robots/libero/v5_runtime.py").read_text())
    executor = next(node for node in runtime.body
                    if isinstance(node, ast.ClassDef) and node.name == "V5Executor")
    constructor = next(node for node in executor.body
                       if isinstance(node, ast.FunctionDef) and node.name == "__init__")
    allowed = {argument.arg for argument in constructor.args.args + constructor.args.kwonlyargs}
    harness = ast.parse((source / "harness_v5_eval.py").read_text())
    for node in ast.walk(harness):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                and node.func.id == "V5Executor"):
            continue
        passed = {keyword.arg for keyword in node.keywords if keyword.arg is not None}
        for keyword in node.keywords:
            if keyword.arg is None and isinstance(keyword.value, ast.DictComp):
                for generator in keyword.value.generators:
                    if isinstance(generator.iter, (ast.Tuple, ast.List)):
                        passed.update(ast.literal_eval(generator.iter))
        if constructor.args.kwarg is None and passed - allowed:
            raise ValueError(f"Snapshot executor does not support caller keywords: {sorted(passed - allowed)}")
    dependencies = set()
    for node in ast.walk(harness):
        if isinstance(node, (ast.Tuple, ast.List)):
            values = [item.value for item in node.elts
                      if isinstance(item, ast.Constant) and isinstance(item.value, str)]
            if "harness_v5_eval.py" in values and "typed_choice_eval.py" in values:
                dependencies.update(values)
    if not dependencies:
        raise ValueError("Snapshot has no explicit finalizer source list")
    missing = sorted(name for name in dependencies if not (source / name).is_file())
    if missing:
        raise FileNotFoundError(f"Snapshot finalizer files missing: {missing}")
    return {"executor_caller_compatible": True, "finalizer_files_checked": len(dependencies)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--parent", type=Path, required=True)
    parser.add_argument("--parent-sha", required=True)
    parser.add_argument("--overlays", type=Path, required=True)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--commit", required=True)
    args = parser.parse_args()
    parent = checked({"path": str(args.parent), "sha256": args.parent_sha})
    plan = json.loads(parent.read_text())
    overlays = json.loads(args.overlays.read_text())
    for ref in plan["source_snapshot"]["files"]:
        relative = Path(ref.get("relative_path", ref["path"]))
        if "__pycache__" in relative.parts or relative.suffix in (".pyc", ".pyo"):
            continue
        checked(ref)
    archive = checked(plan["source_snapshot"]["archive"])
    if not args.source.is_absolute() or args.source.exists() or args.manifest.exists():
        raise ValueError("New absolute source and manifest paths are required")
    overlay_paths = {}
    for ref in overlays:
        relative = Path(ref["relative_path"])
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError(f"Invalid overlay destination: {relative}")
        overlay_paths[str(relative)] = checked(ref)
    args.source.mkdir(parents=True)
    members = []
    # The explicit, pinned source archive supplies this list. No artifact
    # directory enumeration or test-set loading occurs during preparation.
    with tarfile.open(archive) as source_tar:
        for member in source_tar.getmembers():
            relative = Path(member.name)
            if relative.is_absolute() or ".." in relative.parts or member.issym() or member.islnk():
                raise ValueError(f"Unsafe source archive member: {member.name}")
            if not (member.isdir() or member.isfile()):
                raise ValueError(f"Unsupported source member: {member.name}")
            if "__pycache__" in relative.parts or relative.suffix in (".pyc", ".pyo"):
                continue
            source_tar.extract(member, args.source)
            if member.isfile():
                members.append(str(relative))
    for relative, original in overlay_paths.items():
        target = args.source / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(original, target)
        members.append(relative)
    interface_check = validate_source_interfaces(args.source)
    files = []
    for relative in sorted(set(members)):
        files.append({**identity(args.source / relative), "relative_path": relative})
    archive_out = args.source.with_suffix(".tar")
    with tarfile.open(archive_out, "x") as destination:
        for relative in sorted(set(members)):
            destination.add(args.source / relative, arcname=relative, recursive=False)
    plan["source_snapshot"] = {
        "path": str(args.source), "commit": args.commit,
        "files": files, "archive": identity(archive_out),
    }
    plan["source_snapshot_sha256"] = hashlib.sha256(
        json.dumps(plan["source_snapshot"], sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    supplement = args.manifest.parent / "typed_choice_eval.py"
    shutil.copyfile(parent.parent / "typed_choice_eval.py", supplement)
    plan["producer"] = identity(__file__)
    plan["producer_dependencies"] = [identity(args.overlays)] + [
        identity(args.source / relative) for relative in overlay_paths
    ] + [identity(supplement)]
    plan["repair"] = {
        "parent_manifest": identity(parent), "repair_commit": args.commit,
        "startup_contract": "same immutable launcher/source; one real episode before remaining shards",
        "previous_physical_attempts_to_exclude": ["moka_transfer_visited_libero_90_t19_s3"],
        "previous_physical_attempt_source": "/public/home/sunyihan/rpent_libero_eval/results/harness_v5/moka_transfer_confirmation_prep_CPU_20261007/smoke10/job4378/part3/probe/episodes.jsonl",
    }
    args.manifest.write_text(json.dumps(plan, indent=2) + "\n")
    print(json.dumps({"manifest": identity(args.manifest), "source": plan["source_snapshot"]["path"],
                      "archive": identity(archive_out), "source_file_count": len(files),
                      "source_interface_check": interface_check}))


if __name__ == "__main__":
    main()
