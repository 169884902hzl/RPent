"""Package explicitly named diagnostic outputs; never enumerate artifacts."""

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent
NAMES = [
    "collect.py", "compare.py", "collect_prefix_diagnosis.py", "test_off320_contract.py",
    "report.json", "paired_report.json", "prefix_diagnosis.json", "REPORT.md", "package.py",
    "off320_packet/prepare_control_packet_source.py", "off320_packet/capture_control_sequence.py",
    "off320_packet/probe_control580_off320.py", "off320_packet/control580_off320_probe_env.py",
    "off320_packet/capture_manifest.json", "off320_packet/preparation_report.json",
    "off320_packet/run_capture.sbatch", "off320_packet/preflight_part0.json",
    "off320_packet/preflight_part1.json", "off320_packet/preflight_part2.json",
    "off320_packet/same_launcher_CPU_summary.json",
]


def identity(path):
    return {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    preparation = json.loads((ROOT / "off320_packet/preparation_report.json").read_text())
    report = json.loads((ROOT / "report.json").read_text())
    prefix = json.loads((ROOT / "prefix_diagnosis.json").read_text())
    manifest = {
        "format": "control580_r3_diagnosis_off320_handoff/1",
        "source_commit": "c56de638fc5a5f0376194768b4d3d484369eb435",
        "physical_r3_job": 4495,
        "r4_first_state_job": 4505,
        "r4_submission_owner": "parent agent",
        "r4_first_state_physical_verified_at_packaging": False,
        "r4_other_states_released": False,
        "source_snapshot": {
            "inherited_immutable_root": "/public/home/sunyihan/rpent_libero_eval/source_v5_stove555_20261006",
            "budget_overlay_root": "/public/home/sunyihan/rpent_libero_eval/results/harness_v5/temporal_control580_capture_CPU_20261007/r4_off320",
            "explicit_imported_source_files": json.loads((ROOT / "off320_packet/capture_manifest.json").read_text())["source_files"],
        },
        "r4_manifest": preparation["manifest"],
        "r4_launcher": preparation["launcher"],
        "r4_single_state_launch_command": preparation["single_state_launch_command"],
        "CPU_verification": {
            "default160_tests": "7/7", "off320_contract_tests": "3/3",
            "same_launcher_preflights": identity(ROOT / "off320_packet/same_launcher_CPU_summary.json"),
            "physical_launch_not_replaced_by_mocks": True,
        },
        "r3_physical_contract": [ref for ref in report["inputs"] if ref["kind"] in (
            "collector_boundary", "episodes", "executed_chunk_ledger", "private_chunk_score_ledger")],
        "files": [identity(ROOT / name) for name in NAMES],
        "r3_remote_inputs": report["inputs"],
        "prefix_remote_inputs": prefix["inputs"],
        "confirmation_registry_complete": False,
        "registered_confirmation_overlap": 0,
        "training_allowed": False,
        "freeze_evidence": False,
        "private_truth_controls_budget_or_stop": False,
        "stop_admitted": False,
        "read_mode": "explicit manifest/ledger paths only",
    }
    path = ROOT / "manifest.json"
    if path.exists():
        raise FileExistsError(path)
    path.write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps(identity(path)))


if __name__ == "__main__":
    main()
