"""Startup failures remain evidence and cannot release the next GPU cohort."""

import hashlib
import importlib
import json
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import pytest

import v5_batch_eval as batch
from scripts import probe_v5_moka_transfer_public_20261007 as moka


@pytest.mark.parametrize("failure", [
    {"status": "startup_error", "error": "missing module"},
    {"status": "startup", "error": "not initialized"},
    {"status": "error", "termination_category": "startup_error"},
])
def test_batch_preserves_startup_failure_and_exits_nonzero(monkeypatch, tmp_path, failure):
    import rpent.utils.daemon
    import rpent.utils.rpc

    stopped = []

    class Daemon:
        def __init__(self, **kwargs):
            self.name = kwargs["name"]

        def start(self):
            pass

        def stop(self):
            stopped.append(self.name)

    monkeypatch.setattr(rpent.utils.daemon, "ProcessDaemon", Daemon)
    monkeypatch.setattr(rpent.utils.rpc, "wait_for_ready", lambda *a, **kw: None)
    manifest = tmp_path / "cohort.json"
    episodes = [{"suite": "libero_object", "task": i, "seed": 10} for i in range(2)]
    manifest.write_text(json.dumps({"purpose": "startup contract", "libero_type": "standard",
                                    "episodes": episodes, "budget": {}}))
    output = tmp_path / "job"
    outcomes = iter([failure, {"status": "completed", "correct_finish": False}])
    monkeypatch.setattr(batch, "run_episode", lambda *a, **kw: next(outcomes))
    monkeypatch.setattr(sys, "argv", [
        "batch", "--manifest", str(manifest), "--choice-package", str(tmp_path),
        "--provider", "oracle", "--output-dir", str(output),
        "--pause-marker", str(tmp_path / "absent_pause"),
    ])
    with pytest.raises(SystemExit) as exit_info:
        batch.main()
    assert exit_info.value.code == 1
    rows = [json.loads(line) for line in (output / "episodes.jsonl").read_text().splitlines()]
    assert rows[0]["result"] == failure
    assert rows[1]["result"]["status"] == "completed"
    summary = json.loads((output / "summary.json").read_text())
    assert summary["attempted"] == 2 and summary["startup_error_seen"] is True
    assert sorted(stopped) == ["v5_batch_sam3", "v5_batch_vla"]


def pin(path):
    return {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def test_import_audit_uses_snapshot_not_working_root(monkeypatch, tmp_path):
    source = tmp_path / "snapshot"
    (source / "scripts").mkdir(parents=True)
    harness = source / "harness_v5_eval.py"
    harness.write_text("origin = 'registered snapshot'\n")
    probe = source / "scripts" / "probe_v5_grasp449_20261005.py"
    probe.write_text("origin = 'registered snapshot'\n")
    preparation = tmp_path / "preparation"
    preparation.mkdir()
    (preparation / "typed_choice_eval.py").write_text("origin = 'explicit preparation'\n")
    manifest = preparation / "plan.json"
    plan = {"source_snapshot": {"path": str(source), "files": [pin(harness), pin(probe)]}}
    manifest.write_text(json.dumps(plan))
    monkeypatch.setenv("MOKA_TRANSFER_SOURCE", str(source))
    monkeypatch.setattr(sys, "path", sys.path.copy())
    for name in ("harness_v5_eval", "scripts", "scripts.probe_v5_grasp449_20261005", "typed_choice_eval"):
        monkeypatch.delitem(sys.modules, name, raising=False)
    audit = moka._bootstrap_registered_dependencies(manifest)
    assert Path(audit["path"]) == preparation / "typed_choice_eval.py"
    imported = importlib.import_module("harness_v5_eval")
    imported_probe = importlib.import_module("scripts.probe_v5_grasp449_20261005")
    assert imported.origin == imported_probe.origin == "registered snapshot"
    assert moka._audit_registered_module(plan, imported, "harness_v5_eval.py")["sha256"] == pin(harness)["sha256"]
    assert moka._audit_registered_module(plan, imported_probe, "scripts/probe_v5_grasp449_20261005.py")["path"] == str(probe)
    shadow = tmp_path / "harness_v5_eval.py"
    shadow.write_text("origin = 'working root'\n")
    with pytest.raises(ImportError, match="outside registered snapshot"):
        moka._audit_registered_module(plan, SimpleNamespace(__file__=str(shadow), __name__="harness_v5_eval"), "harness_v5_eval.py")
    harness.write_text("origin = 'changed snapshot'\n")
    with pytest.raises(ValueError, match="Registered runner module changed"):
        moka._audit_registered_module(plan, imported, "harness_v5_eval.py")


@pytest.fixture
def launcher_packet(tmp_path):
    """Exercise the real shell boundary with explicit, CPU-only producer files."""
    root = tmp_path / "runtime"
    source = root / "snapshot"
    preparation = root / "preparation"
    (source / "scripts").mkdir(parents=True)
    preparation.mkdir()
    (root / ".venv" / "bin").mkdir(parents=True)
    (root / ".venv" / "bin" / "python").symlink_to(sys.executable)
    wrapper = source / "scripts" / "probe_v5_moka_transfer_public_20261007.py"
    wrapper.write_text('''import argparse,hashlib,json,os
from pathlib import Path
p=argparse.ArgumentParser(); p.add_argument('--manifest'); p.add_argument('--output'); p.add_argument('--case-name'); p.add_argument('--exclude-case-name',action='append',default=[]); p.add_argument('--shard-index',type=int); p.add_argument('--shards',type=int)
a=p.parse_args(); plan=json.loads(Path(a.manifest).read_text()); out=Path(a.output); out.mkdir()
(out/'actual_argv.json').write_text(json.dumps(vars(a)))
cases=[case for case in plan['cases'] if case['name'] not in a.exclude_case_name]
cases=[case for case in cases if case['name']==a.case_name] if a.case_name else cases[a.shard_index::a.shards]
rows=[{'case':case,'result':{'status':os.environ.get('TEST_RESULT_STATUS','completed')},'server_chunk_execution':{'requested_controls':int(os.environ.get('TEST_CONTROLS','5'))}} for case in cases]
(out/'episodes.jsonl').write_text(''.join(json.dumps(row)+'\\n' for row in rows))
dep=Path(a.manifest).parent/'typed_choice_eval.py'
(out/'startup_dependency_audit.json').write_text(json.dumps({'path':str(dep),'sha256':hashlib.sha256(dep.read_bytes()).hexdigest()}))
''')
    (source / "scripts" / "v5_probe_preflight.py").write_text("print('{}')\n")
    (preparation / "typed_choice_eval.py").write_text("# registered supplement\n")
    archive = source.with_suffix(".tar")
    archive.write_bytes(b"source archive")
    plan = {"source_snapshot": {"path": str(source), "files": [pin(wrapper)],
                                "archive": pin(archive)},
            "qualification_authorized": False, "new_training_rows": 0,
            "selection": {"analysis_role": "development_visited_state_smoke"},
            "producer": pin(wrapper), "producer_dependencies": [],
            "cases": [{"name": f"case{i}"} for i in range(10)]}
    manifest = preparation / "plan.json"
    manifest.write_text(json.dumps(plan))
    launcher = root / "launcher.sbatch"
    original = Path(moka.__file__).with_name("run_v5_moka_transfer_public_smoke10_20261007.sbatch")
    launcher.write_text(original.read_text().replace(
        "MOKA_TRANSFER_ROOT=/public/home/sunyihan/rpent_libero_eval", f"MOKA_TRANSFER_ROOT={root}"))
    env = {**os.environ, "MOKA_TRANSFER_SOURCE": str(source), "MOKA_TRANSFER_MANIFEST": str(manifest),
           "MOKA_TRANSFER_MANIFEST_SHA": pin(manifest)["sha256"],
           "SLURM_JOB_ID": "startup", "SLURM_ARRAY_JOB_ID": "formal", "SLURM_ARRAY_TASK_ID": "0"}
    for key in list(env):
        if key.startswith("MOKA_TRANSFER_") and key not in (
            "MOKA_TRANSFER_SOURCE", "MOKA_TRANSFER_MANIFEST", "MOKA_TRANSFER_MANIFEST_SHA"
        ):
            env.pop(key)
    base = root / "results/harness_v5/moka_transfer_confirmation_prep_CPU_20261007"
    return SimpleNamespace(root=root, source=source, manifest=manifest, launcher=launcher, env=env, base=base)


def run_launcher(packet, **extra_env):
    return subprocess.run(["bash", str(packet.launcher)], env={**packet.env, **extra_env},
                          text=True, capture_output=True, timeout=15)


@pytest.mark.parametrize("status,controls", [("startup_error", "5"), ("completed", "0")])
def test_real_launcher_rejects_startup_or_zero_physical_preflight(launcher_packet, status, controls):
    run = run_launcher(launcher_packet, MOKA_TRANSFER_STARTUP_PREFLIGHT="1",
                       TEST_RESULT_STATUS=status, TEST_CONTROLS=controls)
    assert run.returncode != 0
    probe = launcher_packet.base / "startup_preflight/startup/probe"
    assert (probe / "episodes.jsonl").is_file()
    assert not (probe / "contract.json").exists()


def qualify(packet):
    run = run_launcher(packet, MOKA_TRANSFER_STARTUP_PREFLIGHT="1")
    assert run.returncode == 0, run.stderr
    contract = packet.base / "startup_preflight/startup/probe/contract.json"
    return {"MOKA_TRANSFER_STARTUP_CONTRACT": str(contract),
            "MOKA_TRANSFER_STARTUP_CONTRACT_SHA": pin(contract)["sha256"]}


def test_real_launcher_can_preflight_an_unexecuted_registered_case(launcher_packet):
    run = run_launcher(launcher_packet, MOKA_TRANSFER_STARTUP_PREFLIGHT="1",
                       MOKA_TRANSFER_PREFLIGHT_CASE_NAME="case2")
    assert run.returncode == 0, run.stderr
    contract = launcher_packet.base / "startup_preflight/startup/probe/contract.json"
    assert json.loads(contract.read_text())["case_name"] == "case2"


@pytest.mark.parametrize("status,controls,message", [
    ("startup_error", "5", "startup/infrastructure failures: case1"),
    ("completed", "0", "no requested physical controls: case1"),
])
def test_formal_failures_report_case_names_without_masking_error(launcher_packet, status, controls, message):
    env = qualify(launcher_packet)
    run = run_launcher(launcher_packet, **env, MOKA_TRANSFER_EXCLUDE_CASE_NAMES="case0,case3",
                       TEST_RESULT_STATUS=status, TEST_CONTROLS=controls)
    assert run.returncode == 2
    assert message in run.stderr and "TypeError" not in run.stderr


@pytest.mark.parametrize("mode", ["json_file", "comma_list"])
def test_formal_launcher_excludes_both_retained_attempts(launcher_packet, mode):
    packet = launcher_packet
    contract_env = qualify(packet)
    retained = packet.base / "smoke10/job4378/part3/probe/episodes.jsonl"
    retained.parent.mkdir(parents=True)
    retained.write_text('{"case":"case3","requested_controls":1600}\n')
    original = retained.read_bytes()
    if mode == "json_file":
        excludes = packet.root / "excluded.json"
        excludes.write_text(json.dumps(["case0", "case3"]))
        exclusion_env = {"MOKA_TRANSFER_EXCLUDE_CASES_FILE": str(excludes)}
    else:
        exclusion_env = {"MOKA_TRANSFER_EXCLUDE_CASE_NAMES": "case0,case3"}
    run = run_launcher(packet, **contract_env, **exclusion_env)
    assert run.returncode == 0, run.stderr
    probe = packet.base / "smoke10/jobformal/part0/probe"
    argv = json.loads((probe / "actual_argv.json").read_text())
    assert argv["exclude_case_name"] == ["case0", "case3"]
    rows = [json.loads(line) for line in (probe / "episodes.jsonl").read_text().splitlines()]
    assert [row["case"]["name"] for row in rows] == ["case1"]
    assert retained.read_bytes() == original
    assert (probe / "contract.json").is_file()


@pytest.mark.parametrize("fault", ["missing_contract", "missing_exclusion", "changed_sha", "changed_identity"])
def test_formal_contract_failure_stops_before_any_new_attempt(launcher_packet, fault):
    packet = launcher_packet
    env = qualify(packet)
    env["MOKA_TRANSFER_EXCLUDE_CASE_NAMES"] = "case0,case3"
    if fault == "missing_contract":
        env.pop("MOKA_TRANSFER_STARTUP_CONTRACT")
    elif fault == "missing_exclusion":
        env["MOKA_TRANSFER_EXCLUDE_CASE_NAMES"] = "case3"
    elif fault == "changed_sha":
        env["MOKA_TRANSFER_STARTUP_CONTRACT_SHA"] = "0" * 64
    else:
        path = Path(env["MOKA_TRANSFER_STARTUP_CONTRACT"])
        contract = json.loads(path.read_text())
        contract["launcher_sha256"] = "0" * 64
        path.write_text(json.dumps(contract))
        env["MOKA_TRANSFER_STARTUP_CONTRACT_SHA"] = pin(path)["sha256"]
    run = run_launcher(packet, **env)
    assert run.returncode != 0
    assert not (packet.base / "smoke10/jobformal").exists()
