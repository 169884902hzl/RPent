"""Owned original five-state sampler; append retreat sequences to fixed probe."""

import argparse
import json
from pathlib import Path
import sys
from types import SimpleNamespace

from public_temporal_verifier import identity
from sample_public_sequence import capture_public_sequence


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--sampling-manifest", type=Path, required=True)
    parser.add_argument("--sampling-manifest-sha256", required=True)
    parser.add_argument("--shard-index", type=int, required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--preflight-only", action="store_true")
    parser.add_argument("--preflight-report", type=Path)
    args = parser.parse_args()
    if identity(args.sampling_manifest)["sha256"] != args.sampling_manifest_sha256:
        raise ValueError("sampling manifest changed")
    sampling = json.loads(args.sampling_manifest.read_text())
    for r in sampling["owned_sources"]:
        if identity(r["path"])["sha256"] != r["sha256"]:
            raise ValueError("sampler source changed")
    if sampling["phase_hold_controls"] != {"before_off": 0, "after_release": 12, "after_retreat": 12}:
        raise ValueError("fixed public sampling schedule changed")
    import probe_public_red_recovery as probe
    probe.load_inputs(SimpleNamespace(manifest=Path(sampling["parent_manifest"]["path"]),
        expected_manifest_sha256=sampling["parent_manifest"]["sha256"], shard_index=args.shard_index,
        check_states=True))
    if args.preflight_only:
        result = {"passed": True, "cwd": str(Path.cwd()), "sampling_manifest": identity(args.sampling_manifest),
            "case": sampling["cases"][args.shard_index]["name"], "source_files_checked": len(sampling["owned_sources"]),
            "simulator_started": False, "gpu_services_started": False, "private_labels_control_sampling": False}
        if args.preflight_report:
            args.preflight_report.parent.mkdir(parents=True, exist_ok=True)
            args.preflight_report.write_text(json.dumps(result, indent=2) + "\n")
        print(json.dumps(result)); return
    from scripts import probe_v5_stove521_endpoint as inherited
    original_capture = inherited.capture_measurements
    def augmented_capture(executor, sam_rpc, oracle_rpc, case, plan, destination, **kwargs):
        result = original_capture(executor, sam_rpc, oracle_rpc, case, plan, destination, **kwargs)
        phase = destination.name
        if phase in sampling["phase_hold_controls"]:
            shells = [e for e in executor.scene.entities.values() if e.name == "stove"]
            entity = shells[0] if len(shells) == 1 else None
            public_sequence = capture_public_sequence(executor, entity, destination / "temporal", phase=phase,
                gripper_control=1 if phase == "before_off" else -1,
                controls_between_frames=0 if phase == "before_off" else 6)
            # Read after the fixed sequence; never feed this result to sampling.
            try:
                label = {"status": "scored", "private_labels": {mode: oracle_rpc.call("oracle.skill501_truth",
                    kwargs={"spec": {"kind": "articulate", "mode": mode, "object_symbol": "flat_stove_1"}},
                    timeout_s=120) for mode in ("turn_on", "turn_off")}}
            except Exception as error:
                label = {"status": "unknown_private_scoring_error", "private_labels": None, "error": repr(error)}
            label_path = destination / "temporal" / "private_final_frame_label.json"
            from scripts.probe_v5_skill501_original import diagnostic_json
            label_path.write_text(diagnostic_json({"judge": "measured_predicate_private_joint", "last_frame_only": True,
                "controller_access": False, **label}, indent=2) + "\n")
            result["public_temporal_sequence"] = public_sequence
            result["private_temporal_final_label"] = identity(label_path)
        return result
    inherited.capture_measurements = augmented_capture
    sys.argv = [str(Path(probe.__file__)), "--manifest", sampling["parent_manifest"]["path"],
        "--expected-manifest-sha256", sampling["parent_manifest"]["sha256"],
        "--shard-index", str(args.shard_index), "--output", str(args.output)]
    probe.main()


if __name__ == "__main__":
    main()
