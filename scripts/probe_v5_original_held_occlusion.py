"""Remeasure a held original-task object from the wrist before its first place.

This diagnostic uses real RGB-D and SAM responses. Missing detections are
never injected, and a visible result is reported as absent occlusion coverage.
It emits no training rows and does not change the production entry point.
"""

from robots.libero.v5_runtime import V5Executor
from robots.libero.v5_state import entity_record


def install_probe():
    original = V5Executor._execute

    def execute(self, action, receipt, card):
        if (action.tool == "place" and self.held == action.object
                and not getattr(self, "_held_occlusion_probe_done", False)):
            self._held_occlusion_probe_done = True
            obj = self.scene.entities[action.object]
            self.capture()
            self.scene.refresh([obj.name], camera_view="wrist")
            measured = self.scene.entities[action.object]
            receipt.update(
                occlusion_probe="current_wrist_rgbd_before_first_place",
                occlusion_probe_measurement=entity_record(measured),
                occlusion_probe_missing=not measured.visible,
            )
        return original(self, action, receipt, card)

    V5Executor._execute = execute


if __name__ == "__main__":
    import json
    import sys
    from pathlib import Path

    manifest = Path(sys.argv[sys.argv.index("--manifest") + 1])
    data = json.loads(manifest.read_text())
    if ("--collection-config" in sys.argv or "--provider" not in sys.argv
            or sys.argv[sys.argv.index("--provider") + 1] != "oracle"
            or data["libero_type"] != "standard"):
        raise ValueError("held occlusion probe permits original-task diagnostics only")
    install_probe()
    from v5_batch_eval import main
    main()
