"""Minimal RunPod REST API client."""

from __future__ import annotations

from typing import Any

import httpx

from runpod_vllm.errors import ApiError, NetworkError
from runpod_vllm.redaction import redact_text, redact_url


class RunPodClient:
    def __init__(
        self,
        api_key: str,
        *,
        base_url: str = "https://rest.runpod.io/v1",
        timeout: float = 30.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
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
