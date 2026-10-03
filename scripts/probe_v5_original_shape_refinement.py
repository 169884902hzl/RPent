"""Record real wrist refinement and private reference poses on original tasks."""

from robots.libero.v5_runtime import V5Executor
from robots.libero.v5_state import entity_record


def install_probe():
    original = V5Executor._execute

    def execute(self, action, receipt, card):
        if action.tool != "grasp":
            return original(self, action, receipt, card)
        refresh = self.scene.refresh

        def measured_refresh(*args, **kwargs):
            result = refresh(*args, **kwargs)
            if kwargs.get("camera_view") == "wrist":
                measured = self.scene.entities.get(action.object)
                self.motion_evidence.append({
                    "name": "shape_probe_wrist",
                    "scope": "original_task_private_diagnostic_only",
                    "measurement": entity_record(measured) if measured else None,
                    "reference": self.p.env._client.call(
                        "oracle.measurement_reference", timeout_s=120),
                })
            return result

        self.scene.refresh = measured_refresh
        try:
            return original(self, action, receipt, card)
        finally:
            self.scene.refresh = refresh

    V5Executor._execute = execute


if __name__ == "__main__":
    import json
    import sys
    from pathlib import Path

    manifest = Path(sys.argv[sys.argv.index("--manifest") + 1])
    data = json.loads(manifest.read_text())
    if ("--collection-config" in sys.argv or "--provider" not in sys.argv
            or sys.argv[sys.argv.index("--provider") + 1] != "oracle"
            or data["libero_type"] != "standard"
            or data["budget"]["max_decisions"] != 1
            or not data["budget"].get("wrist_refine_v1")):
        raise ValueError("shape probe requires one original-task expert grasp with wrist refinement")
    install_probe()
    from v5_batch_eval import main
    main()
