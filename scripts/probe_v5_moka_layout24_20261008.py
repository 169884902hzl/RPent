"""Use the pinned placement582r2 runner with an auditable layout-reset server."""

from pathlib import Path


def main():
    from rpent.utils import daemon
    from scripts import probe_v5_moka_transfer_public_20261007 as runner

    original_daemon = daemon.ProcessDaemon
    original_execute = runner.execute_original_subtask
    server = Path(__file__).with_name("serve_v5_moka_layout24_20261008.py")

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


if __name__ == "__main__":
    main()
