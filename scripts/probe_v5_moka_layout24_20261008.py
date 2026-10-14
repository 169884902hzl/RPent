"""Use the pinned placement582r2 runner with an auditable layout-reset server."""

from pathlib import Path
import json
import os
import sys


def main():
    from rpent.utils import daemon
    from scripts import probe_v5_moka_transfer_public_20261007 as runner

    original_daemon = daemon.ProcessDaemon
    original_execute = runner.execute_original_subtask
    server = Path(__file__).with_name("serve_v5_moka_layout24_20261008.py")
    plan = json.loads(Path(sys.argv[sys.argv.index("--manifest") + 1]).read_text())
    stop_settings = {bool(condition.get("native_task_stop_v1", False))
                     for condition in plan["conditions"].values()}
    if len(stop_settings) != 1:
        raise ValueError("native-task stop conditions require separate original-task servers")
    native_stop = stop_settings.pop()
    if native_stop and any(not case.get("original_goal_source") for case in plan["cases"]):
        raise ValueError("native completion stop requires the unmodified original task goal")
    previous_native_stop = os.environ.get("MOKA_TRANSFER_NATIVE_TASK_STOP_V1")
    os.environ["MOKA_TRANSFER_NATIVE_TASK_STOP_V1"] = "1" if native_stop else "0"

    class LayoutDaemon(original_daemon):
        def __init__(self, *args, **kwargs):
            command = list(kwargs.get("cmd", []))
            for index, value in enumerate(command):
                if Path(value).name == "serve_v5_moka_transfer_registered_20261007.py":
                    command[index] = str(server)
            kwargs["cmd"] = command
            super().__init__(*args, **kwargs)

    def execute(executor, case, condition, obj, receipt, evidence):
        # The extra read-only audit is kept in the private ledger even if public
        # binding fails before the unchanged skill enters contact execution.
        evidence["registered_reset_evidence"] = executor.p.env._client.call(
            "diagnostic.moka_registered_reset", timeout_s=30)
        return original_execute(executor, case, condition, obj, receipt, evidence)

    daemon.ProcessDaemon = LayoutDaemon
    runner.execute_original_subtask = execute
    try:
        runner.main()
    finally:
        daemon.ProcessDaemon = original_daemon
        runner.execute_original_subtask = original_execute
        if previous_native_stop is None:
            os.environ.pop("MOKA_TRANSFER_NATIVE_TASK_STOP_V1", None)
        else:
            os.environ["MOKA_TRANSFER_NATIVE_TASK_STOP_V1"] = previous_native_stop


if __name__ == "__main__":
    main()
