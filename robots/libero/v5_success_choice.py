"""Opt-in grasp ranking diagnostic using predictions on the same pre-state."""

import json
import hashlib
import math
import time
from urllib.error import HTTPError
from urllib.request import Request, urlopen


def success_payload(context: str, action: str) -> dict:
    """Use the exact question spelling evaluated by the saved-state probe."""
    return {"state": context, "questions": {"success": {
        "type": "choice", "instructions": f"Will executing {action} now pass its measured physical success check? Predict from the current state and earlier receipts only.",
        "criteria": {"C0": "The action will fail its physical success check.",
                     "C1": "The action will pass its physical success check."}}}}


def predict_success(endpoint: str, context: str, action: str) -> dict:
    """Return a success prediction without altering the state text."""
    payload = success_payload(context, action)
    url = endpoint.rstrip("/")
    if not url.endswith("/v1/systemone"):
        url += "/v1/systemone"
    request = Request(url, data=json.dumps(payload, ensure_ascii=False).encode(),
                      headers={"Content-Type": "application/json"}, method="POST")
    started = time.perf_counter()
    try:
        with urlopen(request, timeout=180) as response:
            reply = json.load(response)
    except HTTPError as error:
        raise RuntimeError(f"System One HTTP {error.code}: {error.read().decode()}") from error
    probability = float(reply["answers"]["success"]["probabilities"]["C1"])
    if not math.isfinite(probability) or not 0 <= probability <= 1:
        raise ValueError("invalid pre-action success probability")
    compute = reply.get("timing_ms", {}).get("compute")
    return {"p_success": probability, "request": payload, "response": reply,
            "http_round_trip_s": time.perf_counter() - started,
            "model_inference_s": float(compute) / 1000 if compute is not None else None}


def diagnose_selected_success(endpoint: str, context: str, options: list[str], answer: dict) -> dict:
    """Record an online prediction for the action that will actually execute."""
    index = int(answer["selected"])
    if not 0 <= index < len(options):
        raise ValueError("selected action outside registered candidates")
    prediction = predict_success(endpoint, context, options[index])
    result = {**answer, "pre_action_success_diagnostic": {
        "candidate_index": index, "candidate": options[index],
        "context_sha256": hashlib.sha256(context.encode()).hexdigest(),
        "phase": "before_physical_branches_and_execution",
        "p_success": prediction["p_success"], "prediction": prediction,
        "selection_changed": False}}
    result["http_round_trip_s"] = answer["http_round_trip_s"] + prediction["http_round_trip_s"]
    times = (answer.get("model_inference_s"), prediction["model_inference_s"])
    result["model_inference_s"] = sum(times) if all(t is not None for t in times) else None
    return result


def rerank_grasp(endpoint: str, context: str, options: list[str], answer: dict) -> dict:
    """Rank grasp alternatives among the top three action-choice candidates.

Non-grasp selections retain their existing behavior. Saved-state diagnosis
supports grasp discrimination; place remains near chance and is not reranked.
The original action distribution is preserved separately from success scores.
"""
    if not options[answer["selected"]].startswith("grasp("):
        return answer
    probabilities = answer["probabilities"]
    indices = sorted(range(len(options)), key=lambda index: -probabilities[f"C{index}"])[:3]
    eligible = [index for index in indices if options[index].startswith("grasp(")]
    if len(eligible) < 2:
        return answer
    predictions = []
    for index in eligible:
        result = predict_success(endpoint, context, options[index])
        predictions.append({"candidate_index": index, "candidate": options[index],
                            "p_success": result["p_success"],
                            "prediction": result})
    chosen = max(predictions, key=lambda row: row["p_success"])["candidate_index"]
    result = {**answer, "selected": chosen, "top3_success_diagnostic": {
        "original_selected": answer["selected"], "top3_by_action_probability": indices,
        "predictions": predictions, "selection_scope": "grasp_only",
        "absolute_success_probabilities_calibrated": False}}
    result["http_round_trip_s"] = answer["http_round_trip_s"] + sum(p["prediction"]["http_round_trip_s"] for p in predictions)
    times = [answer.get("model_inference_s"), *[p["prediction"]["model_inference_s"] for p in predictions]]
    result["model_inference_s"] = sum(times) if all(t is not None for t in times) else None
    return result
