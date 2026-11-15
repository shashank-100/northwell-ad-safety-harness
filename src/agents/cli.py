"""The only place a model is called: one headless `claude -p` process per call."""
import json
import subprocess
import time

from src.harness.retry import InfraError


def call(model, system, user, schema, *, role, timeout_s=180):
    failure = {"writer": "WRITER_FAILURE", "reviewer": "REVIEWER_FAILURE"}[role]
    start = time.time()
    try:
        proc = subprocess.run(
            ["claude", "-p", user, "--model", model, "--system-prompt", system, "--tools", "",
             "--no-session-persistence", "--output-format", "json", "--json-schema", json.dumps(schema)],
            capture_output=True, text=True, timeout=timeout_s, cwd="/tmp")
    except subprocess.TimeoutExpired as e:
        raise InfraError("TIMEOUT", f"{role} ({model}) timed out after {timeout_s}s") from e
    try:
        out = json.loads(proc.stdout)
    except json.JSONDecodeError as e:
        raise InfraError(failure, f"{role} ({model}) returned non-JSON: {proc.stderr[-300:]}") from e
    if out.get("is_error"):
        raise InfraError(failure, f"{role} ({model}) error: {out.get('result', '')[:300]}")
    usage = out.get("usage", {})
    return {
        "data": out.get("structured_output"),  # may be None/garbage: callers validate, never trust
        "model": model,
        "cost": out.get("total_cost_usd", 0.0),
        "tokens": {"input": usage.get("input_tokens", 0) + usage.get("cache_creation_input_tokens", 0)
                   + usage.get("cache_read_input_tokens", 0), "output": usage.get("output_tokens", 0)},
        "latency_ms": int((time.time() - start) * 1000),
    }
