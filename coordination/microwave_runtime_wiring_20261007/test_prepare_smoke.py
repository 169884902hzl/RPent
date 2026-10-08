"""A current explicit source identity must replace all inherited source refs."""

import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace


def test_prepare_replaces_old_source_identity_and_dependency_paths(tmp_path, monkeypatch):
    path = Path(__file__).with_name("prepare_smoke.py")
    spec = importlib.util.spec_from_file_location("prepare_microwave_smoke", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    source = tmp_path / "parent.json"
    source.write_text(json.dumps({"cases": [{"name": "original_microwave", "condition": "old",
        "episode": {"suite": "libero_90", "task": 33, "seed": 0}}],
        "conditions": {"old": {"executor": "current", "max_chunks": 160, "overrides": {}}},
        "source_snapshot": {"path": "/old", "commit": "old"}}))
    snapshot = tmp_path / "source"
    names = ("robots/libero/v5_microwave_capture.py", "robots/libero/v5_microwave_door_temporal.py",
             "robots/libero/v5_microwave_identity.py", "robots/libero/v5_runtime.py",
             "scripts/probe_v5_skill501_original.py",
             "scripts/probe_v5_microwave_public571.py", "scripts/v5_probe_preflight.py",
             "coordination/microwave_runtime_wiring_20261007/prepare_smoke.py",
             "coordination/microwave_runtime_wiring_20261007/run_smoke.sbatch",
             "typed_choice_eval.py")
    refs=[]
    for name in names:
        file=snapshot / name
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text(name)
        refs.append({"path":str(file),"relative_path":name,
                     "sha256":module.hashlib.sha256(file.read_bytes()).hexdigest()})
    identity_path=tmp_path / "source_identity.json"
    identity_path.write_text(json.dumps({"path":str(snapshot),"commit":"new","files":refs}))
    output=tmp_path / "smoke.json"
    module.prepare(source,output,source_identity_file=identity_path)
    result=json.loads(output.read_text())
    assert result["source_snapshot"]["commit"] == "new"
    assert result["source_snapshot_sha256"] == module.hashlib.sha256(
        json.dumps(result["source_snapshot"], sort_keys=True).encode()).hexdigest()
    assert result["adapter"]["path"] == str(snapshot / "scripts/probe_v5_microwave_public571.py")
    assert result["producer"]["path"] == str(snapshot / "coordination/microwave_runtime_wiring_20261007/prepare_smoke.py")
    assert result["launcher"]["path"] == str(snapshot / "coordination/microwave_runtime_wiring_20261007/run_smoke.sbatch")
    assert len(result["cases"]) == 1
    condition = result["conditions"][result["cases"][0]["condition"]]
    assert condition["max_chunks"] == 8
    assert condition["overrides"]["microwave_identity_tracking_v1"] is True
