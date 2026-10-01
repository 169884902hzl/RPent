#!/bin/bash
# Run inside the existing vLLM service allocation; no GPU allocation added.
set -euo pipefail
ROOT=/public/home/sunyihan/rpent_libero_eval
SERVICE_OUT="$ROOT/results/harness_v5/a1m_vllm_probe_20261001/service_job${SLURM_JOB_ID:?}"
OUT="$SERVICE_OUT/full_audit"
mkdir -p "$OUT/runtime"
cp "$ROOT/scripts/a1m_vllm_full_audit_20261001/m2_api.py" "$OUT/runtime/"
sha256sum "$OUT/runtime/m2_api.py" "$ROOT/scripts/run_a1m_full_audit_step_20261001.sh" > "$OUT/source.sha256"
export PYTHONPATH="$OUT/runtime" M2_BACKEND_KIND=vllm M2_BACKEND_URL=http://127.0.0.1:18052
export A1M_BACKEND_AUDIT="$OUT/backend_responses.jsonl"
export A1M_NO_TOOL_REQUEST_AUDIT="$OUT/no_tool_requests.jsonl"
cd "$OUT/runtime"
"$ROOT/runtime_vllm019_a1m_20261001/bin/python" -m uvicorn m2_api:app --host 0.0.0.0 --port 18369 --no-access-log > "$OUT/gateway.log" 2>&1 &
GATEWAY_PID=$!
trap 'kill "$GATEWAY_PID" 2>/dev/null || true' EXIT
while kill -0 "$GATEWAY_PID" 2>/dev/null; do
    if test -f "$SERVICE_OUT/EVALUATION_DONE"; then exit 0; fi
    sleep 2
done
wait "$GATEWAY_PID"
