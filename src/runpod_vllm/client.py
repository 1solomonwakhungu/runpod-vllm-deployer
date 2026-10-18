"""Minimal RunPod REST API client."""

from __future__ import annotations

import random
import time
from collections.abc import Callable
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from typing import Any

import httpx

from runpod_vllm.config import ApiVersion, default_api_url
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


# Upper bound on followed v2 list pages (up to 1000 Pods each) to stop cursor loops.
_V2_MAX_LIST_PAGES = 50


class RunPodClient:
    """Pod lifecycle client for RunPod REST v1 (``/v1/pods``) or v2 (``/v2/pods``).

    Both versions use ``Authorization: Bearer <key>`` and the same relative ``/pods``
    paths under their base URL. Responses are returned as raw JSON objects; use
    :func:`runpod_vllm.models.normalize_pod` for a version-independent view.
    """

    def __init__(
        self,
        api_key: str,
        *,
        base_url: str | None = None,
        api_version: ApiVersion = ApiVersion.V1,
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
        self.api_version = api_version
        resolved_url = base_url or default_api_url(api_version)
        self._client = httpx.Client(
            base_url=resolved_url.rstrip("/"),
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
        """Return GPU Pods. v1 returns a bare array; v2 a paginated ``{"pods": [...]}``."""
        if self.api_version is ApiVersion.V2:
            return self._list_pods_v2()
        response = self._request("GET", "/pods", params={"computeType": "GPU"})
        try:
            data = response.json()
        except ValueError as exc:
            raise ApiError("RunPod API returned invalid JSON.") from exc
        if not isinstance(data, list) or not all(isinstance(item, dict) for item in data):
            raise ApiError("RunPod API returned an unexpected response shape.")
        return data

    def _list_pods_v2(self) -> list[dict[str, Any]]:
        pods: list[dict[str, Any]] = []
        params: dict[str, str] = {}
        for _page in range(_V2_MAX_LIST_PAGES):
            page_pods, next_cursor = _parse_v2_pod_page(
                self._json_object(self._request("GET", "/pods", params=params))
            )
            pods.extend(page_pods)
            if next_cursor is None:
                # v2 has no computeType filter; GPU Pods carry a `gpu` block, CPU Pods do not.
                return [pod for pod in pods if isinstance(pod.get("gpu"), dict)]
            params = {"cursor": next_cursor}
        raise ApiError(f"RunPod API returned more than {_V2_MAX_LIST_PAGES} pages of Pods.")

    def delete_pod(self, pod_id: str) -> bool:
        try:
            self._request("DELETE", f"/pods/{pod_id}")
        except ApiError as exc:
            if exc.status_code == 404:
                return False
            raise
        return True


def _parse_v2_pod_page(data: dict[str, Any]) -> tuple[list[dict[str, Any]], str | None]:
    """Split a v2 ``ListPodsResponse`` into its Pods and the next-page cursor."""
    pods = data.get("pods")
    if not isinstance(pods, list) or not all(isinstance(item, dict) for item in pods):
        raise ApiError("RunPod API returned an unexpected response shape.")
    pagination = data.get("pagination")
    if not isinstance(pagination, dict) or not pagination.get("hasNextPage"):
        return pods, None
    cursor = pagination.get("nextCursor")
    if not isinstance(cursor, str) or not cursor:
        raise ApiError("RunPod API reported another page without a valid cursor.")
    return pods, cursor
