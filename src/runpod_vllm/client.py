"""Minimal RunPod REST API client."""

from __future__ import annotations

from typing import Any

import httpx

from runpod_vllm.config import ApiVersion, default_api_url
from runpod_vllm.errors import ApiError, NetworkError
from runpod_vllm.redaction import redact_text, redact_url

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
    ) -> None:
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

    def _request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        try:
            response = self._client.request(method, path, **kwargs)
        except httpx.RequestError as exc:
            url = redact_url(str(exc.request.url)) if exc.request else path
            raise NetworkError(f"RunPod request failed for {url}: {redact_text(str(exc))}") from exc
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
