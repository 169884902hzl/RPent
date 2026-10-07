"""Own the original-only passive metrology hooks in one diagnostic process."""
import dataclasses
import hashlib
import json
import os
import sys
import time
from pathlib import Path


ACTIVE = None


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     ensure_ascii=False).encode()).hexdigest()


def ref(path):
    path = Path(path).resolve(strict=True)
    return {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def append(path, row):
    with Path(path).open("a") as handle:
        handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def instrument_score(original):
    def score(scorer, **request):
        answer = original(scorer, **request)
        if ACTIVE is not None:
            ACTIVE["request"] = request
            ACTIVE["answer"] = answer
        return answer
    return score


def instrument_prediction(original):
    def predict(*args, **kwargs):
        answer = original(*args, **kwargs)
        if ACTIVE is not None:
            ACTIVE["answer"] = answer
        return answer
    return predict


def instrument_execute(original):
    def execute(executor, action, view, resolved_card, result):
        sequence = getattr(executor, "_success578_sequence", 0)
        effective = resolved_card if action.tool == "card_next" and resolved_card is not None else action
        entities = executor.scene.entities
        def measured(key):
            item = entities.get(key)
            return {"name": item.name, "xyz": list(item.xyz)} if item is not None else None
        client = executor.p.env._client
        identity = None
        if ACTIVE is not None:
            request, answer = ACTIVE["request"], ACTIVE["answer"]
            prediction = answer.get("pre_action_success_diagnostic", {})
            selected = int(answer["selected"])
            state_sha = hashlib.sha256(request["context"].encode()).hexdigest()
            if prediction and (prediction["candidate_index"] != selected
                               or prediction["context_sha256"] != state_sha):
                raise ValueError("pre-action prediction differs from the executed state/action")
            identity = {"run_id": ACTIVE["run_id"], "episode": ACTIVE["episode"],
                        "decision": sequence, "state_sha256": state_sha,
                        "request_sha256": digest(request), "candidate_index": selected,
                        "candidate": request["options"][selected],
                        "selected_action_sha256": digest(dataclasses.asdict(action)),
                        "effective_action_sha256": digest(dataclasses.asdict(effective))}
            identity["state_action_key"] = digest(identity)
            # This metadata is logged in choices.answer, never serialized into
            # model-visible state, candidates or skill receipts.
            answer["passive_label_identity"] = identity
            append(ACTIVE["output"] / "pre_action_predictions.jsonl", {
                **identity, "phase": "before_physical_execution", "recorded_at_ns": time.time_ns(),
                "p_success": prediction.get("p_success"),
                "prediction": prediction.get("prediction"),
                "prediction_request_sha256": hashlib.sha256(json.dumps(prediction["prediction"]["request"], ensure_ascii=False).encode()).hexdigest() if prediction else None,
                "action_request_sha256": hashlib.sha256(json.dumps(answer["systemone_request"], ensure_ascii=False).encode()).hexdigest() if "systemone_request" in answer else None,
                "model_identity": ACTIVE["model_identity"], "behavior_changed": False})
        client.call("diagnostic.action_begin", kwargs={
            "sequence": sequence, "action": dataclasses.asdict(effective),
            "source": measured(effective.object), "target": measured(effective.target),
            **({"identity": identity} if identity is not None else {}),
        }, timeout_s=120)
        executor._success578_sequence = sequence + 1
        try:
            return original(executor, action, view, resolved_card, result)
        finally:
            client.call("diagnostic.action_end", timeout_s=120)
    return execute


def export_pairs(output, runtime_manifest, model_identity_path):
    """Read only paths in the current ledger; never discover old artifacts."""
    output = Path(output)
    ledger = output / "episodes.jsonl"
    files, pairs, finishes = [], [], []
    if not ledger.is_file():
        return
    for line in ledger.read_text().splitlines():
        row = json.loads(line)
        episode_dir = Path(row["output_dir"])
        choices_path = episode_dir / "choices.jsonl"
        prediction_path = episode_dir / "pre_action_predictions.jsonl"
        labels_path = episode_dir / "private_action_labels.jsonl"
        files.append({"episode": row["episode"], "status": row["result"].get("status"),
                      "files": {name: ref(path) for name, path in (
                          ("choices", choices_path), ("predictions", prediction_path),
                          ("private_action_labels", labels_path)) if path.is_file()}})
        if not prediction_path.is_file():
            continue
        choices = {}
        if choices_path.is_file():
            for item in map(json.loads, choices_path.read_text().splitlines()):
                key = item["answer"].get("passive_label_identity", {}).get("state_action_key")
                if key in choices:
                    raise ValueError("duplicate same-run choice key")
                choices[key] = item
        labels = {}
        if labels_path.is_file():
            for item in map(json.loads, labels_path.read_text().splitlines()):
                key = item["identity"]["state_action_key"]
                if key in labels:
                    raise ValueError("duplicate same-run private label key")
                labels[key] = item
        for prediction in map(json.loads, prediction_path.read_text().splitlines()):
            key = prediction["state_action_key"]
            choice, label = choices.get(key), labels.get(key)
            if label is not None and label["identity"] != {k: prediction[k] for k in label["identity"]}:
                raise ValueError("private label identity differs from execution-before prediction")
            record = {k: prediction[k] for k in (
                "run_id", "episode", "decision", "state_action_key", "state_sha256", "request_sha256",
                "candidate_index", "candidate", "selected_action_sha256", "effective_action_sha256",
                "p_success", "prediction_request_sha256", "action_request_sha256", "model_identity")}
            record.update(simulation_truth=label["simulation_truth"] if label else None,
                          label_rule=label["label_rule"] if label else "missing_private_sidecar",
                          choice_persisted=choice is not None, private_label_persisted=label is not None,
                          label_source="same_run_passive_simulation_sidecar", may_train=False)
            (finishes if label and label["action"]["tool"] == "finish"
             or prediction["candidate"].startswith("finish") else pairs).append(record)
    pair_path, finish_path = output / "paired_action_outcomes.jsonl", output / "finish_outcomes.jsonl"
    for path, rows in ((pair_path, pairs), (finish_path, finishes)):
        path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows))
    known = [r for r in pairs if r["simulation_truth"] is not None and r["p_success"] is not None
             and r["choice_persisted"]]
    manifest = {"schema": "same_run_success578/2", "ledger": ref(ledger),
                "runtime_manifest": ref(runtime_manifest), "model_identity": ref(model_identity_path),
                "episodes": files, "pairs": ref(pair_path), "finish": ref(finish_path),
                "counts": {"actions": len(pairs), "finish": len(finishes), "auroc_eligible": len(known),
                           "truth_unknown": sum(r["simulation_truth"] is None for r in pairs),
                           "prediction_unknown": sum(r["p_success"] is None for r in pairs),
                           "missing_persisted_choice": sum(not r["choice_persisted"] for r in pairs)},
                "truth_private_sidecar_only": True, "diagnostic_control_steps": 0,
                "state_action_key_encoding": "canonical_json_sort_keys_utf8",
                "service_request_hash_encoding": "actual_json_dumps_ensure_ascii_false_utf8",
                "old4103_records_used": False, "training_allowed": False}
    (output / "pairing_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")


def main():
    import argparse
    import importlib.util
    import harness_v5_eval
    from rpent.utils.daemon import ProcessDaemon
    p = argparse.ArgumentParser()
    p.add_argument("--batch-runner", type=Path, required=True)
    p.add_argument("--model-identity", type=Path, required=True)
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
    from typed_choice_eval import ChoiceScorer
    from robots.libero import v5_success_choice
    ChoiceScorer.score = instrument_score(ChoiceScorer.score)
    v5_success_choice.diagnose_selected_success = instrument_prediction(v5_success_choice.diagnose_selected_success)
    manifest_path = Path(rest[rest.index("--manifest") + 1]).resolve(strict=True)
    output = Path(rest[rest.index("--output-dir") + 1]).resolve()
    health = json.loads(args.model_identity.read_text())
    model_identity = {"service_health": health, "service_health_file": ref(args.model_identity),
                      "runtime_manifest": ref(manifest_path)}
    original_episode = harness_v5_eval.run_episode
    def run_episode(run_args, **kw):
        global ACTIVE
        ACTIVE = {"episode": {k: getattr(run_args, k) for k in ("suite", "task", "seed")},
                  "output": Path(run_args.output_dir), "model_identity": model_identity,
                  "run_id": digest({"manifest": ref(manifest_path), "output": str(output),
                                    "model_identity": model_identity})}
        try:
            return original_episode(run_args, **kw)
        finally:
            ACTIVE = None
    harness_v5_eval.run_episode = run_episode
    spec = importlib.util.spec_from_file_location("success578_batch", args.batch_runner.resolve(strict=True))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    sys.argv = [str(args.batch_runner), *rest]
    try:
        module.main()
    finally:
        export_pairs(output, manifest_path, args.model_identity)


if __name__ == "__main__":
    main()
