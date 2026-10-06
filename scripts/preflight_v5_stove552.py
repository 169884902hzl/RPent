"""Check explicit original stove inputs before any GPU service starts."""

import hashlib
import json
import os
from pathlib import Path

from scripts.v5_probe_preflight import pinned_file, validate_registered_states


def load_stove_inputs(manifest, *, source, expected_sha=None, check_states=False):
    """Use absolute inputs and the runner's actual validation from any cwd."""
    from scripts import probe_v5_stove521_endpoint as probe

    manifest, source = Path(manifest).expanduser(), Path(source).expanduser()
    if not manifest.is_absolute() or not source.is_absolute():
        raise ValueError("stove manifest and source must be absolute paths")
    manifest, source = manifest.resolve(strict=True), source.resolve(strict=True)
    if Path(probe.__file__).resolve().parents[1] != source:
        raise ValueError("imported stove runner differs from the explicit source root")
    digest = hashlib.sha256(manifest.read_bytes()).hexdigest()
    if expected_sha is not None and digest != expected_sha:
        raise ValueError("registered stove manifest changed")
    plan = json.loads(manifest.read_text())
    probe.validate_manifest(plan)
    if os.environ.get("LIBERO_TYPE") != "standard":
        raise ValueError("stove preflight requires LIBERO_TYPE=standard")
    cache, checked = {}, []
    checked.append(pinned_file(plan["base_config"], "base_config", cache))
    base = json.loads(Path(checked[0]["path"]).read_text())
    if base.get("libero_type") != "standard":
        raise ValueError("registered stove base config must be original standard LIBERO")
    for case in plan["cases"]:
        for key in ("bddl", "init_file"):
            checked.append(pinned_file(case[key], f"case:{case['name']}:{key}", cache))
    for key in ("original_task_catalog_file", "producer"):
        if key in plan:
            checked.append(pinned_file(plan[key], key, cache))
    source_hashes = dict(plan.get("required_source_sha256", {}))
    source_hashes.update({"scripts/probe_v5_stove521_endpoint.py": plan["required_probe_sha256"],
                         "robots/libero/v5_stove_probe_env.py": plan["required_server_sha256"],
                         "robots/libero/v5_stove_measurement.py": plan["required_stove_module_sha256"]})
    for name, sha in source_hashes.items():
        path = source / name
        if not path.resolve(strict=True).is_relative_to(source):
            raise ValueError("registered stove source file is outside explicit source root")
        checked.append(pinned_file({"path": str(path), "sha256": sha}, "source:" + name, cache))
    resources = []
    for resource in plan.get("runtime_resources", []):
        path = Path(resource["path"])
        if not path.is_absolute():
            raise ValueError("stove runtime resource must be absolute")
        path = path.resolve(strict=True)
        resources.append({**resource, "path": str(path), "bytes": path.stat().st_size})
    report = {"passed": True, "manifest": str(manifest), "manifest_sha256": digest,
              "source": str(source), "cwd": str(Path.cwd()), "files_checked": checked,
              "resources": resources, "explicit_files_only": True, "gpu_services_started": False,
              "original_states": len(plan["cases"]), "physical_resets": len(probe.work_items(plan)),
              "actions_per_chunk": plan["budget"]["actions_per_chunk"],
              "qualification_authorized": False}
    if check_states:
        report.update(validate_registered_states(plan["cases"]))
    return plan, base, report
