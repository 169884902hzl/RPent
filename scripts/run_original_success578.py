"""Own the original-only passive metrology hooks in one diagnostic process."""
import dataclasses
import os
import sys
from pathlib import Path


def instrument_execute(original):
    def execute(executor, action, view, resolved_card, result):
        sequence = getattr(executor, "_success578_sequence", 0)
        effective = resolved_card if action.tool == "card_next" and resolved_card is not None else action
        entities = executor.scene.entities
        def measured(key):
            item = entities.get(key)
            return {"name": item.name, "xyz": list(item.xyz)} if item is not None else None
        client = executor.p.env._client
        client.call("diagnostic.action_begin", sequence=sequence, action=dataclasses.asdict(effective),
                    source=measured(effective.object), target=measured(effective.target), timeout_s=120)
        executor._success578_sequence = sequence + 1
        try:
            return original(executor, action, view, resolved_card, result)
        finally:
            client.call("diagnostic.action_end", timeout_s=120)
    return execute


def main():
    import argparse
    import importlib.util
    import harness_v5_eval
    from rpent.utils.daemon import ProcessDaemon
    p = argparse.ArgumentParser()
    p.add_argument("--batch-runner", type=Path, required=True)
    args, rest = p.parse_known_args()
    if os.environ.get("LIBERO_TYPE") != "standard":
        p.error("truth diagnosis never runs on PRO/MAX")
    old_init = ProcessDaemon.__init__
    def initialize(self, *a, **kw):
        cmd = list(kw["cmd"])
        if "robots.libero.v5_env_server" in cmd:
            index = cmd.index("robots.libero.v5_env_server")
            cmd[index] = "original_success578_server"
            label_path = Path(kw["log_path"]).with_name("private_action_labels.jsonl")
            cmd += ["--private-label-path", str(label_path)]
            kw["cmd"] = cmd
        old_init(self, *a, **kw)
    ProcessDaemon.__init__ = initialize
    harness_v5_eval._execute_action = instrument_execute(harness_v5_eval._execute_action)
    spec = importlib.util.spec_from_file_location("success578_batch", args.batch_runner.resolve(strict=True))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    sys.argv = [str(args.batch_runner), *rest]
    module.main()


if __name__ == "__main__":
    main()
