"""Minimal RunPod REST API client."""

from __future__ import annotations

import random
import time
from collections.abc import Callable
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from typing import Any

import httpx

from runpod_vllm.errors import ApiError, NetworkError, RateLimitError
from runpod_vllm.redaction import redact_text, redact_url

DEFAULT_MAX_RETRIES = 5
DEFAULT_BACKOFF_BASE = 1.0
DEFAULT_BACKOFF_CAP = 60.0

_RATE_LIMITED = 429
_TRANSIENT_STATUSES = frozenset({502, 503, 504})
_IDEMPOTENT_METHODS = frozenset({"GET", "DELETE"})


def parse_retry_after(value: str | None, *, now: datetime | None = None) -> float | None:
    """Return the wait in seconds from a Retry-After header, or None when unusable."""
    if value is None:
        return None
    value = value.strip()
    if not value:
        return None
    if value.isdigit():
        return float(value)
    try:
        when = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return None
    if when.tzinfo is None:
        when = when.replace(tzinfo=UTC)
    current = now or datetime.now(UTC)
    return max(0.0, (when - current).total_seconds())


class RunPodClient:
    def __init__(
        self,
        api_key: str,
        *,
        base_url: str = "https://rest.runpod.io/v1",
        timeout: float = 30.0,
        transport: httpx.BaseTransport | None = None,
        max_retries: int = DEFAULT_MAX_RETRIES,
        backoff_base: float = DEFAULT_BACKOFF_BASE,
        backoff_cap: float = DEFAULT_BACKOFF_CAP,
        sleep: Callable[[float], None] = time.sleep,
        random_fn: Callable[[], float] = random.random,
    ) -> None:
        if max_retries < 0:
            raise ValueError("max_retries must be zero or greater.")
        if backoff_base < 0 or backoff_cap < 0:
            raise ValueError("Backoff values must be zero or greater.")
        self._max_retries = max_retries
        self._backoff_base = backoff_base
        self._backoff_cap = backoff_cap
        self._sleep = sleep
        self._random = random_fn
        self._client = httpx.Client(
            base_url=base_url.rstrip("/"),
            timeout=timeout,
            transport=transport,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        )

    def __enter__(self) -> RunPodClient:
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()

    def close(self) -> None:
        self._client.close()

    def _backoff_delay(self, attempt: int) -> float:
        """Exponential backoff with full jitter: uniform in [0, min(cap, base * 2**attempt)]."""
        ceiling = min(self._backoff_cap, self._backoff_base * (2.0**attempt))
        return self._random() * ceiling

    def _retry_delay(self, response: httpx.Response, attempt: int) -> float:
        retry_after = parse_retry_after(response.headers.get("Retry-After"))
        if retry_after is not None:
            return min(retry_after, self._backoff_cap)
        return self._backoff_delay(attempt)

    def _should_retry(self, method: str, status_code: int) -> bool:
        # A 429 means RunPod rejected the request before acting on it, so retrying
        # is safe for every method, including the billable POST /pods.
        if status_code == _RATE_LIMITED:
            return True
        # Gateway errors can hide a request that was applied, so only replay
        # methods that are idempotent.
        return status_code in _TRANSIENT_STATUSES and method.upper() in _IDEMPOTENT_METHODS

    def _request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        attempt = 0
        while True:
            try:
                response = self._client.request(method, path, **kwargs)
            except httpx.RequestError as exc:
                url = redact_url(str(exc.request.url)) if exc.request else path
                raise NetworkError(
                    f"RunPod request failed for {url}: {redact_text(str(exc))}"
                ) from exc
            if attempt >= self._max_retries or not self._should_retry(method, response.status_code):
                break
            self._sleep(self._retry_delay(response, attempt))
            attempt += 1

        if response.status_code == _RATE_LIMITED:
            retry_after = parse_retry_after(response.headers.get("Retry-After"))
            hint = (
                f" RunPod suggested waiting {retry_after:.0f}s." if retry_after is not None else ""
            )
            raise RateLimitError(
                f"RunPod API rate limit hit (HTTP 429) for "
                f"{redact_url(str(response.request.url))} after {attempt + 1} attempt(s).{hint} "
                "Wait before retrying and reduce request frequency.",
                retry_after=retry_after,
            )
        if response.status_code >= 400:
            body = redact_text(response.text[:500]).strip() or "no response body"
            raise ApiError(
                f"RunPod API returned HTTP {response.status_code} for "
                f"{redact_url(str(response.request.url))}: {body}",
                status_code=response.status_code,
            )
        return response

    @staticmethod
    def _json_object(response: httpx.Response) -> dict[str, Any]:
        try:
            data = response.json()
        except ValueError as exc:
            raise ApiError("RunPod API returned invalid JSON.") from exc
        if not isinstance(data, dict):
            raise ApiError("RunPod API returned an unexpected response shape.")
        return data

    def create_pod(self, payload: dict[str, Any]) -> dict[str, Any]:
        response = self._request("POST", "/pods", json=payload)
        return self._json_object(response)

    def get_pod(self, pod_id: str) -> dict[str, Any] | None:
        try:
            response = self._request("GET", f"/pods/{pod_id}")
        except ApiError as exc:
            if exc.status_code == 404:
                return None
            raise
        return self._json_object(response)

    def list_pods(self) -> list[dict[str, Any]]:
        response = self._request("GET", "/pods", params={"computeType": "GPU"})
        try:
            data = response.json()
        except ValueError as exc:
            raise ApiError("RunPod API returned invalid JSON.") from exc
        if not isinstance(data, list) or not all(isinstance(item, dict) for item in data):
            raise ApiError("RunPod API returned an unexpected response shape.")
        return data

    def delete_pod(self, pod_id: str) -> bool:
        try:
            self._request("DELETE", f"/pods/{pod_id}")
        except ApiError as exc:
            if exc.status_code == 404:
                return False
            raise
        return True
