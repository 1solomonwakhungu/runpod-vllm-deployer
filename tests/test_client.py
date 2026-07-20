from __future__ import annotations

import httpx
import pytest

from runpod_vllm.client import RunPodClient
from runpod_vllm.errors import ApiError, NetworkError


def test_client_create_get_list_and_delete() -> None:
    seen: list[tuple[str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append((request.method, request.url.path))
        assert request.headers["Authorization"] == "Bearer test-key"
        if request.method == "POST":
            return httpx.Response(201, json={"id": "pod123", "name": "safe"})
        if request.method == "GET" and request.url.path.endswith("/pod123"):
            return httpx.Response(200, json={"id": "pod123", "desiredStatus": "RUNNING"})
        if request.method == "GET":
            return httpx.Response(200, json=[{"id": "pod123"}])
        return httpx.Response(204)

    with RunPodClient("test-key", transport=httpx.MockTransport(handler)) as client:
        assert client.create_pod({"name": "safe"})["id"] == "pod123"
        assert client.get_pod("pod123") == {"id": "pod123", "desiredStatus": "RUNNING"}
        assert client.list_pods() == [{"id": "pod123"}]
        assert client.delete_pod("pod123") is True

    assert seen == [
        ("POST", "/v1/pods"),
        ("GET", "/v1/pods/pod123"),
        ("GET", "/v1/pods"),
        ("DELETE", "/v1/pods/pod123"),
    ]


def test_client_treats_404_as_idempotent_absence() -> None:
    transport = httpx.MockTransport(lambda _request: httpx.Response(404, json={"error": "gone"}))
    with RunPodClient("key", transport=transport) as client:
        assert client.get_pod("missing") is None
        assert client.delete_pod("missing") is False


def test_api_errors_redact_secrets() -> None:
    secret = "sensitive-value"
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            401,
            text=f"Bearer {secret}",
            request=request,
        )
    )
    with RunPodClient(secret, transport=transport) as client, pytest.raises(ApiError) as raised:
        client.list_pods()
    assert secret not in str(raised.value)
    assert "HTTP 401" in str(raised.value)


def test_network_errors_are_actionable() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    with (
        RunPodClient("key", transport=httpx.MockTransport(handler)) as client,
        pytest.raises(NetworkError, match="connection refused"),
    ):
        client.list_pods()


def test_unexpected_json_shapes_fail_cleanly() -> None:
    transport = httpx.MockTransport(lambda _request: httpx.Response(200, json={"not": "a list"}))
    with (
        RunPodClient("key", transport=transport) as client,
        pytest.raises(ApiError, match="unexpected response shape"),
    ):
        client.list_pods()


def test_object_response_invalid_json_and_shape_fail_cleanly() -> None:
    invalid_json = httpx.MockTransport(lambda _request: httpx.Response(200, text="not-json"))
    with (
        RunPodClient("key", transport=invalid_json) as client,
        pytest.raises(ApiError, match="invalid JSON"),
    ):
        client.create_pod({})

    wrong_shape = httpx.MockTransport(lambda _request: httpx.Response(200, json=[]))
    with (
        RunPodClient("key", transport=wrong_shape) as client,
        pytest.raises(ApiError, match="unexpected response shape"),
    ):
        client.create_pod({})


def test_list_invalid_json_fails_cleanly() -> None:
    transport = httpx.MockTransport(lambda _request: httpx.Response(200, text="not-json"))
    with (
        RunPodClient("key", transport=transport) as client,
        pytest.raises(ApiError, match="invalid JSON"),
    ):
        client.list_pods()
