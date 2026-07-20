"""Readiness polling and OpenAI-compatible smoke testing."""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any

import httpx

from runpod_vllm.errors import ApiError, NetworkError, ReadinessTimeout
from runpod_vllm.models import ReadinessResult
from runpod_vllm.redaction import redact_text, redact_url


def wait_until_ready(
    base_url: str,
    *,
    timeout: float = 900.0,
    interval: float = 5.0,
    client: httpx.Client | None = None,
    monotonic: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], None] = time.sleep,
) -> ReadinessResult:
    if timeout <= 0 or interval <= 0:
        raise ValueError("timeout and interval must be positive")
    owns_client = client is None
    http = client or httpx.Client(timeout=10.0)
    started = monotonic()
    attempts = 0
    last_diagnostic = "no response"
    try:
        while True:
            attempts += 1
            try:
                health = http.get(f"{base_url.rstrip('/')}/health")
                models = http.get(f"{base_url.rstrip('/')}/v1/models")
                if health.status_code == 200 and models.status_code == 200:
                    payload = models.json()
                    entries = payload.get("data", []) if isinstance(payload, dict) else []
                    model_ids = tuple(
                        str(item["id"])
                        for item in entries
                        if isinstance(item, dict) and item.get("id")
                    )
                    if model_ids:
                        return ReadinessResult(
                            base_url=base_url.rstrip("/"),
                            model_ids=model_ids,
                            attempts=attempts,
                            elapsed_seconds=monotonic() - started,
                        )
                    last_diagnostic = "models endpoint returned no model IDs"
                else:
                    last_diagnostic = (
                        f"health HTTP {health.status_code}, models HTTP {models.status_code}"
                    )
            except (httpx.RequestError, ValueError) as exc:
                last_diagnostic = redact_text(str(exc))
            elapsed = monotonic() - started
            if elapsed >= timeout:
                raise ReadinessTimeout(
                    f"vLLM was not ready after {elapsed:.1f}s and {attempts} attempts. "
                    f"Last diagnostic: {last_diagnostic}"
                )
            sleep(min(interval, max(0.0, timeout - elapsed)))
    finally:
        if owns_client:
            http.close()


def smoke_test_endpoint(
    base_url: str,
    *,
    model: str,
    bearer_token: str | None = None,
    timeout: float = 30.0,
    client: httpx.Client | None = None,
) -> dict[str, Any]:
    headers = {"Authorization": f"Bearer {bearer_token}"} if bearer_token else {}
    owns_client = client is None
    http = client or httpx.Client(timeout=timeout)
    url = f"{base_url.rstrip('/')}/v1/chat/completions"
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": "Reply with the single word: ready"}],
        "max_tokens": 4,
        "temperature": 0,
        "seed": 0,
    }
    try:
        try:
            response = http.post(url, headers=headers, json=payload)
        except httpx.RequestError as exc:
            raise NetworkError(
                f"Smoke test request failed for {redact_url(url)}: {redact_text(str(exc))}"
            ) from exc
        if response.status_code >= 400:
            raise ApiError(
                f"Smoke test returned HTTP {response.status_code}: "
                f"{redact_text(response.text[:500])}"
            )
        try:
            data = response.json()
        except ValueError as exc:
            raise ApiError("Smoke test returned invalid JSON.") from exc
        if not isinstance(data, dict) or not data.get("choices"):
            raise ApiError("Smoke test response did not contain choices.")
        return data
    finally:
        if owns_client:
            http.close()
