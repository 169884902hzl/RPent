"""Preflight only explicitly registered probe files before starting services."""

import argparse
import hashlib
import json
from pathlib import Path


def pinned_file(reference, label, cache=None):
    path = Path(reference["path"]).expanduser()
    if not path.is_absolute():
        raise ValueError(f"{label} must use an absolute path in the manifest: {path}")
    path = path.resolve(strict=True)
    if not path.is_file():
        raise ValueError(f"{label} is not a regular file: {path}")
    key = (path, reference["sha256"])
    digest = cache.get(key) if cache is not None else None
    if digest is None:
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if digest != reference["sha256"]:
        raise ValueError(f"registered {label} changed: {path}")
    if cache is not None:
        cache[key] = digest
    return {"path": str(path), "sha256": digest, "role": label}


def load_pinned_manifest(manifest, validate=None):
    """Return canonical manifest, plan and base after explicit-file checks.

    Relative CLI arguments are resolved once against the invocation directory.
    References inside the manifest must already be absolute, so changing into
    the immutable source directory cannot change which registered file is read.
    No referenced manifest is recursively opened and no directory is searched.
    """
    manifest = Path(manifest).expanduser().resolve(strict=True)
    plan = json.loads(manifest.read_text())
    if validate is not None:
        validate(plan)
    cache = {}
    checked = [pinned_file(plan["base_config"], "base_config", cache)]
    base = json.loads(Path(checked[0]["path"]).read_text())
    for case in plan["cases"]:
        for key in ("bddl", "init_file"):
            if key in case:
                checked.append(pinned_file(case[key], f"case:{case['name']}:{key}", cache))
    package = Path(plan["choice_package"]).expanduser()
    if not package.is_absolute():
        raise ValueError("choice_package must use an absolute path in the manifest")
    package = package.resolve(strict=True)
    if not (package / "tokenizer_config.json").is_file():
        raise ValueError(f"choice_package has no tokenizer_config.json: {package}")
    for ref in plan.get("choice_package_files", []):
        path = Path(ref["path"]).expanduser().resolve(strict=True)
        if not path.is_relative_to(package):
            raise ValueError("registered choice file is outside choice_package")
        checked.append(pinned_file(ref, "choice_package_file", cache))
    for key in ("original_task_catalog_file", "producer"):
        ref = plan.get(key)
        if isinstance(ref, dict) and "path" in ref:
            checked.append(pinned_file(ref, key, cache))
    reservations = plan.get("access_reservations", {})
    for key in ("inputs", "prior_manifests"):
        for ref in reservations.get(key, []):
            checked.append(pinned_file(ref, f"access_reservations:{key}", cache))
    plan["preflight"] = {
        "manifest": str(manifest),
        "manifest_sha256": hashlib.sha256(manifest.read_bytes()).hexdigest(),
        "files_checked": checked, "explicit_files_only": True,
    }
    return manifest, plan, base


def validate_registered_states(cases):
    """Verify the registered original-state bytes, without running physics."""
    import numpy as np
    from rlinf.envs.libero.utils import benchmark

    suites, states_by_task, count = {}, {}, 0
    for case in cases:
        episode = case["episode"]
        name = episode["suite"]
        if name not in suites:
            suites[name] = benchmark.get_benchmark(name)()
        task_key = (name, episode["task"])
        if task_key not in states_by_task:
            states_by_task[task_key] = suites[name].get_task_init_states(episode["task"])
        states = states_by_task[task_key]
        if not 0 <= episode["seed"] < len(states):
            raise ValueError(f"registered original init index is out of range: {case['name']}")
        state = np.asarray(states[episode["seed"]], dtype="<f8", order="C")
        digest = hashlib.sha256(state.tobytes()).hexdigest()
        if digest != case["state_sha256"]:
            raise ValueError(f"registered official initial state changed: {case['name']}")
        count += 1
    return {"state_hashes_checked": count, "explicit_cases_only": True}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--shard-index", type=int, default=0)
    parser.add_argument("--shards", type=int, default=1)
    parser.add_argument("--states", action="store_true")
    args = parser.parse_args()
    if args.shards < 1 or not 0 <= args.shard_index < args.shards:
        parser.error("shard-index must be in [0, shards)")
    _, plan, _ = load_pinned_manifest(args.manifest)
    result = plan["preflight"]
    if args.states:
        result.update(validate_registered_states(plan["cases"][args.shard_index::args.shards]))
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
